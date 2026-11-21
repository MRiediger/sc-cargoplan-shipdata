"""run.py hauling and hauling-pr (H1, SD14) and the hauling assets in manifest, release and draft: a source stream in
memory, the last release from release_folder, GitHub and git faked. K2 throughout: the hauling job never stops the ship
data - it writes `failed` and exit 0; verify carries the last release's files or writes null."""
import io
import json
import shutil
import tarfile
from pathlib import Path

import pytest

from conftest import contract, entity, order, starmap, write_json
from shipdata import manifest, release, workflow
from shipdata.hauling import check, source, stage
from shipdata.log import Reporter
from test_heartbeat_pr import FakeGit, git  # noqa: F401  (fixture)
from test_workflow_stages import FakeGitHub, gh, paths, release_folder  # noqa: F401  (fixture)

COMMIT = {'sha': 'f182b7f111279c9193df81927c9b4dbc8c4f3291',
          'commit': {'message': '4.10.3-LIVE.13165946\n\nupdate', 'committer': {'date': '2026-11-13T09:58:13Z'}}}
CONTRACTS = [contract('u1', pickup=['HUR-L1 Green Glade Station'], dropoff=['Everus Harbor']),
             contract('u2', debug='RedWind_Pyro_BulkGrade_Solar_HH_StationToStation_Waste_CargoHauling_AtoB',
                      title='Senior Hauler Needed for Large Shipment', giver='Red Wind Linehaul', reward=None,
                      orders=[order('Waste', 400, 600, 32)], pickup=['Checkmate at the L4 Lagrange of Pyro II'],
                      dropoff=['Lobby']),
             contract('u3', released=False),
             {'UUID': 'x', 'DebugName': 'PU_Delivery_X'}]
STARMAP = starmap(entity('Everus Harbor', type_='Manmade', at=(12850400000.0, 0.0, 0.0)),
                  entity('HUR-L1 Green Glade Station', at=(11550400000.0, 0.0, 0.0)),
                  entity('Checkmate', system='pyro', type_='Manmade', uuid='cm'))
ALIASES = {'schemaVersion': 1, 'aliases': {'Checkmate at the L4 Lagrange of Pyro II': {'uuid': 'cm', 'starmap': 'Checkmate'},
                                           'Lobby': {'drop': 'placeholder'}}}


