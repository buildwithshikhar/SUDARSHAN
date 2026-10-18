"""Command line: ``python -m terrain bake|scan|verify``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pack import bake_area, load_areas, verify_pack, write_pack
from .scan import scan_candidates
from .srtm import SrtmTile

TOOL_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = TOOL_DIR.parents[1]
DEFAULT_AREAS = TOOL_DIR / "areas.json"
DEFAULT_OUT = REPO_ROOT / "packs" / "terrain"
DEFAULT_RAW = REPO_ROOT / "data" / "raw"
SRTM_NAME = "N17E074.SRTMGL1.hgt.zip"


def _find_pbf(raw: Path) -> Path:
    found = sorted(raw.glob("*.osm.pbf"))
    if not found:
        raise SystemExit(f"no .osm.pbf file in {raw}")
    return found[0]


def _find_srtm(raw: Path) -> Path:
    p = raw / SRTM_NAME
    if p.is_file():
        return p
    found = sorted(raw.glob("*.hgt.zip"))
    if not found:
        raise SystemExit(f"no SRTM .hgt.zip file in {raw}")
    return found[0]


def cmd_bake(args: argparse.Namespace) -> int:
    areas = load_areas(Path(args.areas))
    wanted = areas if args.area == "all" else [a for a in areas if a.id == args.area]
    if not wanted:
        raise SystemExit(f"unknown area {args.area!r}; known: {', '.join(a.id for a in areas)}")
    raw = Path(args.raw)
    tile = SrtmTile.from_zip(_find_srtm(raw))
    pbf = _find_pbf(raw)
    status = 0
    for area in wanted:
        files, rep = bake_area(area, tile, pbf)
        out = Path(args.out) / area.id
        write_pack(out, files)
        b = rep.buildings
        total = sum(len(v) for v in files.values())
        print(f"[{area.id}] {area.name} ({area.kind}) -> {out}")
        print(
            f"  heights {rep.heights_min_m:+.1f} .. {rep.heights_max_m:+.1f} m "
            f"about datum {rep.datum_m} m"
        )
        print(
            f"  buildings kept {b.kept}: "
            + ", ".join(f"{k} {v}" for k, v in sorted(b.height_source.items()))
        )
        print(
            f"  dropped: invalid {b.dropped_invalid}, outside square {b.dropped_outside}, "
            f"sensitive {b.dropped_sensitive} ({dict(b.sensitive_reasons)}), "
            f"over cap {b.dropped_over_cap}; "
            f"sensitive areas removed {rep.sensitive_areas_dropped}"
        )
        print(f"  trees {rep.trees}; pack size {total / 1e6:.2f} MB")
        for name, data in sorted(files.items()):
            print(f"    {name:<16} {len(data):>10,d} B")
        errors = verify_pack(out)
        reproducible = json.loads(files["manifest.json"])["bake"]["reproducible"]
        print(f"  reproducible (two in-process bakes identical): {reproducible}")
        if errors or not reproducible:
            for e in errors:
                print(f"  VERIFY FAILED: {e}", file=sys.stderr)
            status = 1
    return status


def cmd_verify(args: argparse.Namespace) -> int:
    status = 0
    for p in args.pack:
        errors = verify_pack(Path(p))
        if errors:
            status = 1
            for e in errors:
                print(f"{p}: {e}", file=sys.stderr)
        else:
            print(f"{p}: OK")
    return status


def cmd_scan(args: argparse.Namespace) -> int:
    tile = SrtmTile.from_zip(_find_srtm(Path(args.raw)))
    around = (args.around_lat, args.around_lon) if args.around_lat is not None else None
    cands = scan_candidates(
        tile, _find_pbf(Path(args.raw)), args.half, args.step, around, args.max_km
    )
    if args.kind == "urban":
        cands.sort(key=lambda c: (-c.buildings, c.sensitive))
    else:
        cands = [c for c in cands if args.min_buildings <= c.buildings <= args.max_buildings]
        cands.sort(key=lambda c: (c.sensitive, -c.relief_m))
    print("lat        lon         buildings  relief_m  sensitive  wooded")
    for c in cands[: args.top]:
        print(
            f"{c.lat:.4f}  {c.lon:.4f}  {c.buildings:>9d}  {c.relief_m:>8.1f}  "
            f"{c.sensitive:>9d}  {c.wooded:>6d}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="terrain", description="Terrain pack bake tool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bake", help="bake one area or all")
    b.add_argument("area", help="area id from areas.json, or 'all'")
    b.add_argument(
        "--raw", default=str(DEFAULT_RAW), help="directory with the SRTM zip and OSM pbf"
    )
    b.add_argument("--out", default=str(DEFAULT_OUT), help="output directory for packs")
    b.add_argument("--areas", default=str(DEFAULT_AREAS), help="areas.json path")
    b.set_defaults(fn=cmd_bake)

    v = sub.add_parser("verify", help="re-hash a pack against its manifest")
    v.add_argument("pack", nargs="+", help="pack directory")
    v.set_defaults(fn=cmd_verify)

    s = sub.add_parser("scan", help="list candidate centres by buildings and relief")
    s.add_argument("--raw", default=str(DEFAULT_RAW))
    s.add_argument("--kind", choices=("rural", "urban"), default="rural")
    s.add_argument("--half", type=float, default=2000.0, help="half extent in metres")
    s.add_argument("--step", type=float, default=500.0)
    s.add_argument("--top", type=int, default=15)
    s.add_argument("--min-buildings", type=int, default=40)
    s.add_argument("--max-buildings", type=int, default=150)
    s.add_argument("--around-lat", type=float)
    s.add_argument("--around-lon", type=float)
    s.add_argument("--max-km", type=float, default=15.0)
    s.set_defaults(fn=cmd_scan)

    args = ap.parse_args(argv)
    return int(args.fn(args))
