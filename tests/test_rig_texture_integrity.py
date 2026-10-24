"""Genuine textured source fixtures must decode, not merely have valid headers."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

import numpy as np
from PIL import Image, ImageFile, PngImagePlugin

from rig_contracts import DEFAULT_LIMITS
from rig_errors import RigError
from rig_gltf import export_geometry
from rig_import import _decode_texture, load_character_model
from rig_jobs import create_run
from rig_models import TextureImage
from test_rig_skinning import test_geometry


ROOT = Path(__file__).resolve().parents[1]


def image_bytes(mode='RGB', fmt='PNG', size=(16, 16)):
    rng = np.random.default_rng(7)
    channels = {'L': 1, 'RGB': 3, 'RGBA': 4, 'CMYK': 4}[mode]
    shape = (*size[::-1], channels) if channels > 1 else size[::-1]
    image = Image.fromarray(rng.integers(0, 256, shape, dtype=np.uint8), mode=mode)
    stream = io.BytesIO();image.save(stream, format=fmt)
    return stream.getvalue()


def png_chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def png_with_bad_pixels():
    # Valid container/chunk CRCs, but no valid zlib scanlines. verify() accepts it.
    return (b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
            + png_chunk(b'IDAT', b'not a zlib stream') + png_chunk(b'IEND', b''))


class TextureIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def model(self, data, suffix='.glb', *, mime='image/png', external=False, data_uri=False, images=1):
        geometry = test_geometry()
        geometry.meshes[0].attributes['TEXCOORD_0'] = np.array([[0, 0], [1, 0], [0, 1], [1, 1]], float)
        geometry.images = [TextureImage('synthetic texture', mime, data) for _ in range(images)]
        geometry.textures = [dict(source=0)]
        geometry.materials[0]['pbrMetallicRoughness'] = dict(baseColorTexture=dict(index=0))
        path = self.root / ('synthetic-' + str(len(list(self.root.iterdir()))) + suffix)
        export_geometry(geometry, path, provenance=dict(fixture=True))
        if external or data_uri:
            value = json.loads(path.read_bytes())
            uri = 'texture-' + path.stem + ('.jpg' if mime == 'image/jpeg' else '.png')
            if external: (self.root / uri).write_bytes(data)
            else: uri = 'data:' + mime + ';base64,' + base64.b64encode(data).decode('ascii')
            value['images'] = [dict(uri=uri, mimeType=mime)]
            path.write_text(json.dumps(value), 'utf-8')
        return path

    def obj(self, data, extension='.png', *, images=1):
        parent = self.root / ('obj-' + str(len(list(self.root.iterdir()))));parent.mkdir()
        lines = []
        for i in range(images):
            (parent / (str(i) + extension)).write_bytes(data)
            lines += [f'newmtl material{i}', f'map_Kd {i}{extension}']
        (parent / 'texture.mtl').write_text('\n'.join(lines) + '\n')
        path = parent / 'mesh.obj'
        path.write_text('mtllib texture.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\n'
                        'vt 0 0\nvt 1 0\nvt 0 1\nusemtl material0\nf 1/1 2/2 3/3\n')
        return path

    def assert_rejected(self, path, code, **kwargs):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaises(RigError) as caught: load_character_model(path, **kwargs)
        self.assertEqual(caught.exception.report['code'], code)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()})

    def test_actual_png_jpeg_modes_preserve_encoded_bytes_and_native_roundtrip(self):
        for mode, fmt in [('L', 'PNG'), ('RGB', 'PNG'), ('RGBA', 'PNG'), ('L', 'JPEG'), ('RGB', 'JPEG'), ('CMYK', 'JPEG')]:
            for suffix in ('.glb', '.gltf'):
                with self.subTest(mode=mode, fmt=fmt, suffix=suffix):
                    data = image_bytes(mode, fmt);mime = 'image/png' if fmt == 'PNG' else 'image/jpeg'
                    path = self.model(data, suffix, mime=mime)
                    before = path.read_bytes();imported = load_character_model(path)
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(imported.geometry.images[0].data, data)
                    self.assertEqual(imported.geometry.images[0].mime_type, mime)
                    output = self.root / ('again-' + path.stem + suffix)
                    export_geometry(imported.geometry, output, provenance=dict(fixture=True))
                    self.assertEqual(load_character_model(output).geometry.images[0].data, data)

    def test_truncated_jpeg_is_rejected_in_all_gltf_storage_forms(self):
        data = image_bytes(fmt='JPEG');self.assertEqual(data[-2:], b'\xff\xd9')
        damaged = data[:-2]
        Image.open(io.BytesIO(damaged)).verify()
        with self.assertRaises(OSError): Image.open(io.BytesIO(damaged)).load()
        for suffix, external, data_uri in [('.glb', False, False), ('.gltf', False, False), ('.gltf', True, False), ('.gltf', False, True)]:
            with self.subTest(suffix=suffix, external=external, data_uri=data_uri):
                self.assert_rejected(self.model(damaged, suffix, mime='image/jpeg', external=external, data_uri=data_uri), 'RIG_TEXTURE_DECODE')

    def test_png_valid_crc_but_invalid_pixels_and_broken_crc_are_structured(self):
        damaged = png_with_bad_pixels();Image.open(io.BytesIO(damaged)).verify()
        with self.assertRaises(OSError): Image.open(io.BytesIO(damaged)).load()
        crc_bad = bytearray(image_bytes());pos = crc_bad.index(b'IDAT') + 4;crc_bad[pos] ^= 1
        for data in (damaged, bytes(crc_bad)):
            for suffix in ('.glb', '.gltf'):
                self.assert_rejected(self.model(data, suffix), 'RIG_TEXTURE_DECODE')

    def test_obj_uses_same_pixel_integrity_and_aggregate_budget(self):
        for fmt, extension in [('PNG', '.png'), ('JPEG', '.jpg')]:
            data = image_bytes(fmt=fmt)
            path = self.obj(data, extension)
            imported = load_character_model(path)
            self.assertEqual(imported.geometry.images[0].data, data)
            self.assertEqual(set(imported.source_files), {path, path.parent / 'texture.mtl', path.parent / ('0' + extension)})
        self.assert_rejected(self.obj(image_bytes(fmt='JPEG')[:-2], '.jpg'), 'RIG_TEXTURE_DECODE')
        self.assert_rejected(self.obj(png_with_bad_pixels()), 'RIG_TEXTURE_DECODE')
        data = image_bytes(size=(4, 4))
        self.assert_rejected(self.obj(data, images=2), 'RIG_LIMIT_TEXTURE', limits={**DEFAULT_LIMITS, 'memory_bytes': 800})

    def test_encoded_and_decoded_limits_precede_pixel_allocation(self):
        data = image_bytes()
        with patch('PIL.Image.open', side_effect=AssertionError('encoded limit must run first')):
            with self.assertRaises(RigError) as caught: _decode_texture(data, {**DEFAULT_LIMITS, 'source_bytes': len(data) - 1})
            self.assertEqual(caught.exception.report['code'], 'RIG_LIMIT_TEXTURE')
        # Header has a real CRC but exceeds the core pixel cap; no raster exists.
        data = b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', struct.pack('>IIBBBBB', 4097, 4096, 8, 2, 0, 0, 0)) + png_chunk(b'IDAT', b'x') + png_chunk(b'IEND', b'')
        with patch.object(PngImagePlugin.PngImageFile, 'load', side_effect=AssertionError('pixel limit must run first')):
            self.assert_rejected(self.model(data), 'RIG_LIMIT_TEXTURE')

    def test_aggregate_gltf_budget_precedes_second_image_load(self):
        data = image_bytes(size=(4, 4));path = self.model(data, images=2)
        calls = []
        original = PngImagePlugin.PngImageFile.load
        def load(image, *args, **kwargs):
            calls.append(image.size)
            return original(image, *args, **kwargs)
        with patch.object(PngImagePlugin.PngImageFile, 'load', load):
            self.assert_rejected(path, 'RIG_LIMIT_TEXTURE', limits={**DEFAULT_LIMITS, 'memory_bytes': 800})
        self.assertEqual(calls, [(4, 4)])

    def test_decoded_memory_exact_boundary_is_inclusive(self):
        data = image_bytes(size=(4, 3))
        self.assertEqual(_decode_texture(data, {**DEFAULT_LIMITS, 'memory_bytes': 12 * 32}), ('image/png', 12))
        with self.assertRaises(RigError) as caught:
            _decode_texture(data, {**DEFAULT_LIMITS, 'memory_bytes': 12 * 32 - 1})
        self.assertEqual(caught.exception.report['code'], 'RIG_LIMIT_TEXTURE')

    def test_pillow_bomb_warning_and_error_are_structured_without_global_mutation(self):
        data = image_bytes(size=(4, 3));path = self.model(data)
        for threshold in (8, 4):
            with patch.object(Image, 'MAX_IMAGE_PIXELS', threshold):
                self.assert_rejected(path, 'RIG_LIMIT_TEXTURE')
                self.assertEqual(Image.MAX_IMAGE_PIXELS, threshold)

    def test_mime_animation_and_lax_decoder_policy_fail_closed(self):
        self.assert_rejected(self.model(image_bytes(), mime='image/jpeg'), 'RIG_TEXTURE_FORMAT')
        stream = io.BytesIO()
        Image.new('RGBA', (2, 2), 'red').save(stream, format='PNG', save_all=True,
                                            append_images=[Image.new('RGBA', (2, 2), 'blue')], duration=100, loop=0)
        self.assert_rejected(self.model(stream.getvalue()), 'RIG_TEXTURE_FORMAT')
        path = self.model(image_bytes())
        with patch.object(ImageFile, 'LOAD_TRUNCATED_IMAGES', True):
            self.assert_rejected(path, 'RIG_TEXTURE_POLICY')
            self.assertTrue(ImageFile.LOAD_TRUNCATED_IMAGES)

    def test_actual_cli_bad_pixels_never_publish_a_run_or_modify_sources(self):
        path = self.model(image_bytes(fmt='JPEG')[:-2], mime='image/jpeg')
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir() if p.is_file()}
        destination = self.root / 'rejected-run'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/rig.py'), 'import', '--model', str(path),
                                 '--run-dir', str(destination)], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Traceback', result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)['error']['code'], 'RIG_TEXTURE_DECODE')
        self.assertFalse(destination.exists())
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()
                                  if p.is_file() and not p.name.endswith('.rig.lock')})

    @unittest.skipUnless(os.environ.get('HATCH_RIG_INTEROP_TEST') == '1', 'Enable the declared independent Khronos gate.')
    def test_actual_valid_png_jpeg_exports_pass_independent_khronos(self):
        from rig_interop import validate_gltf
        for fmt, mime in [('PNG', 'image/png'), ('JPEG', 'image/jpeg')]:
            for suffix in ('.glb', '.gltf'):
                path = self.model(image_bytes(fmt=fmt), suffix, mime=mime)
                result = validate_gltf(path)
                self.assertTrue(result['ok'], result)
                self.assertEqual(result['issues']['numErrors'], 0)
                self.assertEqual(result['issues']['numWarnings'], 0)


if __name__ == '__main__': unittest.main()
