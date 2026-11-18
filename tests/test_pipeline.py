"""The five stages end to end through run.py, with the real import (pwsh) and no models: seed -> fetch (saved answers) ->
diff -> build -> verify -> release --dry-run. Checks the hand-overs in work/, not the hologram chain (test_acceptance.py)."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from conftest import CLEAN, TOOLS, catalog, grid, needs_pwsh, ship, write_json
from shipdata import importer, stages

OUTLINES = {'schemaVersion': 1, 'generatedAt': '2026-11-16T13:50:01Z', 'dataVersion': 'holo-v3', 'ships': [
    {'slug': 'test-a', 'className': 'TEST_A', 'lengthM': 10, 'beamM': 5, 'heightM': 3, 'floorM': -2.5, 'outline': [[0, 0], [1, 0], [1, 1]]},
    {'slug': 'test-gone', 'className': 'TEST_G', 'lengthM': 10, 'beamM': 5, 'heightM': 3, 'floorM': -2.5, 'outline': [[0, 0], [1, 0], [1, 1]]}]}
ALPHA = ship('Alpha', 'TEST_A', [grid('a', [2, 2, 1], [0.3, 0, 0])])
GONE = ship('Gone', 'TEST_G', [grid('g', [2, 2, 2], [0, 0, 0])], sid=2)


def run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, '-I', str(TOOLS / 'run.py'), '--root', str(root), *args], capture_output=True, text=True)


def setup(tmp: Path) -> Path:
    """An 'app' whose ship files the import itself wrote from the first catalog, and a holo release for its two models."""
    app = tmp / 'app'
    (app / 'ships').mkdir(parents=True)
    (app / 'outlines').mkdir()
    # Written by outlines-v2 itself (no model rebuilt, both entries kept), as v0.5.1's file was.
    (tmp / 'empty-map.csv').write_text('id,className,modelKey,sx,sy,sz\n', encoding='utf-8')
    subprocess.run([sys.executable, '-I', str(TOOLS / 'holo_mesh.py'), 'outlines-v2', str(tmp / 'empty-map.csv'),
                    str(write_json(tmp / 'raw-outlines.json', OUTLINES)), str(app / 'outlines' / 'ship-outlines.json'),
                    OUTLINES['generatedAt'], OUTLINES['dataVersion'], 'test-a', 'test-gone'], check=True, capture_output=True)
    r = importer.run_import(write_json(tmp / 'first.json', catalog([ALPHA, GONE])), app / 'ships',
                            app / 'outlines' / 'ship-outlines.json', tmp / 'map.csv', tmp / 'r.json',
                            {'TEST_A': 'test-a', 'TEST_G': 'test-gone'})
    assert r.rc == 0, r.output
    holo = tmp / 'holo-v3'
    holo.mkdir()
    entries = []
    for slug, cls in (('test-a', 'TEST_A'), ('test-gone', 'TEST_G')):
        (holo / f'{slug}.holo').write_bytes(slug.encode())
        entries.append({'slug': slug, 'file': f'{slug}.holo', 'bytes': len(slug), 'sha256': hashlib.sha256(slug.encode()).hexdigest(),
                        'model': cls, 'rawSha256': 'a' * 64, 'budget': 20000, 'triangles': 1, 'edges': [1, 1, 1],
                        'passed': True, 'metrics': dict(CLEAN)})
    write_json(holo / 'manifest.json', {'dataVersion': 'holo-v3', 'formatVersion': 2, 'ships': entries})
    root = tmp / 'root'
    root.mkdir()
    (root / 'NOTICE.md').write_text('data notice', encoding='utf-8')
    write_json(root / 'overrides.json', {'ships': []})
    return root


@needs_pwsh
def test_a_catalog_without_changes_but_a_gone_ship_releases_with_missing_since(tmp_path: Path) -> None:
    root = setup(tmp_path)
    steps = [('release', '--seed', '--app', str(tmp_path / 'app'), '--holo', str(tmp_path / 'holo-v3'), '--out', str(tmp_path / 'seed')),
             ('fetch', '--saved', str(write_json(tmp_path / 'saved' / 'api.json', catalog([ALPHA])).parent)),
             ('diff', '--previous', str(tmp_path / 'seed')),
             ('build', '--data-version', 'holo-v3', '--generated-at', '2026-11-16T13:50:01Z'),
             ('verify', '--today', '2026-11-17'),
             ('release', '--dry-run')]
    (tmp_path / 'saved' / 'page-ships.json').write_text('[]', encoding='utf-8')
    for args in steps:
        r = run(root, *args)
        assert r.returncode == 0, f'{args[0]}: {r.stdout[-3000:]}{r.stderr[-3000:]}'
        assert 'checked:' in r.stdout and 'found:' in r.stdout and 'to do:' in r.stdout

    d = json.loads((root / 'work' / 'diff.json').read_text(encoding='utf-8'))
    assert (d['ships']['changed'], d['ships']['new'], d['ships']['gone']) == ([], [], ['gone'])
    m = json.loads((root / 'out' / 'release' / 'manifest.json').read_text(encoding='utf-8'))
    assert m['ships']['gone']['missingSince'] == '2026-11-17'
    assert m['builtFrom']['motherlode']['gameBuild'] == '4.10.3-LIVE.13165946'
    # Nothing changed but the gone ship's state: every ship file and the outlines byte-equal to the seed.
    for rel in ('ships/alpha.json', 'ships/gone.json', 'outlines.json', 'holo/test-a.holo'):
        assert (root / 'out' / 'release' / rel).read_bytes() == (tmp_path / 'seed' / rel).read_bytes(), rel
    assert (root / 'out' / 'release' / 'NOTICE.md').read_text(encoding='utf-8') == 'data notice'


@needs_pwsh
def test_a_grid_without_transform_and_no_override_goes_to_the_pr_path(tmp_path: Path) -> None:
    root = setup(tmp_path)
    kept = ship('Kept', None, [grid('k', [2, 2, 1], [0, 0, 0], transform=False)], sid=3)
    (tmp_path / 'saved').mkdir()
    (tmp_path / 'saved' / 'page-ships.json').write_text('[]', encoding='utf-8')
    write_json(tmp_path / 'saved' / 'api.json', catalog([ALPHA, GONE, kept]))
    assert run(root, 'release', '--seed', '--app', str(tmp_path / 'app'), '--holo', str(tmp_path / 'holo-v3'), '--out', str(tmp_path / 'seed')).returncode == 0
    for args in (('fetch', '--saved', str(tmp_path / 'saved')), ('diff', '--previous', str(tmp_path / 'seed')), ('build',)):
        assert run(root, *args).returncode == 0
    r = run(root, 'verify')
    assert r.returncode == 2, r.stdout[-2000:]
    proposed = json.loads((root / 'work' / 'overrides-proposed.json').read_text(encoding='utf-8'))
    assert [o['id'] for o in proposed['ships']] == ['kept']


def test_a_gone_variant_takes_its_base_file_with_its_own_names() -> None:
    base = '{\n  "schemaVersion": 6,\n  "id": "mole",\n  "name": "ARGO MOLE",\n  "modelKey": "argo-mole",\n  "source": "s2",\n  "totalScu": 96,\n  "racks": [1]\n}\n'
    variant = '{\n  "schemaVersion": 6,\n  "id": "mole_carbon_edition",\n  "name": "ARGO MOLE Carbon Edition",\n  "modelKey": "argo-mole",\n  "source": "s1",\n  "totalScu": 96,\n  "racks": [0]\n}\n'
    out = stages.follow_base(variant, base)
    assert out == base.replace('"id": "mole"', '"id": "mole_carbon_edition"').replace('"name": "ARGO MOLE"', '"name": "ARGO MOLE Carbon Edition"')
