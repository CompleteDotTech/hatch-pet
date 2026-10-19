"""Raster regressions use synthetic fixtures only, never production artwork."""
import argparse,copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from PIL import Image,ImageDraw
import extract_strip_frames as e
import inspect_frames as q
from profile_spec import load_profile

class RasterTests(unittest.TestCase):
    def strip(self,ys=(50,20),widths=(30,30)):
        im=Image.new('RGBA',(200,100));draw=ImageDraw.Draw(im)
        for i,(y,w) in enumerate(zip(ys,widths)):draw.rectangle((i*100+50-w//2,y,i*100+50+w//2,y+25),fill=(200,40,20,255))
        return im
    def test_jump_preserved(self):
        frames=e.extract_component_frames(self.strip(),2)
        self.assertEqual(frames[0].getbbox()[1]-frames[1].getbbox()[1],30)
    def test_scale_stable(self):
        frames=e.extract_component_frames(self.strip(widths=(30,70)),2)
        self.assertEqual(frames[0].getbbox()[3]-frames[0].getbbox()[1],frames[1].getbbox()[3]-frames[1].getbbox()[1])
    def test_extra_pose_rejected(self):
        im=self.strip();ImageDraw.Draw(im).rectangle((5,50,25,75),fill='blue')
        with self.assertRaisesRegex(ValueError,'extra complete pose'):e.extract_component_frames(im,2)
    def test_merged_neighbor_rejected(self):
        im=self.strip();ImageDraw.Draw(im).rectangle((65,50,135,52),fill='blue')
        with self.assertRaisesRegex(ValueError,'boundary-crossing'):e.extract_component_frames(im,2)
    def test_missing_pose_rejected(self):
        im=self.strip();ImageDraw.Draw(im).rectangle((100,0,199,99),fill=(0,0,0,0))
        with self.assertRaisesRegex(ValueError,'missing pose'):e.extract_component_frames(im,2)
    def test_alpha_and_small_details(self):
        im=self.strip();im.putpixel((47,48),(0,255,0,128));im.putpixel((50,55),(0,0,0,0))
        out,receipt=e.mask_background(im,(0,255,0),96)
        self.assertEqual(receipt['mode'],'alpha');self.assertEqual(out.getpixel((47,48)),(0,255,0,128));self.assertEqual(out.getpixel((50,55)),(0,0,0,0))
    def test_enclosed_key_color_preserved(self):
        im=Image.new('RGBA',(100,100),(0,255,0,255));d=ImageDraw.Draw(im);d.rectangle((20,20,80,80),fill='red');d.rectangle((40,40,50,50),fill=(0,255,0,255))
        out,r=e.mask_background(im,(0,255,0),48,'chroma');self.assertEqual(out.getpixel((0,0)),(0,0,0,0));self.assertEqual(out.getpixel((45,45)),(0,255,0,255));self.assertTrue(r['warnings'])
    def test_diagonal_and_antialias_connected(self):
        im=Image.new('RGBA',(10,10));im.putpixel((1,1),(1,1,1,255));im.putpixel((2,2),(1,1,1,1));self.assertEqual(len(e.connected_components(im)),1)
    def test_missing_manifest_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'missing extraction'):q.load_manifest(Path(td))
    def test_temporal_metrics(self):
        im=e.extract_component_frames(self.strip(ys=(50,50)),2)[0]
        metric,warnings=q.temporal_metrics([im,im],{'id':'idle','motion':'quiet'})
        self.assertTrue(metric['pairwise'][0]['exact']);self.assertTrue(any('insufficient' in w for w in warnings))
    def test_provenance_stale_and_partial_merge(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); decoded=root/'decoded';decoded.mkdir();frames=root/'frames';frames.mkdir();(root/'pet_request.json').write_text('{}')
            profile=load_profile();profile=copy.deepcopy(profile);profile['states']=profile['states'][:2]
            for state in profile['states']:state['frames']=2;state['durations']=[100,100]
            rows=[]
            for spec in profile['states']:
                source=decoded/(spec['id']+'.png');self.strip().save(source)
                row=e.extract_state(source,spec['id'],frames,(0,255,0),48,'auto',profile);row['request_sha256']=e.digest(root/'pet_request.json');rows.append(row)
            e.atomic_json(frames/'frames-manifest.json',{'schema_version':e.EXTRACTION_SCHEMA,'algorithm':e.EXTRACTION_ALGORITHM,'rows':rows})
            untouched=json.dumps(rows[1],sort_keys=True)
            replacement=e.extract_state(decoded/'idle.png','idle',frames,(0,255,0),48,'auto',profile);replacement['request_sha256']=e.digest(root/'pet_request.json')
            merged=q.load_manifest(frames);merged['idle']=replacement;e.atomic_json(frames/'frames-manifest.json',{'schema_version':e.EXTRACTION_SCHEMA,'algorithm':e.EXTRACTION_ALGORITHM,'rows':list(merged.values())})
            self.assertEqual(json.dumps(q.load_manifest(frames)['running-right'],sort_keys=True),untouched)
            files=q.frame_files(frames/'idle');self.assertEqual(q.validate_provenance(frames,'idle',files,replacement,profile),[])
            (root/'pet_request.json').write_text('{"changed":true}');self.assertTrue(any('stale request' in x for x in q.validate_provenance(frames,'idle',files,replacement,profile)))
            files[0].write_bytes(files[1].read_bytes());self.assertTrue(any('frame hashes' in x for x in q.validate_provenance(frames,'idle',files,replacement,profile)))
    def test_partial_cli_keeps_other_rows(self):
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);decoded=root/'decoded';decoded.mkdir();frames=root/'frames'
            profile=load_profile();profile=copy.deepcopy(profile);profile['states']=profile['states'][:2]
            for key in ('rows','width','height'):profile['layout'].pop(key,None)
            for state in profile['states']:state['frames']=2;state['durations']=[100,100]
            profile['events']={};profile['export']={'formats':['frames'],'static_state':'idle','static_frame':0};profile['export']['codex_compatible']=False
            (root/'profile.json').write_text(json.dumps(profile));(root/'pet_request.json').write_text('{}')
            for spec in profile['states']:self.strip().save(decoded/(spec['id']+'.png'))
            cmd=[sys.executable,str(Path(e.__file__)),'--decoded-dir',str(decoded),'--output-dir',str(frames)]
            subprocess.run(cmd,check=True,capture_output=True);before=q.load_manifest(frames)['running-right']
            subprocess.run(cmd+['--states','idle'],check=True,capture_output=True);self.assertEqual(q.load_manifest(frames)['running-right'],before)

if __name__=='__main__':unittest.main()
