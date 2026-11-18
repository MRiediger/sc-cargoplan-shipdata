"""The render gate (SD3, P3, P5): the old and the new release rendered with the same app in one job, hash-exact; only
ships whose data changed (without stamps) may differ. ShipPictureTests and dotnet are replaced by a fake that renders
from bin/ships and the hologram folder the way the app does, so the gate's own logic runs without Windows."""
import hashlib
import json
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from conftest import CLEAN
from shipdata import gate, github, manifest, release, sheet, stages
from shipdata.log import Reporter
from test_workflow_stages import FakeGitHub, paths

SHIP = {'schemaVersion': 6, 'id': 'a', 'name': 'A', 'modelKey': 'test-a', 'source': 'cryon.rocks (Motherlode) 4.10.3-LIVE.1, 2026-11-12',
        'totalScu': 4, 'racks': [{'id': 'rack-0', 'origin': [0, 0, 0]}]}
OUTLINES = {'schemaVersion': 1, 'generatedAt': '2026-11-16T13:50:01Z', 'dataVersion': 'holo-v3',
            'ships': [{'slug': 'test-a', 'outline': [[0, 0]]}, {'slug': 'test-b', 'outline': [[0, 0]]}]}


def ship_doc(sid: str, **kw: object) -> dict:
    return dict(SHIP, id=sid, modelKey=f'test-{sid}', **kw)


def make_release(folder: Path, version: str, ships: dict[str, dict], holos: dict[str, bytes], outlines: dict = OUTLINES) -> Path:
    """Flat release assets (SD4) with a manifest that manifest.read accepts."""
    folder.mkdir(parents=True)
    files = {f'ships/{sid}.json': json.dumps(doc, indent=2).encode() for sid, doc in ships.items()}
    files['outlines.json'] = json.dumps(outlines).encode()
    with zipfile.ZipFile(folder / 'ships.zip', 'w') as z:
        for rel, data in sorted(files.items()):
            z.writestr(rel, data)
    holo = {}
    for slug, data in holos.items():
        (folder / f'{slug}.holo').write_bytes(data)
        holo[slug] = {'file': f'{slug}.holo', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'model': 'TEST',
                      'rawSha256': 'a' * 64, 'budget': 20000, 'triangles': 1, 'edges': [1, 1, 1], 'passed': True, 'fails': [],
                      'metrics': dict(CLEAN)}
    (folder / 'NOTICE.md').write_text('notice', encoding='utf-8')
    manifest.write(folder / 'manifest.json', {
        'dataVersion': version, 'schemaVersion': 6, 'generatedAt': 'x', 'builtFrom': {}, 'assets': {'ships': 'ships.zip'},
        'files': {rel: hashlib.sha256(data).hexdigest() for rel, data in files.items()},
        'holo': {'formatVersion': 2, 'ships': holo},
        'ships': {sid: {'source': d.get('source'), 'modelKey': d.get('modelKey'), 'racksSha256': 'x', 'orderKeys': None,
                        'missingSince': None, 'follows': None} for sid, d in ships.items()}})
    return folder


OLD_SHIPS = {'a': ship_doc('a'), 'b': ship_doc('b')}
OLD_HOLOS = {'test-a': b'holo a', 'test-b': b'holo b'}


# ---------------------------------------------------------------- expected ships

def unpacked(tmp: Path, name: str, ships: dict, holos: dict, outlines: dict = OUTLINES) -> tuple[dict, Path]:
    folder = make_release(tmp / name, 'ships-2026.11', ships, holos, outlines)
    return release.unpack(folder, tmp / f'{name}-data'), tmp / f'{name}-data'


def test_a_new_source_alone_expects_no_ship(tmp_path: Path) -> None:
    """A new catalog date changes source in every file: compared by bytes, every ship would be 'expected' and the gate
    would check nothing."""
    om, od = unpacked(tmp_path, 'old', OLD_SHIPS, OLD_HOLOS)
    nm, nd = unpacked(tmp_path, 'new', {s: dict(d, source='cryon.rocks (Motherlode) 4.10.3-LIVE.1, 2026-11-17') for s, d in OLD_SHIPS.items()},
                      OLD_HOLOS)
    assert gate.expected_ids(om, nm, od, nd) == []


