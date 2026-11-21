"""A raw contract (scunpacked-data contracts/<uuid>.json) -> a template of schema 1, or the reason it is left out
(H1, sc-cargoplan/docs/hauling-data-format.md with the addenda V1-V4, V6, V8, K2 of the approval)."""
import pytest

from conftest import contract, order
from shipdata.hauling import templates as t


def test_a_covalex_template_takes_its_fields_from_name_title_and_orders() -> None:
    raw = contract(debug='HaulCargo_SingleToMulti2_Supply_PressurizedIce_Stanton1_SupplyGrade2',
                   title='Experienced Rank - Direct Medium Cargo Haul', reward=160250,
                   orders=[order('Pressurized Ice', 41, 72, 16), order('Pressurized Ice', 81, 144, 16)],
                   pickup=['Everus Harbor'], tokens={'Destination1|Address': ['HUR-L1 Green Glade Station'],
                                                     'Destination2|Address': ['HUR-L3 Thundering Express Station',
                                                                              'HUR-L1 Green Glade Station']})
    got, why = t.normalize(raw)
    assert why is None
    assert got == {'uuid': 'u1', 'debugName': 'HaulCargo_SingleToMulti2_Supply_PressurizedIce_Stanton1_SupplyGrade2',
                   'contractor': 'covalex', 'title': 'Experienced Rank - Direct Medium Cargo Haul', 'rank': 'experienced',
                   'size': 'medium', 'direct': True, 'shape': 'singleToMulti', 'stops': 2, 'system': 'stanton',
                   'areaKey': 'Stanton1', 'missionType': 'stellar', 'faction': None, 'reward': 160250,
                   'legs': [{'commodity': 'Pressurized Ice', 'minScu': 41, 'maxScu': 72, 'containerScu': 16},
                            {'commodity': 'Pressurized Ice', 'minScu': 81, 'maxScu': 144, 'containerScu': 16}],
                   'pickupPool': ['Everus Harbor'],
                   'dropoffPool': ['HUR-L1 Green Glade Station', 'HUR-L3 Thundering Express Station']}


def test_a_red_wind_template_has_a_faction_no_reward_and_the_lower_case_form() -> None:
    raw = contract(debug='RedWind_Pyro_BulkGrade_RegionA_HH_StationToStation_Waste_CargoHauling_AtoB',
                   title='Experienced Hauler Needed for Direct Large Shipment', giver='Red Wind Linehaul', reward=None,
                   orders=[order('Waste', 400, 600, 32)], pickup=['Checkmate at the L4 Lagrange of Pyro II'],
                   dropoff=['Patch City at the L3 Lagrange of Pyro III'])
    got, why = t.normalize(raw)
    assert why is None
    assert (got['contractor'], got['system'], got['areaKey'], got['faction'], got['shape'], got['stops'], got['reward'],
            got['rank'], got['size'], got['direct']) == ('redWind', 'pyro', 'RegionA', 'hh', 'aToB', 1, None,
                                                         'experienced', 'large', True)


def test_the_route_type_may_carry_a_region_and_the_commodity_an_underscore() -> None:
    a, _ = t.normalize(contract(debug='RedWind_Pyro_SmallGrade_RegionB_CFP_RuinToStation_RegionB_Slam_unprocessed_CargoHauling_Multi3ToSingle',
                                title='Member Hauler Needed for Small Shipment', giver='Red Wind Linehaul',
                                orders=[order(), order(), order()]))
    assert (a['areaKey'], a['faction'], a['shape'], a['stops']) == ('RegionB', 'cfp', 'multiToSingle', 3)
    b, _ = t.normalize(contract(debug='HaulCargo_AToB_Mixed_Aluminum_Titanium_Stanton_SupplyGrade1',
                                title='Senior Rank - Medium Cargo Haul'))
    assert (b['areaKey'], b['system'], b['direct']) == ('Stanton', 'stanton', False)


@pytest.mark.parametrize('geo, system', [('CrossStanton', 'stanton'), ('Stanton4', 'stanton'), ('Interstellar', None)])
def test_the_geo_part_gives_the_system(geo: str, system: str | None) -> None:
    got, _ = t.normalize(contract(debug=f'HaulCargo_AToB_Metal_Gold_{geo}_BulkGrade', mission='Hauling - Interstellar'))
    assert (got['areaKey'], got['system']) == (geo, system)


def test_red_wind_under_the_covalex_scheme_is_red_wind_by_its_giver() -> None:
    """V4: the contractor comes from MissionGiver; 7 HaulCargo_*_Interstellar are Red Wind's."""
    got, _ = t.normalize(contract(debug='HaulCargo_AToB_Metal_Gold_Interstellar_BulkGrade', giver='Red Wind Linehaul',
                                  title='Rookie Hauler Needed for Direct Bulk Shipment', mission='Hauling - Interstellar'))
    assert (got['contractor'], got['faction'], got['system'], got['size']) == ('redWind', None, None, 'bulk')


