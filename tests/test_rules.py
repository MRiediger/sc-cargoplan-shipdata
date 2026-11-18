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


def test_a_ship_back_in_the_catalog_is_named_with_what_it_was() -> None:
    """SD6 "back": missingSince or follows in the last manifest, in the catalog again -> both are cleared."""
    prev = {'f7c': dict(entry('anvl-f7c', 'r5', '2026-11-16'), follows=None),
            'mole_carbon_edition': dict(entry('argo-mole', 'r1'), follows='mole'),
            'mole': dict(entry('argo-mole', 'r1'), follows=None), 'cyclone': dict(PREV['cyclone'], follows=None)}
    assert rules.back(prev, present={'f7c', 'mole_carbon_edition', 'mole'}) == {
        'f7c': 'missing since 2026-11-16', 'mole_carbon_edition': 'followed mole'}


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


# Judge (SD5, replaces P9): a turn for the worse is a metric, not a flag. Each fixture lets exactly one case fire (lesson
# of T12.1: a second check catching the same case keeps a broken rule green). The tests read the finding's fields (E1).
A, B = 'TEST_A', 'TEST_B'


def built(passed: bool, h: float, fails: list[str], triangles: int = 30000, budget: int = 40000) -> dict:
    """PP.json of a newly built hologram: the judge's numbers at the top level."""
    return {'passed': passed, 'fails': fails, 'triangles': triangles, 'budget': budget,
            'topHausdorff': h, 'sideHausdorff': 0.001, 'frontHausdorff': 0.001}


def published(model: str, passed: bool, h: float, fails: list[str]) -> dict:
    """holo.ships.<slug> of the last manifest."""
    return {'model': model, 'passed': passed, 'fails': fails, 'triangles': 30000, 'budget': 40000,
            'metrics': {'topHausdorff': h, 'sideHausdorff': 0.001, 'frontHausdorff': 0.001}}


def test_judge_case_1_passed_turns_false() -> None:
    f = rules.judge('test-a', built(False, 0.0055, ['hausdorff']), published(A, True, 0.0040, []), A)
    assert f is not None and f.stop and f.data['cases'] == [1]
    assert f.data['passed'] == {'old': True, 'new': False}


def test_judge_case_2_above_110_percent_of_the_budget() -> None:
    f = rules.judge('test-a', built(True, 0.001, [], triangles=22001, budget=20000), published(A, True, 0.001, []), A)
    assert f is not None and f.stop and f.data['cases'] == [2]


def test_judge_case_3_hausdorff_worse_by_more_than_the_tolerance() -> None:
    f = rules.judge('test-a', built(False, 0.0150, ['hausdorff']), published(A, False, 0.0124, ['hausdorff']), A)
    assert f is not None and f.stop and f.data['cases'] == [3]
    assert f.data['hausdorff'] == {'old': 0.0124, 'new': 0.0150, 'delta': 0.0026, 'tolerance': rules.HAUSDORFF_TOLERANCE}


def test_judge_case_3_within_the_tolerance_is_a_note() -> None:
    f = rules.judge('test-a', built(False, 0.0148, ['hausdorff']), published(A, False, 0.0124, ['hausdorff']), A)
    assert f is not None and not f.stop and f.data['cases'] == []


def test_judge_case_4_a_new_ship_stops_even_when_it_passes() -> None:
    f = rules.judge('test-a', built(True, 0.001, []), None, A)
    assert f is not None and f.stop and f.data['cases'] == [4]


def test_judge_case_4_a_change_of_source_stops_even_when_it_passes() -> None:
    f = rules.judge('anvl-f7c', built(True, 0.001, []), published('fleetyards (holo-v1)', True, 0.0, []), A)
    assert f is not None and f.stop and f.data['cases'] == [4]
    assert f.data['model'] == {'old': 'fleetyards (holo-v1)', 'new': A}


def test_judge_case_5_one_more_metric_failed() -> None:
    f = rules.judge('test-a', built(False, 0.0129, ['hausdorff', 'iou']), published(A, False, 0.0124, ['hausdorff']), A)
    assert f is not None and f.stop and f.data['cases'] == [5]
    assert f.data['fails'] == {'old': ['hausdorff'], 'new': ['hausdorff', 'iou']}


def test_judge_otherwise_a_note_also_for_a_reexported_failed_ship() -> None:
    """A re-export (same className, new model hash) of a ship published with passed=false: comparable, a note."""
    f = rules.judge('test-a', built(False, 0.0134, ['hausdorff']), published(A, False, 0.0124, ['hausdorff']), A)
    assert f is not None and not f.stop and f.data['cases'] == []
    assert rules.judge('test-b', built(True, 0.001, []), published(B, True, 0.001, []), B) is None
