"""heartbeat (SD9: every run commits state/last-run.json, with one line Martin reads without the log) and pr (the PR
whose merge publishes the draft, P6; its text only from the fields of verify.json, diff.json and gate.json, E1)."""
import json
from pathlib import Path

import pytest

from shipdata import github, workflow
from shipdata.log import Reporter
from test_workflow_stages import FakeGitHub, paths, release_folder

F7C = {'rule': 'judge', 'id': 'anvl-hornet-f7c-mk2', 'stop': True, 'proposal': None,
       'detail': 'SD5 case 4: no comparable hologram (fleetyards (holo-v1) -> ANVL_Hornet_F7C_Mk2)',
       'data': {'cases': [4], 'model': {'old': 'fleetyards (holo-v1)', 'new': 'ANVL_Hornet_F7C_Mk2'},
                'passed': {'old': True, 'new': True}, 'fails': {'old': [], 'new': []},
                'hausdorff': {'old': 0.004, 'new': 0.0031, 'delta': -0.0009, 'tolerance': 0.0025},
                'triangles': {'old': 18000, 'new': 19876}, 'budget': {'old': 20000, 'new': 20000}}}
HYUN = {'rule': 'judge', 'id': 'gama-hyun', 'stop': True, 'proposal': None, 'detail': 'SD5 case 4: new ship',
        'data': {'cases': [4], 'model': {'old': None, 'new': 'GAMA_Hyun'}, 'passed': {'old': None, 'new': True},
                 'fails': {'old': None, 'new': []}, 'hausdorff': {'old': None, 'new': 0.002, 'delta': None, 'tolerance': 0.0025},
                 'triangles': {'old': None, 'new': 9000}, 'budget': {'old': None, 'new': 20000}}}
ORDER = {'rule': 'order', 'id': 'alpha', 'stop': True, 'proposal': None, 'detail': 'grids in another order', 'data': None}
IDRIS = {'rule': 'judge', 'id': 'aegs-idris-m', 'stop': False, 'proposal': None,
         'detail': 'fails hausdorff, comparable to the last release', 'data': {'cases': []}}
VARIANT = {'rule': 'variant', 'id': 'mole_carbon_edition', 'stop': False, 'proposal': None,
           'detail': 'gone, takes the data of mole (racks were equal)', 'data': None}
VERIFY = {'findings': [F7C, HYUN, ORDER, IDRIS, VARIANT], 'stop': True, 'files': {'same': 10, 'of': 110},
          'holo': {'built': 98, 'byteEqualToPrevious': 2, 'unavailable': {}}}
DIFF = {'ships': {'changed': ['f7c_hornet_mk_ii'], 'new': ['hyun'], 'gone': ['mole_carbon_edition'], 'stillGone': ['cyclone'],
                  'back': [], 'same': ['alpha']},
        'models': {'changed': [f'M{i}' for i in range(96)], 'new': ['GAMA_Hyun', 'ANVL_Hornet_F7C_Mk2'], 'same': [],
                   'without_url': ['Cyclone'], 'unused': []}}
GATE = {'pictures': {'equal': 1300, 'different': 120, 'missing': 0}, 'unexpected': [], 'expectedShips': 99,
        'sheets': ['contact-sheet-1.png']}


# ---------------------------------------------------------------- the one line (SD9)

def test_counts_from_diff_and_verify() -> None:
    assert workflow.counts(DIFF, VERIFY) == {'changed': 1, 'new': 1, 'gone': 1, 'holosRefreshed': 96, 'findings': 3}


