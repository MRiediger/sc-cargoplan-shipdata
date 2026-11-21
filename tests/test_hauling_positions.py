"""Pool names -> starmap entries and the positions file (H1; K1: name = starmap name, contractNames = the contract forms
of the alias table, pools carry the starmap name; K3: names unique per system; V6: drop)."""
from conftest import entity, starmap
from shipdata.hauling import positions as ps

L1 = entity('HUR-L1 Green Glade Station', at=(11550400000.0, 0.0, 0.0))
EVERUS = entity('Everus Harbor', type_='Manmade', at=(12850400000.0, 0.0, 0.0))
CHECKMATE = entity('Checkmate', system='pyro', type_='Manmade')
LORVILLE = entity('Lorville', type_='LandingZone', parent='id-Hurston')
HURSTON = entity('Hurston', type_='Planet')


def tpl(uuid: str = 'u1', system: str | None = 'stanton', pickup: list[str] | None = None,
        dropoff: list[str] | None = None) -> dict:
    return {'uuid': uuid, 'system': system, 'pickupPool': pickup or [], 'dropoffPool': dropoff or []}


def test_an_exact_name_resolves_in_the_template_system() -> None:
    r = ps.resolve([tpl(pickup=['Everus Harbor'], dropoff=['HUR-L1 Green Glade Station'])],
                   ps.Starmap(starmap(EVERUS, L1)), {})
    assert r.gaps == [] and r.used == {'id-Everus Harbor', 'id-HUR-L1 Green Glade Station'}
    assert (r.templates[0]['pickupPool'], r.templates[0]['dropoffPool']) == (['Everus Harbor'], ['HUR-L1 Green Glade Station'])


def test_an_alias_resolves_by_uuid_and_the_pool_carries_the_starmap_name() -> None:
    aliases = {'Checkmate at the L4 Lagrange of Pyro II': {'uuid': 'id-Checkmate', 'starmap': 'Checkmate'},
               'L19 Admin Office in Lorville': {'uuid': 'id-Lorville', 'starmap': 'Lorville'},
               'L19 Habs in Lorville': {'uuid': 'id-Lorville', 'starmap': 'Lorville'}}
    r = ps.resolve([tpl('u1', 'pyro', pickup=['Checkmate at the L4 Lagrange of Pyro II']),
                    tpl('u2', dropoff=['L19 Habs in Lorville', 'L19 Admin Office in Lorville', 'Lorville'])],
                   ps.Starmap(starmap(CHECKMATE, LORVILLE)), aliases)
    assert r.gaps == []
    assert r.templates[0]['pickupPool'] == ['Checkmate'] and r.templates[1]['dropoffPool'] == ['Lorville']


def test_an_alias_whose_starmap_name_changed_still_resolves_with_a_hint() -> None:
    r = ps.resolve([tpl(pickup=['Old Name'])], ps.Starmap(starmap(entity('New Name', uuid='x1'))),
                   {'Old Name': {'uuid': 'x1', 'starmap': 'Renamed Before'}})
    assert r.gaps == [] and r.templates[0]['pickupPool'] == ['New Name']
    assert any('renamed' in h for h in r.hints)


def test_an_alias_to_a_uuid_the_starmap_lost_is_a_gap() -> None:
    r = ps.resolve([tpl(pickup=['Gone Place'])], ps.Starmap(starmap(EVERUS)), {'Gone Place': {'uuid': 'nope', 'starmap': 'X'}})
    assert [(g.name, g.why) for g in r.gaps] == [('Gone Place', 'the alias names a uuid the starmap does not have')]


def test_a_drop_alias_takes_the_name_out_of_the_pool_and_counts_it() -> None:
    r = ps.resolve([tpl(dropoff=['Lobby', 'Everus Harbor'])], ps.Starmap(starmap(EVERUS)), {'Lobby': {'drop': 'placeholder'}})
    assert r.gaps == [] and r.templates[0]['dropoffPool'] == ['Everus Harbor'] and r.dropped == {'Lobby': 1}


def test_an_unknown_name_is_a_gap_with_candidates_and_the_templates_that_name_it() -> None:
    r = ps.resolve([tpl('u1', 'pyro', pickup=['Checkmate at the L4 Lagrange of Pyro II']),
                    tpl('u2', 'pyro', dropoff=['Checkmate at the L4 Lagrange of Pyro II'])],
                   ps.Starmap(starmap(CHECKMATE, entity('Ruin Station', system='pyro'))), {})
    [g] = r.gaps
    assert (g.name, g.system, g.why, g.templates) == ('Checkmate at the L4 Lagrange of Pyro II', 'pyro',
                                                      'no starmap entry of that name', ['u1', 'u2'])
    assert [c['uuid'] for c in g.candidates] == ['id-Checkmate']


def test_a_name_twice_in_the_system_is_a_gap() -> None:
    sm = ps.Starmap(starmap(entity('Derelict Outpost', 'pyro', 'Outpost', 'd1', hidden=True),
                            entity('Derelict Outpost', 'pyro', 'Outpost', 'd2', hidden=True)))
    [g] = ps.resolve([tpl(system='pyro', pickup=['Derelict Outpost'])], sm, {}).gaps
    assert g.why == 'ambiguous: 2 starmap entries of that name' and len(g.candidates) == 2


