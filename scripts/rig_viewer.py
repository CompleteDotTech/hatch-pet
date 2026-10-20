"""Portable offline Three.js rig inspection bundle; serve only on localhost."""
from pathlib import Path
import shutil
from rig_errors import atomic_json, require
from rig_gltf import export_gltf
from rig_models import rig_signature


def create_review_ui(rig,destination):
    require(all(w.indices.shape[1]<=4 for w in rig.weights.values()),'RIG_VIEWER_INFLUENCES',
            'The pinned Three.js viewer supports four influences; use an eight-influence-capable external consumer for that profile.')
    destination=Path(destination).absolute();require(not destination.exists(),'RIG_VIEWER_EXISTS','Use a new review destination.')
    assets=Path(__file__).resolve().parents[1]/'assets/rig-viewer';shutil.copytree(assets,destination)
    export_gltf(rig,destination/'character.glb')
    atomic_json(destination/'review.json',dict(schema_version=1,rig_sha256=rig_signature(rig.manifest),rig=rig.manifest,clips=rig.clips))
    return dict(path=str(destination/'index.html'),serve=f'python -m http.server 8765 --bind 127.0.0.1 --directory {destination}',
                url='http://127.0.0.1:8765/',offline=True,review_status=rig.manifest['review']['status'])
