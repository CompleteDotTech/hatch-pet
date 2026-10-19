"""Every advertised use must build inspectable files and pass its own acceptance checks."""
from pathlib import Path
import tempfile
import unittest

from fixture_workflow import hatch
from demonstrate import ROOT, acceptance, demonstrate
from generate_presets import build
from profile_spec import load_profile
from asset_exporters import read_xcursor


class Demonstrations(unittest.TestCase):
    def test_generated_profiles_and_recipes_have_no_drift(self):
        for path, expected in build().items():
            self.assertEqual(path.read_text(encoding='utf-8'),expected,path.name)

    def test_xcursor_decoder_rejects_truncation(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'invalid.xcursor';path.write_bytes(b'Xcur')
            with self.assertRaisesRegex(ValueError,'truncated'):read_xcursor(path)


def make_case(name):
    def test(self):
        with tempfile.TemporaryDirectory(prefix='hatch-use-'+name+'-') as td:
            result=demonstrate(name,td)
            self.assertTrue(result['ok']);self.assertTrue(result['fixture']);self.assertFalse(result['external_integration_verified'])
            out=Path(td)/name
            self.assertTrue((out/'export/export-receipt.json').is_file())
            self.assertTrue((out/'review/review.html').is_file())
            data=hatch.manifest(out/'run')
            self.assertTrue(all('import_receipt' in j and 'generation_receipt' not in j for j in data['jobs']))
            self.assertEqual(result['checks'],acceptance(name,out,load_profile(ROOT/'presets'/(name+'.json')))['checks'])
            if name=='cursor':
                path=out/'export/busy.xcursor';raw=path.read_bytes();path.write_bytes(raw[:-1])
                with self.assertRaisesRegex(ValueError,'truncated'):read_xcursor(path)
    return test


for name in hatch.read(ROOT/'presets/catalog.json'):
    setattr(Demonstrations,'test_'+name+'_demonstration',make_case(name))


if __name__=='__main__':unittest.main()