def test_without_a_system_a_name_resolves_only_when_it_is_unique_in_all_three() -> None:
    sm = ps.Starmap(starmap(entity('Pyro Gateway', 'stanton', 'Manmade', 'g1'), entity('Pyro Gateway', 'nyx', 'Manmade', 'g2'),
                            EVERUS, entity('Elsewhere', 'hades', 'Manmade')))
    r = ps.resolve([tpl(system=None, pickup=['Everus Harbor'], dropoff=['Pyro Gateway', 'Elsewhere'])], sm, {})
    assert [(g.name, g.why) for g in r.gaps] == [('Elsewhere', 'no starmap entry of that name'),
                                                 ('Pyro Gateway', 'ambiguous: 2 starmap entries of that name')]


def test_the_file_holds_stations_planets_stars_of_three_systems_and_every_pool_place() -> None:
    sm = ps.Starmap(starmap(EVERUS, L1, HURSTON, LORVILLE, entity('Stanton', type_='Star'), CHECKMATE,
                            entity('Hidden Base', 'nyx', 'Manmade', hidden=True), entity('Levski', 'nyx', 'LandingZone'),
                            entity('Some Outpost', type_='Outpost'), entity('Far Away', 'hades', 'Manmade'),
                            entity('Odin', 'nyx', 'Planet')))
    got, hints = ps.build(sm, {'id-Lorville'}, {})
    assert hints == []
    assert [(x['system'], x['name']) for x in got] == [('nyx', 'Odin'), ('pyro', 'Checkmate'), ('stanton', 'Everus Harbor'),
                                                       ('stanton', 'HUR-L1 Green Glade Station'), ('stanton', 'Hurston'),
                                                       ('stanton', 'Lorville'), ('stanton', 'Stanton')]


def test_a_position_has_its_parent_name_and_the_contract_forms_of_the_alias_table() -> None:
    aliases = {'L19 Habs in Lorville': {'uuid': 'id-Lorville', 'starmap': 'Lorville'},
               'L19 Admin Office in Lorville': {'uuid': 'id-Lorville', 'starmap': 'Lorville'},
               'Lobby': {'drop': 'placeholder'}}
    got, _ = ps.build(ps.Starmap(starmap(HURSTON, LORVILLE, entity('Orphan', parent='id-unknown'))), {'id-Lorville'}, aliases)
    by = {x['name']: x for x in got}
    assert by['Lorville'] == {'uuid': 'id-Lorville', 'name': 'Lorville', 'system': 'stanton', 'type': 'LandingZone',
                              'parent': 'Hurston', 'x': 0.0, 'y': 0.0, 'z': 0.0,
                              'contractNames': ['L19 Admin Office in Lorville', 'L19 Habs in Lorville']}
    assert by['Orphan']['parent'] is None and by['Hurston']['contractNames'] == []


def test_a_name_twice_in_one_system_keeps_the_first_and_a_used_one_wins() -> None:
    """K3: unique per system; the gateways of the same name in two systems both stay."""
    sm = ps.Starmap(starmap(entity('Dup', type_='Manmade', uuid='a'), entity('Dup', type_='Manmade', uuid='b'),
                            entity('Twin', type_='Manmade', uuid='c'), entity('Twin', type_='Manmade', uuid='d'),
                            entity('Stanton Gateway', 'pyro', 'Manmade', 's1'), entity('Stanton Gateway', 'nyx', 'Manmade', 's2')))
    got, hints = ps.build(sm, {'d'}, {})
    assert sorted((x['system'], x['name'], x['uuid']) for x in got) == [
        ('nyx', 'Stanton Gateway', 's2'), ('pyro', 'Stanton Gateway', 's1'), ('stanton', 'Dup', 'a'), ('stanton', 'Twin', 'd')]
    assert len(hints) == 2 and all('twice in stanton' in h for h in hints)


def test_a_proposal_keeps_the_table_and_adds_each_gap() -> None:
    gaps = [ps.Gap('Checkmate at the L4', 'pyro', 'no starmap entry of that name', ['u1'],
                   [{'uuid': 'id-Checkmate', 'name': 'Checkmate', 'system': 'pyro', 'type': 'Manmade'}]),
            ps.Gap('Rayari', 'stanton', 'no starmap entry of that name', ['u2'],
                   [{'uuid': 'r1', 'name': 'Rayari A', 'system': 'stanton', 'type': 'Outpost'},
                    {'uuid': 'r2', 'name': 'Rayari B', 'system': 'stanton', 'type': 'Outpost'}])]
    out = ps.propose({'Lobby': {'drop': 'placeholder'}}, gaps)
    assert out['Lobby'] == {'drop': 'placeholder'}
    assert out['Checkmate at the L4'] == {'uuid': 'id-Checkmate', 'starmap': 'Checkmate'}
    assert out['Rayari']['drop'].startswith('no unique starmap entry')
    assert list(out) == sorted(out)
