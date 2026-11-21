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


# ---------------------------------------------------------------- hauling (H1): raw contracts and starmap entries as
# StarCitizenWiki/scunpacked-data writes them (contracts/<uuid>.json, starmap_positions.json), cut down to the fields read

def order(name: str = 'Quartz', lo: int = 6, hi: int = 12, box: int = 4, kind: str = 'Resource') -> dict:
    return {'Kind': kind, 'UUID': '0' * 8, 'Name': name, 'MinAmount': 0, 'MaxAmount': 0, 'MaxContainerSize': box,
            'MinScu': lo, 'MaxScu': hi}


def contract(uuid: str = 'u1', debug: str = 'HaulCargo_AToB_RefinedOre_Quartz_Stanton1_SmallGrade',
             title: str = 'Rookie Rank - Direct Extra Small Cargo Haul', giver: str = 'Covalex Independent Contractors',
             mission: str = 'Hauling - Stellar', reward: int | None = 50250, orders: list[dict] | None = None,
             pickup: list[str] | None = None, dropoff: list[str] | None = None, released: bool = True,
             tokens: dict | None = None) -> dict:
    t = dict(tokens or {})
    if pickup is not None:
        t['Location|Address'] = pickup
    if dropoff is not None:
        t['Destination|Address'] = dropoff
    return {'UUID': uuid, 'DebugName': debug, 'DisplayTitle': title, 'Title': '~mission(ReputationRank) Rank',
            'NotForRelease': not released, 'WorkInProgress': False, 'MissionGiver': giver,
            'MissionType': {'UUID': 'x', 'Name': mission},
            'FixedReward': None if reward is None else {'Amount': reward, 'Max': 0, 'BonusEligible': False, 'Currency': 'UEC'},
            'HaulingOrders': [order()] if orders is None else orders, 'MissionTokens': t}


def entity(name: str, system: str = 'stanton', type_: str = 'Manmade_VisibleOnInteraction', uuid: str | None = None,
           parent: str | None = None, hidden: bool = False, at: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> dict:
    return {'uuid': uuid or f'id-{name}', 'name': name, 'type': type_, 'system': system, 'parent_uuid': parent,
            'hidden': hidden, 'qt_valid': True, 'x': at[0], 'y': at[1], 'z': at[2]}


def starmap(*entities: dict) -> dict:
    return {'entities': list(entities), 'connections': []}
