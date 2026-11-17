"""The rules of CLAUDE.md as code (verify). Each one was red once before rules.py had it (TASKS.md, T12.1 findings)."""
from shipdata import rules

TODAY = '2026-11-17'


def entry(key: str, racks: str, missing: str | None = None) -> dict:
    return {'source': 's', 'modelKey': key, 'racksSha256': racks, 'missingSince': missing}


PREV = {'mole': entry('argo-mole', 'r1'), 'mole_carbon_edition': entry('argo-mole', 'r1'),
        'carrack': entry('anvl-carrack', 'r2'), 'carrack_w_c8x': entry('anvl-carrack', 'r9'),
        'cyclone': entry('tmbl-cyclone', 'r3', '2026-11-16'), 'lonely': entry('test-lonely', 'r4')}


def test_a_gone_variant_with_hash_equal_racks_follows_its_base() -> None:
    out = rules.missing(['mole_carbon_edition'], PREV, present={'mole', 'carrack'}, today=TODAY)
    assert out.follows == {'mole_carbon_edition': 'mole'}
    assert out.missing_since == {}


def test_a_gone_variant_with_other_racks_gets_missing_since() -> None:
    out = rules.missing(['carrack_w_c8x'], PREV, present={'mole', 'carrack'}, today=TODAY)
    assert out.follows == {}
    assert out.missing_since == {'carrack_w_c8x': TODAY}
    assert out.newly_without_base == ['carrack_w_c8x']


def test_a_variant_whose_base_is_gone_too_gets_missing_since() -> None:
    out = rules.missing(['mole_carbon_edition', 'mole'], PREV, present={'carrack'}, today=TODAY)
    assert out.missing_since == {'mole_carbon_edition': TODAY, 'mole': TODAY}


def test_missing_since_stays_from_the_run_that_first_missed_the_ship() -> None:
    out = rules.missing(['cyclone'], PREV, present=set(), today=TODAY)
    assert out.missing_since == {'cyclone': '2026-11-16'}
    assert out.newly_without_base == []


def test_more_than_three_newly_gone_without_base_stop_the_run() -> None:
    assert rules.too_many_gone(['a', 'b', 'c']) is None
    stop = rules.too_many_gone(['a', 'b', 'c', 'd'])
    assert stop is not None and stop.stop and '4' in stop.detail


def import_entry(sid: str, status: str, detail: str = '', anchors_kept: bool = False) -> dict:
    return {'id': sid, 'status': status, 'detail': detail, 'className': 'X', 'modelKey': 'x', 'anchorsKept': anchors_kept}


def test_overlapping_grids_stop_the_run() -> None:
    found = rules.import_findings([import_entry('overlap_ship', 'handcheck', 'grids overlap: rack-0/rack-1')], overrides={})
    assert [(f.rule, f.stop) for f in found] == [('overlap', True)]


def test_another_hand_check_stops_too() -> None:
    found = rules.import_findings([import_entry('x', 'handcheck', 'rack set differs: 2 racks, 3 grids of 1x2x2 cells')], {})
    assert [(f.rule, f.stop) for f in found] == [('handcheck', True)]


def test_grids_in_another_order_stop() -> None:
    assert [f.stop for f in rules.import_findings([import_entry('x', 'order')], {})] == [True]


def test_a_grid_without_transform_with_an_override_is_a_hint() -> None:
    found = rules.import_findings([import_entry('135c', 'kept')], {'135c': {'id': '135c', 'reason': 'r', 'date': 'd'}})
    assert [(f.rule, f.stop) for f in found] == [('no-transform', False)]


def test_a_grid_without_transform_without_an_override_stops_and_proposes_the_entry() -> None:
    found = rules.import_findings([import_entry('135c', 'kept', 'a grid without transform')], {})
    assert [(f.rule, f.stop) for f in found] == [('no-transform', True)]
    assert found[0].proposal == {'id': '135c', 'reason': 'a grid without transform in the catalog: the ship stays as it is',
                                 'date': None}


def test_anchors_left_unset_stop() -> None:
    assert [f.stop for f in rules.import_findings([import_entry('x', 'same', anchors_kept=True)], {})] == [True]


# Judge (Martin, 17.11.): only a turn for the worse stops. holo-v3 published 22 of 101 ships with passed=false, approved
# on their contact sheet; an unchanged one of them must not open a PR every month.
PASSED = {'passed': True, 'triangles': 21000, 'budget': 20000, 'fails': []}
FAILED = {'passed': False, 'triangles': 39000, 'budget': 40000, 'fails': ['topHausdorff']}


def test_judge_passes_a_ship_in_its_budget() -> None:
    assert rules.judge('test-a', PASSED, previous=None, new_model=True) is None


def test_judge_stops_a_ship_that_passed_before_and_fails_now() -> None:
    f = rules.judge('test-a', FAILED, previous={'passed': True}, new_model=False)
    assert f is not None and f.stop and 'topHausdorff' in f.detail


def test_judge_stops_a_new_ship_that_fails() -> None:
    f = rules.judge('test-a', FAILED, previous=None, new_model=True)
    assert f is not None and f.stop


def test_judge_stops_a_failed_ship_with_a_new_model() -> None:
    f = rules.judge('test-a', FAILED, previous={'passed': False}, new_model=True)
    assert f is not None and f.stop


def test_judge_only_notes_a_ship_published_failed_with_the_same_model() -> None:
    f = rules.judge('test-a', FAILED, previous={'passed': False}, new_model=False)
    assert f is not None and not f.stop


def test_judge_stops_a_ship_above_110_percent_of_its_budget() -> None:
    f = rules.judge('test-a', dict(PASSED, triangles=22001), previous={'passed': True}, new_model=False)
    assert f is not None and f.stop and '110' in f.detail
