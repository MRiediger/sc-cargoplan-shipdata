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
    # The saved answers of the catalog the app was built from: the seed takes its orderKeys from them (--catalog).
    write_json(tmp / 'first' / 'api.json', catalog([ALPHA, GONE]))
    (tmp / 'first' / 'page-ships.json').write_text('[]', encoding='utf-8')
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
    steps = [('release', '--seed', '--app', str(tmp_path / 'app'), '--holo', str(tmp_path / 'holo-v3'), '--catalog', str(tmp_path / 'first'), '--out', str(tmp_path / 'seed')),
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

    seed = json.loads((tmp_path / 'seed' / 'manifest.json').read_text(encoding='utf-8'))
    assert seed['ships']['alpha']['orderKeys'] == ['2x2x1@0.3,0.0,0.0']
    d = json.loads((root / 'work' / 'diff.json').read_text(encoding='utf-8'))
    assert (d['ships']['changed'], d['ships']['new'], d['ships']['gone']) == ([], [], ['gone'])
    assert (d['order'], d['orderNotCompared']) == ({'compared': 1, 'changed': []}, [])
    m = json.loads((root / 'out' / 'release' / 'manifest.json').read_text(encoding='utf-8'))
    assert m['ships']['gone']['missingSince'] == '2026-11-17'
    assert m['builtFrom']['motherlode']['gameBuild'] == '4.10.3-LIVE.13165946'
    # Nothing changed but the gone ship's state: ships.zip (every ship file and the outlines) and the holograms are the
    # seed's bytes; the release folder holds the flat assets only (SD4).
    rel = root / 'out' / 'release'
    assert sorted(q.name for q in rel.iterdir()) == ['NOTICE.md', 'manifest.json', 'ships.zip', 'test-a.holo', 'test-gone.holo']
    for name in ('ships.zip', 'test-a.holo', 'test-gone.holo'):
        assert (rel / name).read_bytes() == (tmp_path / 'seed' / name).read_bytes(), name
    assert (rel / 'NOTICE.md').read_text(encoding='utf-8') == 'data notice'

    # diff --previous reads manifest.json and ships.zip only: the same numbers without the holograms.
    bare = tmp_path / 'bare'
    bare.mkdir()
    for name in ('manifest.json', 'ships.zip'):
        (bare / name).write_bytes((rel / name).read_bytes())
    r = run(root, 'diff', '--previous', str(bare))
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    d = json.loads((root / 'work' / 'diff.json').read_text(encoding='utf-8'))
    # The release already has missingSince for the gone ship: gone before, not newly gone (D2) - nothing changed.
    assert (d['ships']['changed'], d['ships']['new'], d['ships']['gone'], d['ships']['stillGone'], d['ships']['same']) == \
           ([], [], [], ['gone'], ['alpha'])
    assert d['nothingChanged'] is True


@needs_pwsh
def test_a_gone_ship_back_in_the_catalog_loses_missing_since(tmp_path: Path) -> None:
    """SD6 "back": run 1 misses the ship (missingSince), run 2 against run 1's release finds it again (null)."""
    root = setup(tmp_path)
    (tmp_path / 'saved').mkdir()
    (tmp_path / 'saved' / 'page-ships.json').write_text('[]', encoding='utf-8')
    (tmp_path / 'back').mkdir()
    (tmp_path / 'back' / 'page-ships.json').write_text('[]', encoding='utf-8')
    write_json(tmp_path / 'saved' / 'api.json', catalog([ALPHA]))
    write_json(tmp_path / 'back' / 'api.json', catalog([ALPHA, GONE]))
    first = run(root, 'release', '--seed', '--app', str(tmp_path / 'app'), '--holo', str(tmp_path / 'holo-v3'), '--catalog', str(tmp_path / 'first'), '--out', str(tmp_path / 'seed'))
    assert first.returncode == 0, first.stdout[-2000:] + first.stderr[-2000:]
    for saved, previous, today in (('saved', tmp_path / 'seed', '2026-11-17'), ('back', tmp_path / 'run1', '2026-12-01')):
        for args in (('fetch', '--saved', str(tmp_path / saved)), ('diff', '--previous', str(previous)),
                     ('build', '--data-version', 'holo-v3', '--generated-at', '2026-11-16T13:50:01Z'),
                     ('verify', '--today', today), ('release', '--dry-run')):
            r = run(root, *args)
            assert r.returncode == 0, f'{saved} {args[0]}: {r.stdout[-3000:]}{r.stderr[-3000:]}'
        if saved == 'saved':
            assert json.loads((root / 'out' / 'release' / 'manifest.json').read_text(encoding='utf-8'))['ships']['gone']['missingSince'] == '2026-11-17'
            (root / 'out' / 'release').rename(tmp_path / 'run1')
    m = json.loads((root / 'out' / 'release' / 'manifest.json').read_text(encoding='utf-8'))
    assert (m['ships']['gone']['missingSince'], m['ships']['gone']['follows']) == (None, None)
    found = json.loads((root / 'work' / 'verify.json').read_text(encoding='utf-8'))['findings']
    assert [(f['rule'], f['id'], f['stop']) for f in found if f['rule'] == 'back'] == [('back', 'gone', False)]


@needs_pwsh
def test_a_grid_without_transform_and_no_override_goes_to_the_pr_path(tmp_path: Path) -> None:
    root = setup(tmp_path)
    kept = ship('Kept', None, [grid('k', [2, 2, 1], [0, 0, 0], transform=False)], sid=3)
    (tmp_path / 'saved').mkdir()
    (tmp_path / 'saved' / 'page-ships.json').write_text('[]', encoding='utf-8')
    write_json(tmp_path / 'saved' / 'api.json', catalog([ALPHA, GONE, kept]))
    assert run(root, 'release', '--seed', '--app', str(tmp_path / 'app'), '--holo', str(tmp_path / 'holo-v3'), '--catalog', str(tmp_path / 'first'), '--out', str(tmp_path / 'seed')).returncode == 0
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


@needs_pwsh
def test_a_ship_gone_since_the_last_release_is_no_change(tmp_path: Path, monkeypatch) -> None:
    """D2: run 1 misses the ship (missingSince), run 2 with the same catalog against run 1's release: nothing changed,
    the ship counts as still gone, and verify keeps the date of the first miss. diff tells the workflow (P7)."""
    out = tmp_path / 'github-output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(out))
    root = setup(tmp_path)
    (tmp_path / 'saved').mkdir()
    (tmp_path / 'saved' / 'page-ships.json').write_text('[]', encoding='utf-8')
    write_json(tmp_path / 'saved' / 'api.json', catalog([ALPHA]))
    first = run(root, 'release', '--seed', '--app', str(tmp_path / 'app'), '--holo', str(tmp_path / 'holo-v3'), '--catalog', str(tmp_path / 'first'), '--out', str(tmp_path / 'seed'))
    assert first.returncode == 0, first.stdout[-2000:] + first.stderr[-2000:]
    for previous, today in ((tmp_path / 'seed', '2026-11-17'), (tmp_path / 'run1', '2026-12-01')):
        for args in (('fetch', '--saved', str(tmp_path / 'saved')), ('diff', '--previous', str(previous)),
                     ('build', '--data-version', 'holo-v3', '--generated-at', '2026-11-16T13:50:01Z'),
                     ('verify', '--today', today), ('release', '--dry-run')):
            r = run(root, *args)
            assert r.returncode == 0, f'{args[0]}: {r.stdout[-3000:]}{r.stderr[-3000:]}'
        d = json.loads((root / 'work' / 'diff.json').read_text(encoding='utf-8'))
        if previous.name == 'seed':
            assert (d['ships']['gone'], d['ships']['stillGone'], d['nothingChanged']) == (['gone'], [], False)
            (root / 'out' / 'release').rename(tmp_path / 'run1')
    assert (d['ships']['gone'], d['ships']['stillGone'], d['nothingChanged']) == ([], ['gone'], True)
    changed = [line for line in out.read_text(encoding='utf-8').splitlines() if line.startswith('changed=')]
    assert changed == ['changed=true', 'changed=false']
    m = json.loads((root / 'out' / 'release' / 'manifest.json').read_text(encoding='utf-8'))
    assert m['ships']['gone']['missingSince'] == '2026-11-17'
