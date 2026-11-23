"""The app's loader checks (sc-cargoplan/docs/hauling-data-format.md, "Checks of the loader", with K2 and K3) and the
pipeline's own rules on the two files - each provoked red once (H1)."""
import copy

import pytest

from shipdata.hauling import check


def good() -> tuple[dict, dict]:
    templates = {'schemaVersion': 1, 'dataVersion': 'ships-2026.12',
                 'source': {'repository': 'StarCitizenWiki/scunpacked-data', 'commit': 'abc', 'gameBuild': '4.10.3-LIVE.1',
                            'fetchedAt': '2026-12-01T04:10:00Z'},
                 'templates': [
                     {'uuid': 'a', 'debugName': 'HaulCargo_AToB_X_Stanton1_S', 'contractor': 'covalex', 'title': 'T',
                      'rank': 'trainee', 'size': 'xs', 'direct': True, 'shape': 'aToB', 'stops': 1, 'system': 'stanton',
                      'areaKey': 'Stanton1', 'missionType': 'stellar', 'faction': None, 'reward': 1000,
                      'legs': [{'commodity': 'Quartz', 'minScu': 6, 'maxScu': 12, 'containerScu': 1}],
                      'pickupPool': ['HUR-L1'], 'dropoffPool': []},
                     {'uuid': 'b', 'debugName': 'RedWind_Pyro_X', 'contractor': 'redWind', 'title': 'T', 'rank': 'senior',
                      'size': 'bulk', 'direct': False, 'shape': 'multiToSingle', 'stops': 2, 'system': 'pyro',
                      'areaKey': 'Solar', 'missionType': 'stellar', 'faction': 'cfp', 'reward': None,
                      'legs': [{'commodity': 'Carbon', 'minScu': 400, 'maxScu': 600, 'containerScu': 32}],
                      'pickupPool': ['Checkmate', 'Stanton Gateway'], 'dropoffPool': ['Checkmate']}]}
    positions = {'schemaVersion': 1, 'dataVersion': 'ships-2026.12',
                 'source': {'repository': 'StarCitizenWiki/scunpacked-data', 'file': 'starmap_positions.json',
                            'commit': 'abc', 'fetchedAt': '2026-12-01T04:10:00Z'},
                 'positions': [
                     {'uuid': 'n1', 'name': 'Stanton Gateway', 'system': 'nyx', 'type': 'Manmade', 'parent': None,
                      'x': 1, 'y': 2, 'z': 3, 'contractNames': []},
                     {'uuid': 'p1', 'name': 'Checkmate', 'system': 'pyro', 'type': 'Manmade', 'parent': None,
                      'x': 1.5, 'y': 0, 'z': 0, 'contractNames': ['Checkmate at the L4 Lagrange of Pyro II']},
                     {'uuid': 'p2', 'name': 'Stanton Gateway', 'system': 'pyro', 'type': 'Manmade', 'parent': None,
                      'x': 0, 'y': 0, 'z': 0, 'contractNames': []},
                     {'uuid': 's1', 'name': 'HUR-L1', 'system': 'stanton', 'type': 'Manmade_VisibleOnInteraction',
                      'parent': None, 'x': 0, 'y': 0, 'z': 0, 'contractNames': []}]}
    return templates, positions


def test_good_files_pass() -> None:
    assert check.problems(*good()) == []


def broken(fn) -> list[str]:
    t, p = copy.deepcopy(good())
    fn(t, p)
    return check.problems(t, p)


@pytest.mark.parametrize('name, fn, expected', [
    ('schema of templates', lambda t, p: t.update(schemaVersion=2), 'hauling-templates.json: schemaVersion 2'),
    ('schema of positions', lambda t, p: p.update(schemaVersion=0), 'positions.json: schemaVersion 0'),
    ('name twice in a system', lambda t, p: p['positions'][3].update(name='Checkmate', system='pyro'), 'twice in pyro'),
    ('pool name without position', lambda t, p: t['templates'][0]['pickupPool'].append('Nowhere'), "'Nowhere' has no position in stanton"),
    ('pool name in another system', lambda t, p: t['templates'][0]['pickupPool'].append('Checkmate'), "'Checkmate' has no position in stanton"),
    ('no legs', lambda t, p: t['templates'][0].update(legs=[]), 'no legs'),
    ('min above max', lambda t, p: t['templates'][0]['legs'][0].update(minScu=13), 'minScu 13 > maxScu 12'),
    ('min below 1', lambda t, p: t['templates'][0]['legs'][0].update(minScu=0), 'minScu 0'),
    ('container size', lambda t, p: t['templates'][0]['legs'][0].update(containerScu=3), 'containerScu 3'),
    ('unknown rank', lambda t, p: t['templates'][0].update(rank='captain'), "rank 'captain'"),
    ('unknown size', lambda t, p: t['templates'][1].update(size='huge'), "size 'huge'"),
    ('aToB with stops', lambda t, p: t['templates'][0].update(stops=2), 'aToB with 2 stops'),
    ('uuid twice', lambda t, p: t['templates'][1].update(uuid='a'), 'not sorted by uuid or not unique'),
    ('templates unsorted', lambda t, p: t['templates'].reverse(), 'not sorted by uuid or not unique'),
    ('positions unsorted', lambda t, p: p['positions'].reverse(), 'not sorted by system, then name'),
    ('unknown system', lambda t, p: p['positions'][0].update(system='hades'), "system 'hades'"),
    ('coordinate not a number', lambda t, p: p['positions'][0].update(x='1'), "x '1'"),
    ('source field missing', lambda t, p: t['source'].pop('commit'), 'source.commit missing'),
    ('data versions differ', lambda t, p: p.update(dataVersion='ships-2026.11'), 'dataVersion differs'),
])
def test_each_rule_is_red_once(name: str, fn, expected: str) -> None:
    got = broken(fn)
    assert any(expected in x for x in got), (name, got)


def test_a_template_without_a_system_finds_its_pool_names_in_any_system() -> None:
    t, p = good()
    t['templates'][1].update(system=None, pickupPool=['HUR-L1'])
    assert check.problems(t, p) == []


def test_the_manifest_section_names_both_files_with_their_length_and_hash(tmp_path) -> None:
    (tmp_path / 'hauling-templates.json').write_bytes(b'{}')
    (tmp_path / 'positions.json').write_bytes(b'[]')
    section = check.section(tmp_path)
    assert section == {'schemaVersion': 1,
                       'templates': {'file': 'hauling-templates.json', 'bytes': 2,
                                     'sha256': '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'},
                       'positions': {'file': 'positions.json', 'bytes': 2,
                                     'sha256': '4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945'}}
    assert check.file_problems(tmp_path, section) == []
    (tmp_path / 'positions.json').write_bytes(b'[ ]')
    assert check.file_problems(tmp_path, section) == ['positions.json: length or SHA-256 differs from the manifest']
