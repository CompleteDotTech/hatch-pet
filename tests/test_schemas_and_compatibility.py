"""Schema consistency, supported old workflows and explicit operational errors."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import jsonschema
from fixture_workflow import build_run, record_fixture_review, hatch, small_profile
from profile_spec import load_profile, FORMATS
from doctor import doctor, capabilities
from generate_schemas import build
from asset_contracts import generation_projection

ROOT=Path(__file__).resolve().parents[1]


class ContractChecks(unittest.TestCase):
    def test_schemas_match_every_profile_and_catalog(self):
        for path,value in build().items():self.assertEqual(json.loads(path.read_text(encoding='utf-8')),value)
        schema=hatch.read(ROOT/'profiles/profile.schema.json')
        for path in [ROOT/'profiles/codex-v1.json',*sorted((ROOT/'examples').glob('*.json')),*sorted((ROOT/'presets').glob('*.json'))]:
            if path.name!='catalog.json':
                raw=hatch.read(path);jsonschema.validate(raw,schema);load_profile(raw)
        self.assertEqual(set(capabilities()['exporters']),FORMATS)

    def test_doctor_reports_actual_codecs_and_destination_probe(self):
        with tempfile.TemporaryDirectory() as td:
            result=doctor(td,ROOT/'presets/cursor.json')
            self.assertTrue(result['ok']);self.assertTrue(result['codecs']['webp'])
            self.assertTrue(result['filesystem']['atomic_rename_probe'])
            self.assertIn('source_pixel_limit',result['resources'])

    def test_invalid_extension_combinations_and_unknown_fields(self):
        p=small_profile();p['export']['formats']=['board']
        with self.assertRaisesRegex(ValueError,'requires browser'):load_profile(p)
        p=small_profile();p['states'][0]['alignment']['resampling']='unavailable'
        with self.assertRaisesRegex(ValueError,'resampling'):load_profile(p)
        p=small_profile();p['playback']={'plugin':'arbitrary.py'}
        with self.assertRaisesRegex(ValueError,'supported keys'):load_profile(p)
        p=small_profile();p['states'][0]['playback']={'mode':'loop','completion':'jump'}
        with self.assertRaisesRegex(ValueError,'requires once'):load_profile(p)

    def test_annotation_changes_are_fresh_and_invalid_permissions_are_preserved_for_diagnosis(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';data=build_run(root);record_fixture_review(root,data)
            path=Path(td)/'annotation.json'
            hatch.atomic(path,{'schema_version':1,'source_sha256':'0'*64,'author':'test','note':'bad source hash','frames':[]})
            with self.assertRaisesRegex(ValueError,'exact source'):hatch.annotate(root,data,'rest',path)
            self.assertTrue((root/'qa/extraction-diagnostics/rest.png').is_file())
            self.assertFalse((root/'annotations/rest.json').exists())
            # Failed attempts leave existing evidence current; no accepted raster changed.
            self.assertTrue(hatch.status(root,data)['reviewed'])

    def test_unrelated_calibration_does_not_reextract_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';data=build_run(root)
            hatch.configure(root,data,argparse.Namespace(chroma_key=None,shared_scale=.5))
            hatch.record_base_review(root,data,'Fixture row-scale extraction is unaffected by shared-scale calibration.')
            result=hatch.validate(root,data)
            self.assertEqual(result['extracted_states'],[])

    def test_extractor_implementation_hash_is_required(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';data=build_run(root)
            path=root/'frames/frames-manifest.json';value=hatch.read(path)
            value['rows'][0]['extractor_sha256']='0'*64;hatch.atomic(path,value)
            result=hatch.validate(root,data)
            self.assertEqual(result['extracted_states'],['rest'])

    def test_changed_backup_cannot_be_rolled_back(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';data=build_run(root);record_fixture_review(root,data)
            package=Path(td)/'package';hatch.package(root,data,package)
            target=Path(td)/'target';target.mkdir()
            hatch.atomic(target/'pet.json',{'id':'old','spritesheetPath':'spritesheet.webp'})
            from PIL import Image
            Image.new('RGBA',(10,10),'blue').save(target/'spritesheet.webp')
            record=hatch.install(root,data,package,target,True)
            backup=Path(record['backup']);(backup/'pet.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'unbound or changed'):hatch.rollback(root,data)
            self.assertEqual(hatch.verify_package(target)['run_id'],data['run_id'])

    def test_reference_role_tampering_is_not_approved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'run';data=build_run(root)
            request=hatch.read(root/'pet_request.json')
            # Record a required copied reference and its immutable declared role.
            target=root/'references/front.png';target.write_bytes((root/'references/canonical-base.png').read_bytes())
            request['references']=[{'copied_path':'references/front.png','role':'front'}]
            hatch.atomic(root/'pet_request.json',request)
            for job in data['jobs']:job['input_images'].append({'path':'references/front.png','role':'side'})
            hatch.save(root,data)
            with self.assertRaisesRegex(ValueError,'reference role'):hatch.manifest(root)


class LegacyExampleWorkflows(unittest.TestCase):
    pass


def legacy_case(path):
    def test(self):
        with tempfile.TemporaryDirectory(prefix='hatch-legacy-profile-') as td:
            root=Path(td)/'run';data=build_run(root,path);record_fixture_review(root,data)
            hatch.export(root,data,Path(td)/'export')
            self.assertTrue(hatch.status(root,data)['reviewed'])
            self.assertEqual(hatch.read(Path(td)/'export/animation.json')['profile_id'],load_profile(path)['id'])
    return test


for path in sorted((ROOT/'examples').glob('*.json')):
    setattr(LegacyExampleWorkflows,'test_'+path.stem.replace('-','_'),legacy_case(path))


if __name__=='__main__':unittest.main()
