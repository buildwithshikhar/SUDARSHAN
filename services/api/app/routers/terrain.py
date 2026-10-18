"""Terrain pack files for the 3D scene (docs/TERRAIN_PACKS.md): read-only, signed-in users."""

import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth import require_roles
from app.models import Role
from sim.terrain import pack_dir

router = APIRouter(prefix="/api/v1/terrain", tags=["terrain"])

READERS = require_roles(Role.trainee, Role.instructor, Role.admin)
#: Exactly the files a pack may serve. Anything else, including a path, is a 404.
FILES: dict[str, str] = {
    "manifest.json": "application/json",
    "heights.i16": "application/octet-stream",
    "buildings.json": "application/json",
    "vegetation.json": "application/json",
    "terrain.glb": "model/gltf-binary",
    "buildings.glb": "model/gltf-binary",
    "ATTRIBUTION.md": "text/markdown; charset=utf-8",
}
#: Packs are immutable per version, but a file can change when a pack is re-baked.
CACHE = "private, max-age=3600"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@router.get("/{pack_id}/{file}", dependencies=[Depends(READERS)])
def pack_file(pack_id: str, file: str) -> FileResponse:
    media_type = FILES.get(file)
    # A pack id is a directory name under packs/terrain; refuse anything that is not a slug.
    if media_type is None or not SLUG.fullmatch(pack_id):
        raise HTTPException(status_code=404, detail="no such terrain file")
    path = pack_dir(pack_id) / file
    if not path.is_file():
        raise HTTPException(status_code=404, detail="no such terrain file")
    return FileResponse(path, media_type=media_type, headers={"Cache-Control": CACHE})