@pytest.mark.parametrize('result, kw, line', [
    ('release', {'tag': 'ships-2026.11.1', 'counts': {'changed': 1, 'new': 1, 'gone': 0, 'holosRefreshed': 96}},
     'Release ships-2026.11.1: 1 ship changed, 1 new, 96 holos refreshed'),
    ('release', {'tag': 'ships-2026.12', 'counts': {'changed': 2, 'new': 0, 'gone': 6, 'holosRefreshed': 1}},
     'Release ships-2026.12: 2 ships changed, 0 new, 6 gone, 1 holo refreshed'),
    ('pr', {'pr': 12, 'counts': {'findings': 2}}, 'PR #12: 2 findings'),
    ('pr', {'pr': 12, 'counts': {'findings': 1}}, 'PR #12: 1 finding'),
    ('nothing', {}, 'nothing changed'),
    ('gate-red', {'unexpected': ['a', 'b', 'c']}, 'gate red: 3 ships differ unexpectedly (a, b, c)'),
    ('error', {'error': 'in build: chain failed for x'}, 'error in build: chain failed for x'),
])
def test_summary_line(result: str, kw: dict, line: str) -> None:
    assert workflow.summary_line(result, **kw) == line


def needs(**jobs: tuple[str, dict]) -> dict:
    return {j: {'result': r, 'outputs': o} for j, (r, o) in jobs.items()}


@pytest.mark.parametrize('event, jobs, result', [
    ('workflow_dispatch', needs(chain=('success', {'changed': 'false'})), 'nothing'),
    ('schedule', needs(chain=('success', {'changed': 'true', 'path': 'release', 'tag': 'ships-2026.12'}), gate=('success', {}),
                       publish=('success', {'published': 'ships-2026.12'}), pr=('skipped', {})), 'release'),
    ('workflow_dispatch', needs(chain=('success', {'changed': 'true', 'path': 'pr', 'tag': 'ships-2026.11.1'}),
                                gate=('success', {}), publish=('skipped', {}), pr=('success', {'pr': '12'})), 'pr'),
    ('workflow_dispatch', needs(chain=('success', {'changed': 'true', 'path': 'pr', 'tag': 'ships-2026.11.1'}),
                                gate=('failure', {}), publish=('skipped', {}), pr=('skipped', {})), 'gate-red'),
    ('workflow_dispatch', needs(chain=('failure', {})), 'error'),
    ('workflow_dispatch', needs(chain=('success', {'changed': 'true', 'path': 'release', 'tag': 'ships-2026.12'}),
                                gate=('success', {}), publish=('failure', {}), pr=('skipped', {})), 'error'),
    ('push', needs(**{'publish-merged': ('success', {'published': 'ships-2026.11.1'})}), 'release'),
    ('push', needs(**{'publish-merged': ('failure', {})}), 'error'),
])
def test_outcome_of_a_run(event: str, jobs: dict, result: str) -> None:
    """SD11: a run ends with nothing, a release or a PR - or red (an error, a red gate)."""
    assert workflow.outcome(jobs, event)['result'] == result


# ---------------------------------------------------------------- heartbeat

class FakeGit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str, cwd: Path) -> str:
        self.calls.append(args)
        return ''

    def verbs(self) -> list[str]:
        return [next(a for a in c if not a.startswith('-') and '=' not in a) for c in self.calls]


@pytest.fixture
def git(monkeypatch: pytest.MonkeyPatch) -> FakeGit:
    fake = FakeGit()
    monkeypatch.setattr(github, 'git', fake)
    return fake


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(github, 'gh', fake)
    return fake


def reports(p, verify: dict | None = VERIFY, diff: dict | None = DIFF, gate: dict | None = GATE) -> None:
    for name, doc in (('verify.json', verify), ('diff.json', diff), ('gate.json', gate)):
        if doc is not None:
            workflow.save_json(p.w(name), doc)


