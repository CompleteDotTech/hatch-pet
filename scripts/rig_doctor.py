"""3D availability inspection without importing NumPy, Blender or a browser."""
import importlib.util
import importlib.metadata
import os
from pathlib import Path
import shutil


def rig_capability_description():
    return dict(schema_version=1,command='python scripts/hatch.py rig',optional=True,
        inputs=['glb','gltf','obj','blend'],coordinate_system='RH +Y up +Z forward; meters; XYZW quaternions',
        templates=['humanoid','quadruped','winged-creature','robotic','custom'],
        exports=['glb','gltf','blend','transparent-frames','portable-zip'],
        review='Hash-bound numerical evidence and separate visual approval; synthetic fixtures retain their provenance.',
        generation_provider='No remote 3D provider is configured. Import genuine generated meshes with their provenance.')


def doctor():
    packages={}
    for name in ('numpy','jsonschema','Pillow','playwright','pygltflib'):
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:packages[name]=None
    blender=os.environ.get('HATCH_BLENDER') or shutil.which('blender')
    validator=Path(os.environ.get('HATCH_GLTF_VALIDATOR_ROOT',str(Path(__file__).resolve().parents[1]/'tools/rig/node_modules/gltf-validator')))
    return dict(ok=bool(packages['numpy'] and packages['jsonschema']),packages=packages,blender=blender,
        node=shutil.which('node'),khronos_validator=validator.is_dir(),offline_three_version='0.180.0',
        ffmpeg=shutil.which('ffmpeg'),capabilities=rig_capability_description(),
        note='Missing optional authoring/viewer tools do not disable the existing 2D workflow.')
