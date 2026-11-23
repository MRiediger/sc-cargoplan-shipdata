"""Hauling data against the last release (H1): templates new, gone, reward changed; places new, gone, renamed, moved
(> 1 km), contract names changed; stamps never compared (rule C of T12.1)."""
from shipdata.hauling import diff


def t(uuid: str, reward: int | None = 100, **kw) -> dict:
    return dict({'uuid': uuid, 'title': f'T {uuid}', 'reward': reward, 'legs': [{'commodity': 'Q'}]}, **kw)


def p(uuid: str, name: str, x: float = 0.0, names: list[str] | None = None) -> dict:
    return {'uuid': uuid, 'name': name, 'system': 'stanton', 'type': 'Manmade', 'parent': None, 'x': x, 'y': 0.0, 'z': 0.0,
            'contractNames': names or []}


def doc(key: str, items: list[dict], version: str = 'ships-2026.12', commit: str = 'abc') -> dict:
    return {'schemaVersion': 1, 'dataVersion': version, 'source': {'commit': commit}, key: items}


def test_templates_new_gone_and_reward_changes_by_uuid() -> None:
    d = diff.compare(doc('templates', [t('a'), t('b', 200), t('c')]), doc('templates', [t('b', 250), t('c'), t('d')]),
                     doc('positions', []), doc('positions', []))
    assert d['templates'] == {'new': ['d'], 'gone': ['a'], 'reward': [{'uuid': 'b', 'title': 'T b', 'old': 200, 'new': 250}],
                              'otherwiseChanged': [], 'same': 1}
    assert d['changed'] is True


def test_places_new_gone_renamed_moved_and_contract_names() -> None:
    old = doc('positions', [p('1', 'A'), p('2', 'B'), p('3', 'C', 0.0), p('4', 'D', 0.0), p('5', 'E', names=['e'])])
    new = doc('positions', [p('2', 'B2'), p('3', 'C', 1001.0), p('4', 'D', 999.0), p('5', 'E', names=['e', 'f']), p('6', 'F')])
    d = diff.compare(doc('templates', []), doc('templates', []), old, new)
    assert d['positions'] == {'new': ['F'], 'gone': ['A'], 'renamed': [{'uuid': '2', 'old': 'B', 'new': 'B2'}],
                              'moved': [{'name': 'C', 'metres': 1001.0}], 'contractNames': ['E'], 'same': 0}   # D: 999 m


def test_stamps_alone_are_no_change() -> None:
    a = diff.compare(doc('templates', [t('a')], 'ships-2026.11', 'x'), doc('templates', [t('a')], 'ships-2026.12', 'y'),
                     doc('positions', [p('1', 'A')], 'ships-2026.11', 'x'), doc('positions', [p('1', 'A')], 'ships-2026.12', 'y'))
    assert a['changed'] is False


def test_a_move_below_one_km_is_no_change_but_still_not_byte_equal() -> None:
    d = diff.compare(doc('templates', []), doc('templates', []), doc('positions', [p('1', 'A', 0.0)]),
                     doc('positions', [p('1', 'A', 5.0)]))
    assert d['positions']['moved'] == [] and d['changed'] is True


def test_without_a_previous_everything_is_new() -> None:
    d = diff.compare(None, doc('templates', [t('a')]), None, doc('positions', [p('1', 'A')]))
    assert (d['templates']['new'], d['positions']['new'], d['changed']) == (['a'], ['A'], True)


def test_the_changelog_names_the_numbers_and_the_reward_changes() -> None:
    d = diff.compare(doc('templates', [t('b', 200)]), doc('templates', [t('b', 250), t('d')]), doc('positions', []),
                     doc('positions', [p('6', 'F')]))
    text = diff.changelog(d, legs_off=3, excluded={'not released': 5}, dropped=2, carried=None)
    assert '1 new, 0 gone, 1 reward changed' in text and 'T b: 200 → 250' in text and '1 new' in text
    assert '3 templates' in text and 'not released 5' in text
    carried = diff.changelog(None, legs_off=0, excluded={}, dropped=0, carried=('ships-2026.11', 'source: down'))
    assert 'carried forward unchanged from ships-2026.11' in carried and 'source: down' in carried