def tarball(contracts: list[dict], sm: dict | None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        def add(name: str, doc: object) -> None:
            data = json.dumps(doc).encode()
            info = tarfile.TarInfo(f'scunpacked-data-f182b7f/{name}')
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        for c in contracts:
            add(f"contracts/{c['UUID']}.json", c)
        add('items.json', {'not': 'read'})
        if sm is not None:
            add('starmap_positions.json', sm)
    return buf.getvalue()


def saved(tmp: Path, contracts: list[dict] = CONTRACTS, sm: dict | None = STARMAP) -> Path:
    d = tmp / 'saved'
    d.mkdir(exist_ok=True)
    write_json(d / source.SAVED_COMMIT, COMMIT)
    (d / source.SAVED_TARBALL).write_bytes(tarball(contracts, sm))
    return d


def setup(tmp: Path, previous: Path | None = None, aliases: dict = ALIASES) -> tuple:
    tmp.mkdir(parents=True, exist_ok=True)
    p = paths(tmp)
    write_json(p.root / 'tools' / 'hauling-aliases.json', aliases)
    workflow.save_json(p.w('previous.json'), {'tag': 'ships-2026.11.1', 'nextVersion': 'ships-2026.11.2', 'latestFlag': []})
    folder = previous or release_folder(tmp / 'prev', 'ships-2026.11.1')
    shutil.copytree(folder, p.w('previous-release'))
    return p, Reporter(p.out)


def status(p) -> dict:
    return json.loads(p.w('hauling.json').read_text(encoding='utf-8'))


# ---------------------------------------------------------------- source

def test_the_source_keeps_the_two_schemes_and_the_starmap_from_one_stream(tmp_path: Path) -> None:
    src = source.fetch(saved(tmp_path))
    assert [c['UUID'] for c in src.contracts] == ['u1', 'u2', 'u3']
    assert (src.commit, src.game_build, src.contract_files, src.requests) == (COMMIT['sha'], '4.10.3-LIVE.13165946', 4, 0)
    assert len(src.starmap['entities']) == 3


def test_a_tarball_without_the_starmap_is_a_source_error(tmp_path: Path) -> None:
    with pytest.raises(source.SourceError, match='starmap_positions.json'):
        source.fetch(saved(tmp_path, sm=None))


def test_the_game_build_comes_from_the_commit_message() -> None:
    assert source.game_build('4.10.3-LIVE.13165946') == '4.10.3-LIVE.13165946'
    assert source.game_build('Update to 4.11.0-PTU.14000000 data\nmore') == '4.11.0-PTU.14000000'
    assert source.game_build('just data') == 'just data'


# ---------------------------------------------------------------- run.py hauling

def test_a_good_run_writes_both_files_and_says_changed_against_a_release_without_hauling(tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    assert stage.hauling_stage(p, log, saved(tmp_path), fetched_at='2026-12-01T04:10:00Z') == 0
    s = status(p)
    assert (s['status'], s['changed'], s['kind']) == ('ok', True, None)
    assert stage.changed(p) is True            # SD14: a hauling change alone releases (diff reads this)
    t = json.loads((p.w('hauling') / check.TEMPLATES_FILE).read_text(encoding='utf-8'))
    pos = json.loads((p.w('hauling') / check.POSITIONS_FILE).read_text(encoding='utf-8'))
    assert check.problems(t, pos) == []
    assert t['dataVersion'] == 'ships-2026.11.2' and t['source'] == {
        'repository': 'StarCitizenWiki/scunpacked-data', 'commit': COMMIT['sha'], 'gameBuild': '4.10.3-LIVE.13165946',
        'fetchedAt': '2026-12-01T04:10:00Z'}
    assert pos['source']['file'] == 'starmap_positions.json'
    assert [x['uuid'] for x in t['templates']] == ['u1', 'u2']
    assert t['templates'][1]['pickupPool'] == ['Checkmate'] and t['templates'][1]['dropoffPool'] == []
    assert next(x for x in pos['positions'] if x['name'] == 'Checkmate')['contractNames'] == [
        'Checkmate at the L4 Lagrange of Pyro II']
    assert s['excluded'] == {'not released': 1} and s['dropped'] == 1
    assert 'Hauling templates:** 2 new' in p.w('hauling-changelog.md').read_text(encoding='utf-8')


def test_a_gap_fails_the_job_writes_the_proposal_and_no_files(tmp_path: Path) -> None:
    p, log = setup(tmp_path, aliases={'schemaVersion': 1, 'aliases': {'Lobby': {'drop': 'placeholder'}}})
    assert stage.hauling_stage(p, log, saved(tmp_path)) == 0
    s = status(p)
    assert (s['status'], s['kind'], s['changed']) == ('failed', 'gap', False)
    assert [g['name'] for g in s['gaps']] == ['Checkmate at the L4 Lagrange of Pyro II']
    proposed = json.loads(p.w('hauling-aliases-proposed.json').read_text(encoding='utf-8'))
    assert proposed['aliases']['Checkmate at the L4 Lagrange of Pyro II'] == {'uuid': 'cm', 'starmap': 'Checkmate'}
    assert not (p.w('hauling') / check.TEMPLATES_FILE).exists()


def test_a_source_error_fails_the_job_with_exit_0(tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    assert stage.hauling_stage(p, log, tmp_path / 'nothing-here') == 0
    assert (status(p)['status'], status(p)['kind']) == ('failed', 'source')


def test_an_unknown_title_word_fails_the_job(tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    stage.hauling_stage(p, log, saved(tmp_path, contracts=[contract('u9', title='Admiral Rank - Small Cargo Haul')]))
    assert (status(p)['status'], status(p)['kind']) == ('failed', 'words')


def test_same_content_as_the_last_release_is_no_change(tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    stage.hauling_stage(p, log, saved(tmp_path), fetched_at='2026-12-01T04:10:00Z')
    prev = with_hauling(tmp_path, p.w('hauling'))
    p2, log2 = setup(tmp_path / 'again', previous=prev)
    stage.hauling_stage(p2, log2, saved(tmp_path), fetched_at='2027-01-01T04:10:00Z')
    assert (status(p2)['status'], status(p2)['changed']) == ('ok', False)
    assert stage.changed(p2) is False


def with_hauling(tmp: Path, files: Path, corrupt: bool = False) -> Path:
    """A last release that carries hauling files (section in its manifest)."""
    folder = release_folder(tmp / 'prev-h', 'ships-2026.11.1')
    for name in check.FILES:
        shutil.copyfile(files / name, folder / name)
    m = manifest.read(folder / 'manifest.json')
    m['hauling'] = check.section(folder)
    manifest.write(folder / 'manifest.json', m)
    if corrupt:
        (folder / check.POSITIONS_FILE).write_text('{}', encoding='utf-8')
    return folder


# ---------------------------------------------------------------- K2: what goes into the release

def test_ok_releases_the_new_files(tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    stage.hauling_stage(p, log, saved(tmp_path))
    folder, state, note = stage.release_files(p, p.w('previous-release'))
    assert (folder, state) == (p.w('hauling'), 'updated')


def test_a_failed_job_carries_the_last_release_files_unchanged(tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    stage.hauling_stage(p, log, saved(tmp_path))
    prev = with_hauling(tmp_path, p.w('hauling'))
    p2, log2 = setup(tmp_path / 'b', previous=prev)
    stage.hauling_stage(p2, log2, tmp_path / 'nothing-here')
    folder, state, note = stage.release_files(p2, p2.w('previous-release'))
    assert (folder, state) == (p2.w('previous-release'), 'carried')
    assert 'ships-2026.11.1' in note and 'source' in note
    assert stage.changed(p2) is False


def test_a_failed_job_without_last_files_releases_null(tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    stage.hauling_stage(p, log, tmp_path / 'nothing-here')
    assert stage.release_files(p, p.w('previous-release'))[:2] == (None, 'none')


def test_a_crashed_step_counts_as_failed(tmp_path: Path) -> None:
    """The step has continue-on-error: a bug leaves no work/hauling.json, verify carries the last files all the same."""
    p, _ = setup(tmp_path)
    assert stage.release_files(p, p.w('previous-release'))[:2] == (None, 'none') and stage.changed(p) is False


def test_last_files_that_differ_from_their_manifest_are_not_carried(tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    stage.hauling_stage(p, log, saved(tmp_path))
    prev = with_hauling(tmp_path, p.w('hauling'), corrupt=True)
    p2, log2 = setup(tmp_path / 'b', previous=prev)
    stage.hauling_stage(p2, log2, tmp_path / 'nothing-here')
    folder, state, note = stage.release_files(p2, p2.w('previous-release'))
    assert (folder, state) == (None, 'none') and 'differs' in note


# ---------------------------------------------------------------- manifest, pack, draft

def test_the_manifest_section_the_zip_and_the_assets(tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    stage.hauling_stage(p, log, saved(tmp_path))
    s = tmp_path / 'stage'
    (s / 'ships').mkdir(parents=True)
    (s / 'ships' / 'a.json').write_text('{"schemaVersion": 6, "racks": []}', encoding='utf-8')
    (s / 'outlines.json').write_text('{}', encoding='utf-8')
    for name in check.FILES:
        shutil.copyfile(p.w('hauling') / name, s / name)
    m = manifest.build(s, data_version='ships-2026.11.2', generated_at='t', motherlode={}, app_tag='v0.5.1',
                       pipeline_commit='x', tools={}, holo_ships=None, ships={}, hauling=check.section(s))
    assert list(m)[-3:] == ['holo', 'hauling', 'ships']
    assert sorted(m['files']) == ['outlines.json', 'ships/a.json']          # not in files, not in ships.zip
    assert manifest.check(s, m) == []
    manifest.write(s / 'manifest.json', m)
    assets = {a.name for a in release.pack(s, tmp_path / 'rel', p.root / 'NOTICE.md')}
    assert assets == {'manifest.json', 'NOTICE.md', 'ships.zip', *check.FILES}
    assert set(workflow.expected_assets(m)) == assets
    (s / check.POSITIONS_FILE).write_text('{}', encoding='utf-8')
    assert manifest.check(s, m) == ['positions.json: length or SHA-256 differs from the manifest']


def test_a_manifest_without_hauling_still_reads_and_null_is_written_as_null(tmp_path: Path) -> None:
    folder = release_folder(tmp_path / 'r', 'ships-2026.11.1')
    m = manifest.read(folder / 'manifest.json')
    assert 'hauling' not in m and set(workflow.expected_assets(m)) == {'manifest.json', 'NOTICE.md', 'ships.zip',
                                                                          'test-a.holo', 'test-b.holo'}


def test_a_hauling_section_with_a_foreign_file_name_is_turned_down(tmp_path: Path) -> None:
    folder = release_folder(tmp_path / 'r', 'ships-2026.11.1')
    m = manifest.read(folder / 'manifest.json')
    m['hauling'] = {'schemaVersion': 1, 'templates': {'file': '../x.json', 'bytes': 1, 'sha256': 'a'},
                    'positions': {'file': 'positions.json', 'bytes': 1, 'sha256': 'b'}}
    manifest.write(folder / 'manifest.json', m)
    with pytest.raises(manifest.ManifestError, match='hauling'):
        manifest.read(folder / 'manifest.json')


# ---------------------------------------------------------------- run.py hauling-pr (E1)

def test_a_gap_opens_the_alias_pr_on_its_own_branch(gh: FakeGitHub, git: FakeGit, tmp_path: Path) -> None:
    p, log = setup(tmp_path, aliases={'schemaVersion': 1, 'aliases': {'Lobby': {'drop': 'placeholder'}}})
    stage.hauling_stage(p, log, saved(tmp_path))
    assert stage.hauling_pr_stage(p, log, 'https://run', dry_run=False) == 0
    assert git.calls[0] == ('switch', '-C', 'data/hauling-aliases')
    assert ('push', '--force', 'origin', 'data/hauling-aliases') in git.calls
    assert next(c for c in git.calls if c[0] == 'add')[1:] == ('tools/hauling-aliases.json',)
    table = json.loads((p.root / 'tools' / 'hauling-aliases.json').read_text(encoding='utf-8'))
    assert 'Checkmate at the L4 Lagrange of Pyro II' in table['aliases']
    [pr] = gh.prs
    assert pr['headRefName'] == 'data/hauling-aliases' and 'Checkmate at the L4 Lagrange of Pyro II' in pr['body']


def test_any_other_failure_opens_an_issue_and_the_next_one_comments(gh: FakeGitHub, git: FakeGit, tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    stage.hauling_stage(p, log, tmp_path / 'nothing-here')
    stage.hauling_pr_stage(p, log, 'https://run/1', dry_run=False)
    assert [i['title'] for i in gh.issues] == [stage.ISSUE_TITLE] and 'source' in gh.issues[0]['body']
    stage.hauling_pr_stage(p, log, 'https://run/2', dry_run=False)
    assert len(gh.issues) == 1 and 'https://run/2' in gh.issues[0]['comments'][0]
    assert git.calls == []


def test_a_crashed_step_opens_an_issue_with_the_error_line(gh: FakeGitHub, git: FakeGit, tmp_path: Path) -> None:
    p, log = setup(tmp_path)
    (p.out / 'say-chain.jsonl').write_text(json.dumps({'job': 'chain', 'step': 'hauling', 'checked': 'run.py hauling',
                                                       'found': 'error: KeyError: x', 'todo': 'fix'}) + '\n', encoding='utf-8')
    stage.hauling_pr_stage(p, log, 'https://run', dry_run=False)
    assert 'KeyError: x' in gh.issues[0]['body']


def test_the_dry_run_writes_the_text_only(gh: FakeGitHub, git: FakeGit, tmp_path: Path) -> None:
    p, log = setup(tmp_path, aliases={'schemaVersion': 1, 'aliases': {}})
    stage.hauling_stage(p, log, saved(tmp_path))
    stage.hauling_pr_stage(p, log, '-', dry_run=True)
    assert 'Lobby' in (p.out / 'hauling-pr-body.md').read_text(encoding='utf-8')
    assert gh.calls == [] and git.calls == []


def test_a_publish_leaves_the_alias_pr_open(gh: FakeGitHub, git: FakeGit) -> None:
    gh.prs += [{'number': 5, 'headRefName': 'data/hauling-aliases', 'state': 'open', 'title': '', 'body': ''},
               {'number': 6, 'headRefName': 'data/2026.11', 'state': 'open', 'title': '', 'body': ''}]
    assert workflow.close_superseded('release ships-2026.12', None) == [6]
    assert gh.prs[0]['state'] == 'open'