def test_changed_racks_holo_outline_and_new_ships_are_expected(tmp_path: Path) -> None:
    om, od = unpacked(tmp_path, 'old', {**OLD_SHIPS, 'c': ship_doc('c'), 'd': ship_doc('d')},
                      {**OLD_HOLOS, 'test-c': b'c', 'test-d': b'd'},
                      dict(OUTLINES, ships=OUTLINES['ships'] + [{'slug': 'test-c', 'outline': [[0, 0]]}, {'slug': 'test-d', 'outline': [[0, 0]]}]))
    moved = ship_doc('a', racks=[{'id': 'rack-0', 'origin': [1, 0, 0]}])
    nm, nd = unpacked(tmp_path, 'new', {'a': moved, 'b': ship_doc('b'), 'c': ship_doc('c'), 'd': ship_doc('d'), 'e': ship_doc('e')},
                      {**OLD_HOLOS, 'test-b': b'refreshed', 'test-c': b'c', 'test-d': b'd', 'test-e': b'e'},
                      dict(OUTLINES, ships=OUTLINES['ships'] + [{'slug': 'test-c', 'outline': [[1, 1]]}, {'slug': 'test-d', 'outline': [[0, 0]]}]))
    assert gate.expected_ids(om, nm, od, nd) == ['a', 'b', 'c', 'e']       # racks, holo, outline, new; d unchanged


def test_ships_sharing_a_model_key_are_all_expected(tmp_path: Path) -> None:
    om, od = unpacked(tmp_path, 'old', {**OLD_SHIPS, 'a2': dict(ship_doc('a2'), modelKey='test-a')}, OLD_HOLOS)
    nm, nd = unpacked(tmp_path, 'new', {**OLD_SHIPS, 'a2': dict(ship_doc('a2'), modelKey='test-a')}, {**OLD_HOLOS, 'test-a': b'new'})
    assert gate.expected_ids(om, nm, od, nd) == ['a', 'a2']


def with_module(data: Path, module: dict) -> None:
    (data / 'ships' / 'modules').mkdir(exist_ok=True)
    (data / 'ships' / 'modules' / f"{module['id']}.json").write_text(json.dumps(module), encoding='utf-8')


MODULE = {'schemaVersion': 1, 'id': 'ts_module', 'name': 'TS module', 'ships': ['a', 'b'], 'source': 'in game',
          'racks': [{'id': 'ts-module', 'origin': [-7, -1, 0]}]}


def test_a_module_entry_follows_its_base_ship(tmp_path: Path) -> None:
    """Found by the local gate of 18 Nov: the app builds aurora_mk_ii_ts_module from aurora_mk_ii and
    modules/ts_module.json (ModuleDto.ConfigurationId: <ship>_<module>); it renders with the base's hologram, so it may
    differ whenever its base may."""
    om, od = unpacked(tmp_path, 'old', OLD_SHIPS, OLD_HOLOS)
    nm, nd = unpacked(tmp_path, 'new', OLD_SHIPS, {**OLD_HOLOS, 'test-a': b'refreshed a'})
    for d in (od, nd):
        with_module(d, MODULE)
    assert gate.expected_ids(om, nm, od, nd) == ['a', 'a_ts_module']


def test_a_changed_module_is_expected_on_every_ship_it_names(tmp_path: Path) -> None:
    om, od = unpacked(tmp_path, 'old', OLD_SHIPS, OLD_HOLOS)
    nm, nd = unpacked(tmp_path, 'new', OLD_SHIPS, OLD_HOLOS)
    with_module(od, MODULE)
    with_module(nd, dict(MODULE, racks=[{'id': 'ts-module', 'origin': [-6, -1, 0]}]))
    assert gate.expected_ids(om, nm, od, nd) == ['a_ts_module', 'b_ts_module']
    with_module(nd, dict(MODULE, source='in game, checked again'))           # a stamp alone: nothing
    assert gate.expected_ids(om, nm, od, nd) == []


# ---------------------------------------------------------------- two picture runs compared (port of csvdiff.py)

def test_compare_runs(tmp_path: Path) -> None:
    a, b = tmp_path / 'a', tmp_path / 'b'
    for d, rows, values in ((a, ['x;holo;800x600;fit;1', 'y;holo;800x600;fit;2', 'z;holo;800x600;fit;3'], ['x;0 0 0;h']),
                            (b, ['x;holo;800x600;fit;1', 'y;holo;800x600;fit;9', 'n;holo;800x600;fit;4'], ['x;0 0 1;h'])):
        d.mkdir()
        (d / 'pictures.csv').write_text('\n'.join(rows) + '\n', encoding='utf-8')
        (d / 'values.csv').write_text('\n'.join(values) + '\n', encoding='utf-8')
    r = gate.compare_runs(a, b)
    assert (r.equal, r.different, r.missing, r.numbers) == (1, ['n;holo;800x600;fit', 'y;holo;800x600;fit'], ['z;holo;800x600;fit'], ['x'])
    assert r.ships() == ['n', 'x', 'y', 'z']
    assert gate.unexpected(r, ['n', 'y']) == ['x', 'z']