def test_heartbeat_writes_last_run_and_commits_it(git: FakeGit, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('GITHUB_JOB', 'chain')
    p = paths(tmp_path)
    reports(p)
    Reporter(p.out).say('diff', 'catalog against ships-2026.11', '1 changed', 'build')
    jobs = needs(chain=('success', {'changed': 'true', 'path': 'pr', 'tag': 'ships-2026.11.1', 'previous': 'ships-2026.11'}),
                 gate=('success', {}), publish=('skipped', {}), pr=('success', {'pr': '12'}))
    assert workflow.heartbeat_stage(p, Reporter(p.out), jobs, 'workflow_dispatch', '44', 'https://x/runs/44', '2026-11-19') == 0
    doc = json.loads((p.root / 'state' / 'last-run.json').read_text(encoding='utf-8'))
    assert (doc['result'], doc['line'], doc['runId'], doc['date']) == ('pr', 'PR #12: 3 findings', '44', '2026-11-19')
    assert (doc['dataVersion'], doc['previous']) == ('ships-2026.11.1', 'ships-2026.11')
    assert doc['stages'][0] == {'job': 'chain', 'step': 'diff', 'checked': 'catalog against ships-2026.11', 'found': '1 changed', 'todo': 'build'}
    assert git.verbs() == ['add', 'commit', 'pull', 'push']
    assert 'rm' not in git.verbs()


def test_heartbeat_after_the_merge_removes_pending(git: FakeGit, tmp_path: Path) -> None:
    p = paths(tmp_path)
    (p.root / 'state').mkdir()
    workflow.save_json(p.root / 'state' / 'pending.json',
                       {'tag': 'ships-2026.11.1', 'manifestSha256': '0' * 64,
                        'counts': {'changed': 1, 'new': 1, 'gone': 6, 'holosRefreshed': 96, 'findings': 3}})
    jobs = needs(**{'publish-merged': ('success', {'published': 'ships-2026.11.1'})})
    workflow.heartbeat_stage(p, Reporter(p.out), jobs, 'push', '45', 'https://x/runs/45', '2026-11-19')
    doc = json.loads((p.root / 'state' / 'last-run.json').read_text(encoding='utf-8'))
    assert doc['line'] == 'Release ships-2026.11.1: 1 ship changed, 1 new, 6 gone, 96 holos refreshed'
    assert ('rm', '-q', '--ignore-unmatch', 'state/pending.json') in git.calls


def test_heartbeat_names_the_failing_stage(git: FakeGit, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('GITHUB_JOB', 'chain')
    p = paths(tmp_path)
    Reporter(p.out).say('fetch', 'catalog', 'error: SourceError: API answered HTTP 503', 'fix the cause; nothing was released')
    workflow.heartbeat_stage(p, Reporter(p.out), needs(chain=('failure', {})), 'schedule', '46', 'u', '2026-12-01')
    doc = json.loads((p.root / 'state' / 'last-run.json').read_text(encoding='utf-8'))
    assert (doc['result'], doc['line']) == ('error', 'error in fetch: SourceError: API answered HTTP 503')


# ---------------------------------------------------------------- pr

def test_pr_text_comes_from_the_fields() -> None:
    body = workflow.pr_body('ships-2026.11.1', 'a' * 64, 'https://draft', 'https://run', DIFF, VERIFY, GATE)
    rows = [line for line in body.splitlines() if line.startswith('| ') and not line.startswith('| Ship')]
    assert len(rows) == 3                                                       # one row per stop
    f7c = next(r for r in rows if 'anvl-hornet-f7c-mk2' in r)
    for part in ('SD5 case 4', 'fleetyards (holo-v1) → ANVL_Hornet_F7C_Mk2', '0.0040 → 0.0031 (-0.0009, tolerance 0.0025)',
                 '18000 → 19876 / 20000'):
        assert part in f7c, part
    assert '– → GAMA_Hyun' in next(r for r in rows if 'gama-hyun' in r)
    assert 'Merge = approval' in body and 'aaaaaaaaaaaa' in body and 'https://draft' in body
    assert '1300 equal, 120 different, 0 unexpected' in body
    assert '2 notes' in body and 'mole_carbon_edition' in body


def test_grid_findings_carry_the_motherlode_hint() -> None:
    """Master chat, 18 Nov: grid data comes from Motherlode, which asks for reports of grids that look wrong in-game."""
    body = workflow.pr_body('ships-2026.11.1', 'a' * 64, 'u', 'u', DIFF, VERIFY, GATE)
    hint = next(line for line in body.splitlines() if 'Motherlode' in line and 'report' in line)
    assert '`alpha`' in hint and 'gama-hyun' not in hint
    clean = dict(VERIFY, findings=[F7C, HYUN])
    assert not any('Motherlode' in line and 'report' in line
                   for line in workflow.pr_body('t', 'a' * 64, 'u', 'u', DIFF, clean, GATE).splitlines())


def test_pr_commits_pending_and_proposed_overrides_and_opens_the_pr(gh: FakeGitHub, git: FakeGit, tmp_path: Path) -> None:
    gh.add('ships-2026.11.1', release_folder(tmp_path / 'draft', 'ships-2026.11.1'), draft=True)
    gh.prs.append({'number': 3, 'headRefName': 'data/2026.10', 'state': 'open', 'title': 'old', 'body': ''})
    p = paths(tmp_path)
    reports(p)
    workflow.save_json(p.w('overrides-proposed.json'), {'ships': [{'id': 'kept', 'reason': 'r', 'date': '2026-11-19'}]})
    assert workflow.pr_stage(p, Reporter(p.out), 'ships-2026.11.1', '44', 'https://run', dry_run=False) == 0
    pending = json.loads((p.root / 'state' / 'pending.json').read_text(encoding='utf-8'))
    manifest_sha = __import__('hashlib').sha256(gh.releases['ships-2026.11.1']['assets']['manifest.json']).hexdigest()
    assert (pending['tag'], pending['manifestSha256'], pending['counts']['findings']) == ('ships-2026.11.1', manifest_sha, 3)
    assert json.loads((p.root / 'overrides.json').read_text(encoding='utf-8'))['ships'][0]['id'] == 'kept'
    assert git.calls[0] == ('switch', '-C', 'data/2026.11')
    assert ('push', '--force', 'origin', 'data/2026.11') in git.calls
    add = next(c for c in git.calls if c[0] == 'add')
    assert set(add[1:]) == {'state/pending.json', 'overrides.json'}
    new = next(x for x in gh.prs if x['headRefName'] == 'data/2026.11')
    assert new['state'] == 'open' and 'Merge = approval' in new['body']
    assert next(x for x in gh.prs if x['number'] == 3)['state'] == 'closed'           # superseded


def test_pr_without_proposals_commits_pending_only_and_updates_an_open_pr(gh: FakeGitHub, git: FakeGit, tmp_path: Path) -> None:
    gh.add('ships-2026.11.1', release_folder(tmp_path / 'draft', 'ships-2026.11.1'), draft=True)
    gh.prs.append({'number': 7, 'headRefName': 'data/2026.11', 'state': 'open', 'title': 'old', 'body': 'old'})
    p = paths(tmp_path)
    reports(p, gate=None)
    workflow.pr_stage(p, Reporter(p.out), 'ships-2026.11.1', '44', 'https://run', dry_run=False)
    assert next(c for c in git.calls if c[0] == 'add')[1:] == ('state/pending.json',)
    assert not (p.root / 'overrides.json').exists()
    assert [x['number'] for x in gh.prs] == [7] and gh.prs[0]['body'] != 'old'


def test_pr_dry_run_writes_the_text_only(gh: FakeGitHub, git: FakeGit, tmp_path: Path) -> None:
    p = paths(tmp_path)
    reports(p)
    workflow.pr_stage(p, Reporter(p.out), 'ships-2026.11.1', '-', '-', dry_run=True)
    assert 'Merge = approval' in (p.out / 'pr-body.md').read_text(encoding='utf-8')
    assert gh.calls == [] and git.calls == []


def test_a_direct_publish_closes_open_data_prs(gh: FakeGitHub, git: FakeGit, tmp_path: Path) -> None:
    """Their drafts were replaced by this run's: merging them could only fail."""
    gh.add('ships-2026.11', release_folder(tmp_path / 'r0', 'ships-2026.11'))
    gh.add('ships-2026.12', release_folder(tmp_path / 'd', 'ships-2026.12'), draft=True)
    gh.prs.append({'number': 7, 'headRefName': 'data/2026.11', 'state': 'open', 'title': '', 'body': ''})
    p = paths(tmp_path)
    workflow.publish_stage(p, Reporter(p.out), 'ships-2026.12', None, target='e' * 40)
    assert gh.prs[0]['state'] == 'closed'
