import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from rig_test_helpers import fixture
from rig_http import RigServer


class RigHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.rig=fixture(self.temp.name)
        self.server=RigServer(self.temp.name,self.temp.name,token='test-fixture-token-0123456789')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def request(self,method,path,body=None,*,token=True,origin=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        headers={'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+self.server.token
        if origin:headers['Origin']=origin
        connection.request(method,path,json.dumps(body).encode() if body is not None else None,headers)
        response=connection.getresponse();value=json.loads(response.read());status=response.status;connection.close();return status,value
    def test_token_origin_and_intake_paths_are_enforced(self):
        self.assertEqual(self.request('GET','/v1/rigs/fixture',token=False)[0],401)
        self.assertEqual(self.request('GET','/v1/rigs/fixture',origin='https://evil.invalid')[0],403)
        self.assertEqual(self.request('POST','/v1/rig-jobs',{'model':'../outside.glb'})[0],400)
    def test_import_status_analyze_and_artifacts(self):
        code,data=self.request('POST','/v1/rig-jobs',{'model':'fixture.glb','id':'api-import'})
        self.assertEqual(code,200,data);self.assertTrue(data['fixture'])
        self.assertEqual(self.request('GET','/v1/rig-jobs/api-import')[0],200)
        self.assertEqual(self.request('POST','/v1/rig-jobs/api-import/analyze',{})[0],200)
        code,data=self.request('GET','/v1/rig-jobs/api-import/artifacts');self.assertEqual(code,200);self.assertTrue(data['artifacts'])
    def test_pose_ik_validation_and_export_are_real(self):
        code,pose=self.request('POST','/v1/rigs/fixture/pose',{'clip':'bend','time':.5});self.assertEqual(code,200,pose);self.assertIn('b1',pose['bones'])
        code,value=self.request('POST','/v1/rigs/fixture/solve-ik',{'chain':'arm','target':[1,1,0]});self.assertEqual(code,200,value);self.assertLess(value['report']['residual_m'],1e-5)
        code,value=self.request('POST','/v1/rig-jobs/fixture/validate',{'require_animation':True});self.assertEqual(code,200,value)
        code,value=self.request('POST','/v1/rig-jobs/fixture/export',{'format':'glb','destination':'exports/api.glb'});self.assertEqual(code,200,value);self.assertTrue((self.rig.root/'exports/api.glb').is_file())
        self.assertEqual(self.request('POST','/v1/rig-jobs/fixture/export',{'format':'glb','destination':'../outside.glb'})[0],400)
    def test_unknown_parameters_and_routes_fail(self):
        self.assertEqual(self.request('POST','/v1/rig-jobs/fixture/skin',{'arbitrary':'code'})[0],400)
        self.assertEqual(self.request('GET','/v1/rig-jobs/absent')[0],404)