# ---------------------------------------------------------------- contact sheets (port of motherlode_sheet.py)

def png(folder: Path, name: str, value: int) -> None:
    (folder / 'png').mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(folder / 'png' / name), np.full((60, 80, 3), value, np.uint8))


def test_sheets_put_the_first_ships_first_and_six_to_a_sheet(tmp_path: Path) -> None:
    old, new = tmp_path / 'old', tmp_path / 'new'
    ships = [f's{i}' for i in range(8)]
    for s in ships:
        for view in ('fit', 'above'):
            png(old, f'{s}.holo-shaded.800x600.{view}.png', 50)
    png(new, 's7.holo-shaded.800x600.fit.png', 200)        # only what differs is saved in the run with a baseline
    made = sheet.sheets(['s7', 's1', 's2', 's3', 's4', 's5', 's6'], old, new, tmp_path / 'out', {'s7': 'UNEXPECTED'})
    assert [(q.name, ids) for q, ids in made] == [('contact-sheet-1.png', ['s7', 's1', 's2', 's3', 's4', 's5']),
                                                  ('contact-sheet-2.png', ['s6'])]
    img = cv2.imread(str(made[0][0]))
    assert img.shape[1] == 4 * sheet.TILE_W and img.shape[0] == 6 * (sheet.TILE_H + sheet.LABEL_H)
    # row 1: old default (50), new default (200, saved by the run), old above, new above (from the old run: same)
    row = img[sheet.LABEL_H + 10]
    assert [int(row[i * sheet.TILE_W + 5][0]) for i in range(4)] == [50, 200, 50, 50]


# ---------------------------------------------------------------- the gate end to end, dotnet replaced

