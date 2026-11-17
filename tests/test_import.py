"""tools/import-motherlode.ps1 as this repo changes it (plan T12.1, P6): the date stays the API's string, -Create takes
modelKey from the key map, a never-seen className gets a derived key, no anchors at the racks' middle, a machine-readable
report. The rest of the import is tested in the app repo (ImportMotherlodeScriptTests.cs) until T12.5."""
import json
import shutil
from pathlib import Path

from conftest import FIXTURES, catalog, grid, needs_pwsh, ship, write_json
from shipdata import importer

OUTLINES = {'schemaVersion': 1, 'generatedAt': 'x', 'dataVersion': 'x', 'ships': [
    {'slug': 'test-known', 'lengthM': 10, 'beamM': 5, 'heightM': 3, 'floorM': -2.5, 'outline': [[0, 0], [1, 0], [1, 1]]},
    {'slug': 'test-fresh', 'lengthM': 10, 'beamM': 5, 'heightM': 3, 'floorM': -1.25, 'outline': [[0, 0], [1, 0], [1, 1]]}]}


def run(tmp: Path, cat: dict, key_map: dict[str, str] | None = None, outlines: dict | None = None,
        ships: dict[str, Path] | None = None) -> importer.ImportResult:
    folder = tmp / 'ships'
    folder.mkdir(exist_ok=True)
    for sid, src in (ships or {}).items():
        shutil.copyfile(src, folder / f'{sid}.json')
    return importer.run_import(write_json(tmp / 'catalog.json', cat), folder, write_json(tmp / 'outlines.json', outlines or OUTLINES),
                               tmp / 'map.csv', tmp / 'report.json', key_map or {}, create=True)


@needs_pwsh
def test_source_keeps_the_api_date_string(tmp_path: Path) -> None:
    r = run(tmp_path, catalog([ship('Known', 'TEST_Known', [grid('a', [2, 2, 1], [0, 0, 0])])]), {'TEST_Known': 'test-known'})
    text = (tmp_path / 'ships' / 'known.json').read_text(encoding='utf-8')
    assert '"source": "cryon.rocks (Motherlode) 4.10.3-LIVE.13165946, 2026-11-12T20:50:33.036Z",' in text, r.output


@needs_pwsh
def test_create_takes_model_key_from_the_key_map(tmp_path: Path) -> None:
    """An older key that the className does not give (as crus-mercury-star-runner for CRUS_Star_Runner) stays."""
    run(tmp_path, catalog([ship('Known', 'TEST_Known', [grid('a', [2, 2, 1], [0, 0, 0])])]), {'TEST_Known': 'test-legacy-key'})
    assert json.loads((tmp_path / 'ships' / 'known.json').read_text(encoding='utf-8'))['modelKey'] == 'test-legacy-key'


@needs_pwsh
def test_a_never_seen_class_name_gets_a_derived_key_and_anchors_from_the_model(tmp_path: Path) -> None:
    run(tmp_path, catalog([ship('Fresh', 'TEST_Fresh', [grid('a', [2, 2, 1], [0.3, 0, 0])])]))
    doc = json.loads((tmp_path / 'ships' / 'fresh.json').read_text(encoding='utf-8'))
    assert doc['modelKey'] == 'test-fresh'
    # Anchors from the model: holoOrigin = s, outlineOrigin.z = s.z + floorM / 1.25 (= -1); never the racks' middle.
    assert doc['outlineOrigin'][2] == doc['holoOrigin'][2] - 1
    assert doc['holoOrigin'] != [1, 1, 0.5]


@needs_pwsh
def test_a_new_ship_without_a_floor_is_written_without_anchors_and_reported(tmp_path: Path) -> None:
    r = run(tmp_path, catalog([ship('Other', 'TEST_Other', [grid('a', [2, 2, 1], [0, 0, 0])])]))
    doc = json.loads((tmp_path / 'ships' / 'other.json').read_text(encoding='utf-8'))
    assert 'holoOrigin' not in doc and 'outlineOrigin' not in doc
    entry = r.by_id['other']
    assert (entry['status'], entry['anchorsKept'], entry['modelKey']) == ('created', True, 'test-other')


@needs_pwsh
def test_a_new_ship_without_a_model_is_not_written(tmp_path: Path) -> None:
    r = run(tmp_path, catalog([ship('Nomodel', None, [grid('a', [2, 2, 1], [0, 0, 0])])]))
    assert not (tmp_path / 'ships' / 'nomodel.json').exists()
    assert r.by_id['nomodel']['status'] == 'new'


@needs_pwsh
def test_the_report_names_overlap_and_a_grid_without_transform(tmp_path: Path) -> None:
    over = json.loads((FIXTURES / 'import' / 'overlap.json').read_text(encoding='utf-8'))['ships'][0]
    kept = ship('Kept', None, [grid('a', [2, 2, 1], [0, 0, 0], transform=False)], sid=2)
    r = run(tmp_path, catalog([over, kept]), ships={'overlap_ship': FIXTURES / 'import' / 'ships' / 'overlap_ship.json'})
    assert r.rc == 1
    assert r.by_id['overlap_ship']['status'] == 'handcheck'
    assert 'grids overlap' in r.by_id['overlap_ship']['detail']
    assert r.by_id['kept']['status'] == 'kept'


@needs_pwsh
def test_a_ship_file_not_in_the_catalog_is_reported_absent(tmp_path: Path) -> None:
    r = run(tmp_path, catalog([ship('Known', 'TEST_Known', [grid('a', [2, 2, 1], [0, 0, 0])])]), {'TEST_Known': 'test-known'},
            ships={'overlap_ship': FIXTURES / 'import' / 'ships' / 'overlap_ship.json'})
    assert r.by_id['overlap_ship']['status'] == 'absent'
