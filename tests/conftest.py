"""Shared helpers for the pipeline tests. Fixtures are small and synthetic (CLAUDE.md); real catalogs live only in the
gitignored cache/ and are read by test_acceptance.py, which skips without them."""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
FIXTURES = Path(__file__).resolve().parent / 'fixtures'
sys.path.insert(0, str(TOOLS))

# The judge's metrics of a clean hologram (holo_mesh.METRIC_KEYS), for holo release fixtures.
CLEAN = {'errorM': 0.0, 'topIou': 1.0, 'sideIou': 1.0, 'frontIou': 1.0, 'topHausdorff': 0.0, 'sideHausdorff': 0.0,
         'frontHausdorff': 0.0, 'edgeFscore': 1.0, 'holeRatio': 1.0, 'windingShare': 0.0, 'sliverShare': 0.0}

needs_pwsh = pytest.mark.skipif(shutil.which('pwsh') is None, reason='pwsh not on PATH (runs in WSL and on the runner)')


def write_json(path: Path, doc: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding='utf-8', newline='\n')
    return path


def grid(name: str, size: list[int], at: list[float], max_scu: int = 4, transform: bool = True) -> dict:
    """A catalog grid, translation only (identity rotation), as Motherlode's API names the fields."""
    t = [1, 0, 0, at[0], 0, 1, 0, at[1], 0, 0, 1, at[2]] if transform else None
    return {'name': name, 'scu': size[0] * size[1] * size[2], 'size': size, 'containerSizes': [1, 2, 4],
            'maxContainerScu': max_scu, 'external': False, 'transform': t}


def ship(name: str, class_name: str | None, grids: list[dict], manufacturer: str = 'TEST', sid: int = 1) -> dict:
    return {'id': sid, 'className': class_name, 'name': name, 'manufacturer': manufacturer,
            'cargoScu': sum(g['scu'] for g in grids), 'containerSizes': [1, 2, 4], 'grids': grids}


def catalog(ships: list[dict], updated: str = '2026-11-12T20:50:33.036Z', build: str = '4.10.3-LIVE.13165946') -> dict:
    return {'gameBuild': build, 'updatedAt': updated, 'ships': ships}
