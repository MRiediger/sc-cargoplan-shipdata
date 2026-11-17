"""fetch: catalog from saved or live answers (one API call), model URLs from the page, models by SHA into the cache.
No network here: the model GET is injected."""
import hashlib
import json
from pathlib import Path

import pytest

from conftest import catalog, grid, ship, write_json
from shipdata import fetch

BODY = b'glTF model bytes'
H12 = hashlib.sha256(BODY).hexdigest()[:12]
BASE = 'https://example.supabase.co/storage/v1/object/public/ship-models/'
PAGE = ('0:junk\n1:{"props":{"ships":[{"id":1,"name":"Alpha [A]","modelUrl":"' + BASE + 'TEST_A-' + H12 + '.glb",'
        '"note":"a ] bracket and a \\" quote"},{"id":7,"name":"Gamma","modelUrl":"' + BASE + 'TEST_G-ba9876543210.glb"}]}}\n')
API = catalog([ship('Alpha', 'TEST_A', [grid('a', [2, 2, 1], [0, 0, 0])]),
               ship('Beta', None, [grid('b', [2, 2, 1], [0, 0, 0])], sid=2)])


def test_the_ships_array_is_cut_by_counting_brackets_outside_strings() -> None:
    ships = json.loads(fetch.ships_array_text(PAGE))
    assert [s['id'] for s in ships] == [1, 7]
    assert ships[0]['note'] == 'a ] bracket and a " quote'


def test_a_page_without_ships_array_is_a_clear_error() -> None:
    with pytest.raises(fetch.SourceError, match='page format changed'):
        fetch.ships_array_text('0:{"props":{}}')


def test_the_catalog_joins_model_urls_by_class_name() -> None:
    cat, notes = fetch.join(API, json.loads(fetch.ships_array_text(PAGE)))
    alpha, beta = cat['ships']
    assert alpha['modelUrl'] == f'{BASE}TEST_A-{H12}.glb'
    assert 'modelUrl' not in beta
    assert (cat['gameBuild'], cat['updatedAt']) == (API['gameBuild'], API['updatedAt'])
    assert any('TEST_G' in n for n in notes)            # a model on the page without an API ship is named


@pytest.mark.parametrize('broken, message', [
    ({'gameBuild': 'latest'}, 'gameBuild'),
    ({'updatedAt': ''}, 'updatedAt'),
    ({'ships': []}, 'no ships'),
])
def test_an_api_answer_out_of_format_stops_before_anything_is_written(broken: dict, message: str) -> None:
    with pytest.raises(fetch.SourceError, match=message):
        fetch.check_api(dict(API, **broken))


def test_a_transform_without_twelve_values_stops() -> None:
    bad = catalog([ship('Alpha', 'TEST_A', [dict(grid('a', [2, 2, 1], [0, 0, 0]), transform=[1, 0, 0])])])
    with pytest.raises(fetch.SourceError, match='12 values'):
        fetch.check_api(bad)


def test_saved_answers_read_the_page_as_stream_or_as_array(tmp_path: Path) -> None:
    write_json(tmp_path / 'a' / 'api.json', API)
    (tmp_path / 'a' / 'page.txt').write_text(PAGE, encoding='utf-8')
    write_json(tmp_path / 'b' / 'api.json', API)
    (tmp_path / 'b' / 'page-ships.json').write_text(fetch.ships_array_text(PAGE), encoding='utf-8')
    assert fetch.load_saved(tmp_path / 'a')[1] == fetch.load_saved(tmp_path / 'b')[1]


def test_no_api_key_is_a_clear_error_without_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('MOTHERLODE_API_KEY', raising=False)
    with pytest.raises(fetch.SourceError, match='MOTHERLODE_API_KEY'):
        fetch.api_key()


def models(tmp_path: Path, answers: dict[str, tuple[int, bytes]]) -> tuple[dict, list[str]]:
    asked: list[str] = []

    def get(url: str) -> tuple[int, bytes]:
        asked.append(url)
        return answers[url.rsplit('/', 1)[-1]]

    cat, _ = fetch.join(catalog([ship('Alpha', 'TEST_A', [grid('a', [2, 2, 1], [0, 0, 0])]),
                                 ship('Gone', 'TEST_G', [grid('b', [2, 2, 1], [0, 0, 0])], sid=7)]),
                        json.loads(fetch.ships_array_text(PAGE)))
    return fetch.fetch_models(cat, tmp_path / 'models', get, pause=0), asked


def test_a_model_answering_404_is_unavailable_and_the_others_still_load(tmp_path: Path) -> None:
    got, asked = models(tmp_path, {f'TEST_A-{H12}.glb': (200, BODY), 'TEST_G-ba9876543210.glb': (404, b'')})
    assert got['TEST_A']['status'] == 'fetched'
    assert (got['TEST_G']['status'], got['TEST_G']['http'], got['TEST_G']['reason']) == ('unavailable', 404, 'HTTP 404')
    assert len(asked) == 2
    assert (tmp_path / 'models' / f'TEST_A-{H12}.glb').read_bytes() == BODY


def test_a_model_whose_bytes_do_not_match_its_hash_is_unavailable(tmp_path: Path) -> None:
    got, _ = models(tmp_path, {f'TEST_A-{H12}.glb': (200, b'something else'), 'TEST_G-ba9876543210.glb': (404, b'')})
    assert got['TEST_A']['status'] == 'unavailable'
    assert not (tmp_path / 'models' / f'TEST_A-{H12}.glb').exists()


def test_a_cached_model_is_not_asked_again(tmp_path: Path) -> None:
    (tmp_path / 'models').mkdir()
    (tmp_path / 'models' / f'TEST_A-{H12}.glb').write_bytes(BODY)
    got, asked = models(tmp_path, {'TEST_G-ba9876543210.glb': (404, b'')})
    assert got['TEST_A']['status'] == 'cached'
    assert [a.rsplit('/', 1)[-1] for a in asked] == ['TEST_G-ba9876543210.glb']


def test_fetch_never_deletes_an_older_model_of_the_same_class(tmp_path: Path) -> None:
    """Rule 'double model' (condition B): the old hash stays until release has published the new hologram."""
    (tmp_path / 'models').mkdir()
    old = tmp_path / 'models' / 'TEST_A-000000000000.glb'
    old.write_bytes(b'old')
    models(tmp_path, {f'TEST_A-{H12}.glb': (200, BODY), 'TEST_G-ba9876543210.glb': (404, b'')})
    assert old.exists()


def test_prune_keeps_the_current_hash_and_removes_older_ones_of_that_class(tmp_path: Path) -> None:
    d = tmp_path / 'models'
    d.mkdir()
    for name in ('TEST_A-000000000000.glb', f'TEST_A-{H12}.glb', 'TEST_B-111111111111.glb'):
        (d / name).write_bytes(b'x')
    removed = fetch.prune_models(d, {f'TEST_A-{H12}.glb', 'TEST_B-111111111111.glb'})
    assert removed == ['TEST_A-000000000000.glb']
    assert sorted(p.name for p in d.iterdir()) == sorted([f'TEST_A-{H12}.glb', 'TEST_B-111111111111.glb'])