class FakeApp:
    """dotnet build copies ships/ and outlines/ to bin (CopyToOutputDirectory IfDifferent: nothing is deleted);
    ShipPictureTests renders every ship in bin/ships with its hologram, saves every PNG without a baseline and only
    differing ones with it, and fails on a difference outside CARGOPLAN_PICTURES_EXPECTED."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (root / 'ships').mkdir(parents=True)
        (root / 'outlines').mkdir()
        (root / 'ships' / 'stale.json').write_text('{}', encoding='utf-8')        # the app's own data before the swap
        (root / 'outlines' / 'ship-outlines.json').write_text('{}', encoding='utf-8')
        self.bin = root / 'tests' / 'CargoPlan.App.Tests' / 'bin' / 'Release' / 'net10.0-windows'
        (self.bin / 'ships').mkdir(parents=True)
        (self.bin / 'ships' / 'stale.json').write_text('{}', encoding='utf-8')    # a checkout built once before
        self.builds = 0

    def build(self, app: Path, log: Path) -> None:
        self.builds += 1
        for q in (app / 'ships').rglob('*.json'):
            target = self.bin / 'ships' / q.relative_to(app / 'ships')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(q.read_bytes())
        (self.bin / 'outlines').mkdir(exist_ok=True)
        (self.bin / 'outlines' / 'ship-outlines.json').write_bytes((app / 'outlines' / 'ship-outlines.json').read_bytes())

    def pictures(self, app: Path, out: Path, holo: Path, baseline: Path | None, expected: list[str], log: Path) -> int:
        out.mkdir(parents=True, exist_ok=True)
        known = gate.read_csv(baseline / 'pictures.csv') if baseline else {}
        rows, values = [], []
        for q in sorted((self.bin / 'ships').glob('*.json')):
            doc = json.loads(q.read_text(encoding='utf-8'))
            racks = json.dumps(doc.get('racks'), sort_keys=True).encode()
            h = holo / f"{doc.get('modelKey')}.holo"
            for view in ('fit', 'above'):
                key = f"{doc['id']};holo-shaded;800x600;{view}"
                digest = hashlib.sha256(racks + (h.read_bytes() if h.exists() else b'')).hexdigest()
                rows.append(f'{key};{digest}')
                if baseline is None or known.get(key) != digest:
                    png(out, f"{key.replace(';', '.')}.png", 100)
            values.append(f"{doc['id']};0 0 0;h")
        (out / 'pictures.csv').write_text('\n'.join(rows) + '\n', encoding='utf-8')
        (out / 'values.csv').write_text('\n'.join(values) + '\n', encoding='utf-8')
        if baseline is None:
            return 0
        return 1 if gate.unexpected(gate.compare_runs(baseline, out), expected) else 0


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeApp:
    fake = FakeApp(tmp_path / 'app')
    monkeypatch.setattr(gate, 'build', fake.build)
    monkeypatch.setattr(gate, 'pictures', fake.pictures)
    return fake


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(github, 'gh', fake)
    return fake


def gate_setup(tmp: Path, gh: FakeGitHub) -> tuple[stages.Paths, Path, Path]:
    old = make_release(tmp / 'old', 'ships-2026.11', OLD_SHIPS, OLD_HOLOS)
    new = make_release(tmp / 'new', 'ships-2026.11.1', OLD_SHIPS, {**OLD_HOLOS, 'test-a': b'refreshed a'})
    gh.add('ships-2026.11.1', new, draft=True)
    return paths(tmp), old, new


def test_a_green_gate_renders_both_states_and_attaches_the_contact_sheet(app: FakeApp, gh: FakeGitHub, tmp_path: Path) -> None:
    p, old, new = gate_setup(tmp_path, gh)
    rc = gate.gate_stage(p, Reporter(p.out), app.root, old_dir=old, new_dir=new, upload_tag='ships-2026.11.1')
    assert rc == 0
    g = json.loads(p.w('gate.json').read_text(encoding='utf-8'))
    assert (g['expected'], g['unexpected'], g['pictures']) == (['a'], [], {'equal': 2, 'different': 2, 'missing': 0})
    assert app.builds == 2 and not (app.bin / 'ships' / 'stale.json').exists()      # bin holds exactly the swapped state
    assert g['sheets'] == ['contact-sheet-1.png']
    assert 'contact-sheet-1.png' in gh.releases['ships-2026.11.1']['assets']


def test_a_red_gate_still_attaches_its_contact_sheet_and_publishes_nothing(app: FakeApp, gh: FakeGitHub, tmp_path: Path,
                                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    """Martin, 18 Nov: a red gate must be visible. The contact sheet of the unexpected ships goes to the draft before
    the job ends with exit 1; nothing is published, no PR (P3)."""
    p, old, new = gate_setup(tmp_path, gh)
    monkeypatch.setattr(gate, 'expected_ids', lambda *a: [])           # a pipeline bug: 'a' changed, nobody expected it
    rc = gate.gate_stage(p, Reporter(p.out), app.root, old_dir=old, new_dir=new, upload_tag='ships-2026.11.1')
    assert rc == 1
    g = json.loads(p.w('gate.json').read_text(encoding='utf-8'))
    assert g['unexpected'] == ['a'] and g['sheets'] == ['contact-sheet-1.png']
    assert g['sheetShips'][0] == {'id': 'a', 'mark': 'UNEXPECTED'}
    assert 'contact-sheet-1.png' in gh.releases['ships-2026.11.1']['assets']
    assert gh.releases['ships-2026.11.1']['isDraft'] is True
    assert [c[1] for c in gh.calls if c[0] == 'release'] == ['upload'] and not [c for c in gh.calls if c[0] == 'pr']


def test_the_gate_refuses_a_bin_that_does_not_hold_the_swapped_state(app: FakeApp, gh: FakeGitHub, tmp_path: Path,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """S12.0 E3: ShipPictureTests reads bin/ships; a build that did not copy the new files would measure old data."""
    p, old, new = gate_setup(tmp_path, gh)
    monkeypatch.setattr(gate, 'build', lambda app_, log: None)
    with pytest.raises(gate.GateError, match='bin'):
        gate.gate_stage(p, Reporter(p.out), app.root, old_dir=old, new_dir=new, upload_tag=None)


def test_stop_ships_come_after_unexpected_and_before_the_rest(tmp_path: Path) -> None:
    runs = gate.Runs(equal=0, different=['a;x', 'b;x', 'c;x'], missing=[], numbers=[])
    m = {'ships': {'a': {'modelKey': 'test-a'}, 'b': {'modelKey': 'test-b'}, 'c': {'modelKey': 'test-c'}}}
    verify = {'findings': [{'rule': 'judge', 'id': 'test-c', 'stop': True}, {'rule': 'order', 'id': 'b', 'stop': False}]}
    assert gate.sheet_order(runs, unexpected=['b'], new_m=m, verify=verify) == [('b', 'UNEXPECTED'), ('c', 'stop'), ('a', '')]