@pytest.mark.parametrize('word, rank', [('Trainee', 'trainee'), ('Master', 'master')])
def test_trainee_is_a_rank(word: str, rank: str) -> None:
    got, _ = t.normalize(contract(title=f'{word} Rank - Small Cargo Haul'))
    assert got['rank'] == rank


@pytest.mark.parametrize('raw, why', [
    (contract(released=False), 'not released'),
    (contract(debug='HaulCargo_AToB_RefinedOre_Quartz_TEMPLATE_SmallGrade'), 'abstract template (TEMPLATE)'),
    (contract(giver='Dead Saints'), 'other contractor (Dead Saints)'),
    (contract(debug='HaulCargo_AToB_Mtest'), 'no area in the name'),
    (contract(debug='HaulCargo_SingleToMulti_Metal_Gold_Interstellar'), 'form without a stop count (SingleToMulti)'),
    (contract(debug='RedWind_Pyro_SmallGrade_Solar_HH_StationToStation_Carbon_CargoHauling_AtoB_Intro',
              giver='Red Wind Linehaul', title='Red Wind Seeking New Haulers'), 'form without a stop count (Intro)'),
    (contract(title='Opportunity for Independent Cargo Hauler'), 'title not in the form of its contractor'),
    (contract(mission='Hauling'), 'mission type Hauling'),
    (contract(orders=[]), 'no hauling orders'),
    (contract(orders=[order(lo=6, hi=0)]), 'leg without an SCU band'),
    (contract(orders=[order(box=-1)]), 'container size -1'),
    (contract(orders=[order(kind='MissionItem')]), 'order kind MissionItem'),
])
def test_what_schema_1_cannot_express_is_left_out_with_its_reason(raw: dict, why: str) -> None:
    """V8 and the filter: nothing estimated, nothing filled in; the reason is counted in the summary."""
    assert t.normalize(raw) == (None, why)


def test_only_the_two_naming_schemes_are_candidates() -> None:
    assert [t.candidate(contract(debug=d)) for d in ('HaulCargo_AToB_X_Stanton', 'RedWind_Pyro_X', 'Redwind_Intro',
                                                      'RedWind_RecoverPackage_X', 'PU_Delivery')] == [True, True, False, False, False]


@pytest.mark.parametrize('title', ['Rookie Rank - Gigantic Cargo Haul', 'Captain Rank - Small Cargo Haul'])
def test_an_unknown_word_in_a_known_title_form_stops_the_hauling_job(title: str) -> None:
    """The contract: an unknown size (or rank) word stops the hauling job - a new game build gets looked at."""
    with pytest.raises(t.UnknownWord):
        t.normalize(contract(title=title))


def test_pools_come_from_every_numbered_key_deduplicated_and_sorted() -> None:
    raw = contract(pickup=['B', 'A'], tokens={'Location1|Address': ['C', 'A'], 'Location|address': ['D'],
                                              'Destination3|Address': ['E'], 'Destination|Target|Address': ['F'],
                                              'Contractor|HaulCargo_AtoB': ['text with [Location|Address]']})
    got, _ = t.normalize(raw)
    assert (got['pickupPool'], got['dropoffPool']) == (['A', 'B', 'C', 'D'], ['E'])


def test_the_title_falls_back_when_the_display_title_is_empty() -> None:
    raw = contract()
    raw['DisplayTitle'], raw['Title'] = '', 'Junior Rank - Small Cargo Haul'
    got, _ = t.normalize(raw)
    assert (got['title'], got['rank']) == ('Junior Rank - Small Cargo Haul', 'junior')


@pytest.mark.parametrize('shape, stops, legs, expected', [('aToB', 1, ['A'], True), ('singleToMulti', 2, ['A', 'A'], True),
                                                          ('singleToMulti', 2, ['A', 'A', 'B', 'B'], True),
                                                          ('singleToMulti', 3, ['A', 'A', 'B', 'B'], True),
                                                          ('aToB', 1, ['A', 'B'], True), ('aToB', 1, ['A', 'A'], False)])
def test_the_leg_count_hint_is_min_of_stops_times_commodities_and_4(shape: str, stops: int, legs: list[str], expected: bool) -> None:
    """K2: a hint in the changelog, not a loader rule."""
    tpl = {'shape': shape, 'stops': stops, 'legs': [{'commodity': c} for c in legs]}
    assert t.legs_as_expected(tpl) is expected
