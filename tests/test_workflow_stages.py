"""The workflow's own stages (T12.2): version, hygiene, previous, draft, publish, heartbeat, pr. gh and git are replaced
by an in-memory GitHub (shipdata.github), so these tests run without GitHub."""
import datetime as dt
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from conftest import CLEAN
from shipdata import github, manifest, stages, workflow
from shipdata.log import Reporter


def rel(tag: str, draft: bool = False, latest: bool = False) -> dict:
    return {'tagName': tag, 'isDraft': draft, 'isLatest': latest}


# ---------------------------------------------------------------- version (SD4)

@pytest.mark.parametrize('tags, expected', [
    ([], 'ships-2026.11'),
    (['ships-2026.11'], 'ships-2026.11.1'),
    (['ships-2026.11', 'ships-2026.11.1'], 'ships-2026.11.2'),
    (['ships-2026.11', 'ships-2026.11.9', 'ships-2026.11.10'], 'ships-2026.11.11'),
    (['ships-2026.10', 'ships-2026.10.1', 'holo-v3'], 'ships-2026.11'),
])
def test_next_version_counts_up_within_the_month(tags: list[str], expected: str) -> None:
    assert workflow.next_version(dt.date(2026, 11, 18), tags) == expected


def test_version_key_sorts_numerically() -> None:
    tags = ['ships-2026.11.10', 'ships-2026.11', 'ships-2026.12', 'ships-2026.11.9']
    assert sorted(tags, key=workflow.version_key) == ['ships-2026.11', 'ships-2026.11.9', 'ships-2026.11.10', 'ships-2026.12']


# ---------------------------------------------------------------- previous (E1)

def test_previous_is_the_highest_published_version_not_the_latest_flag() -> None:
    """E1: the latest flag can be set by hand or left wrong by a broken hygiene step; the version decides."""
    releases = [rel('ships-2026.11.9', latest=True), rel('ships-2026.11.10'), rel('ships-2026.11.11', draft=True),
                rel('holo-v3')]
    assert workflow.pick_previous(releases) == 'ships-2026.11.10'


def test_previous_without_a_data_release_is_an_error() -> None:
    with pytest.raises(workflow.WorkflowError, match='seed'):
        workflow.pick_previous([rel('ships-2026.11', draft=True)])


# ---------------------------------------------------------------- hygiene (SD4: the last two stay)

def test_hygiene_keeps_the_last_two_published_releases() -> None:
    releases = [rel('ships-2026.10'), rel('ships-2026.11'), rel('ships-2026.11.1'), rel('ships-2026.12', draft=True),
                rel('holo-v3')]
    assert workflow.to_delete(releases) == ['ships-2026.10']


def test_hygiene_deletes_nothing_with_two_releases() -> None:
    assert workflow.to_delete([rel('ships-2026.11'), rel('ships-2026.11.1')]) == []


def test_stale_drafts_are_every_data_draft() -> None:
    releases = [rel('ships-2026.11'), rel('ships-2026.11.1', draft=True), rel('other', draft=True)]
    assert workflow.stale_drafts(releases) == ['ships-2026.11.1']


# ---------------------------------------------------------------- a GitHub that lives in memory

class FakeGitHub:
    """Releases as gh shows them, kept in memory: list, create, upload, view (assets with size, digest, state),
    download, edit, delete, delete-asset. Every call is recorded."""

    def __init__(self) -> None:
        self.releases: dict[str, dict] = {}
        self.prs: list[dict] = []
        self.calls: list[tuple[str, ...]] = []

    def add(self, tag: str, folder: Path, draft: bool = False) -> None:
        self.releases[tag] = {'isDraft': draft, 'assets': {q.name: q.read_bytes() for q in sorted(folder.iterdir())}}

    def pr(self, args: tuple[str, ...]) -> str:
        sub = args[1]
        opt = lambda k: args[args.index(k) + 1] if k in args else None
        if sub == 'list':
            return json.dumps([{'number': x['number'], 'headRefName': x['headRefName']} for x in self.prs
                               if x['state'] == 'open' and opt('--head') in (None, x['headRefName'])])
        if sub == 'create':
            n = 10 + len(self.prs)
            self.prs.append({'number': n, 'headRefName': opt('--head'), 'state': 'open', 'title': opt('--title'),
                             'body': Path(opt('--body-file')).read_text(encoding='utf-8')})
            return f'https://github.com/o/r/pull/{n}\n'
        x = next(x for x in self.prs if x['number'] == int(args[2]))
        if sub == 'edit':
            x.update(title=opt('--title'), body=Path(opt('--body-file')).read_text(encoding='utf-8'))
        elif sub == 'close':
            x['state'] = 'closed'
        return ''

    def __call__(self, *args: str) -> str:
        self.calls.append(args)
        if args[0] == 'pr':
            return self.pr(args)
        sub = args[1]
        tag = args[2] if len(args) > 2 and not args[2].startswith('-') else None
        if sub == 'list':
            return json.dumps([{'tagName': t, 'isDraft': r['isDraft'], 'isLatest': False} for t, r in self.releases.items()])
        if sub == 'create':
            assert '--draft' in args
            self.releases[tag] = {'isDraft': True, 'assets': {}}
        elif sub == 'upload':
            for f in (a for a in args[3:] if not a.startswith('-')):
                self.releases[tag]['assets'][Path(f).name] = Path(f).read_bytes()
        elif sub == 'view':
            r = self.releases[tag]
            return json.dumps({'tagName': tag, 'isDraft': r['isDraft'], 'url': f'https://github.com/o/r/releases/tag/untagged-{tag}',
                               'assets': [
                {'name': n, 'size': len(b), 'digest': 'sha256:' + hashlib.sha256(b).hexdigest(), 'state': 'uploaded'}
                for n, b in sorted(r['assets'].items())]})
        elif sub == 'download':
            out = Path(args[args.index('--dir') + 1])
            out.mkdir(parents=True, exist_ok=True)
            pattern = args[args.index('--pattern') + 1] if '--pattern' in args else None
            for n, b in self.releases[tag]['assets'].items():
                if pattern in (None, n):
                    (out / n).write_bytes(b)
        elif sub == 'edit':
            if '--draft=false' in args:
                self.releases[tag]['isDraft'] = False
        elif sub == 'delete':
            del self.releases[tag]
        elif sub == 'delete-asset':
            del self.releases[tag]['assets'][args[3]]
        return ''

    def subs(self) -> list[str]:
        return [c[1] for c in self.calls if c[0] == 'release']


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(github, 'gh', fake)
    return fake


def release_folder(folder: Path, version: str, slugs: tuple[str, ...] = ('test-a', 'test-b'), models: str = 'TEST') -> Path:
    """The flat assets of a data release (SD4): manifest.json, NOTICE.md, ships.zip, <slug>.holo."""
    folder.mkdir(parents=True)
    ship_doc = json.dumps({'schemaVersion': 6, 'id': 'a', 'modelKey': 'test-a', 'racks': []}).encode()
    with zipfile.ZipFile(folder / 'ships.zip', 'w') as z:
        z.writestr('ships/a.json', ship_doc)
        z.writestr('outlines.json', b'{}')
    holo = {}
    for i, slug in enumerate(slugs):
        data = f'{slug}-{version}'.encode()
        (folder / f'{slug}.holo').write_bytes(data)
        holo[slug] = {'file': f'{slug}.holo', 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                      'model': f'{models}_{i}', 'rawSha256': f'{i}' * 64, 'budget': 20000, 'triangles': 1, 'edges': [1, 1, 1],
                      'passed': True, 'fails': [], 'metrics': dict(CLEAN)}
    (folder / 'NOTICE.md').write_text('notice', encoding='utf-8')
    m = {'dataVersion': version, 'schemaVersion': 6, 'generatedAt': '2026-11-18T00:00:00Z', 'builtFrom': {},
         'assets': {'ships': 'ships.zip'}, 'files': {'ships/a.json': hashlib.sha256(ship_doc).hexdigest(),
                                                     'outlines.json': hashlib.sha256(b'{}').hexdigest()},
         'holo': {'formatVersion': 2, 'ships': holo},
         'ships': {'a': {'source': None, 'modelKey': 'test-a', 'racksSha256': 'x', 'orderKeys': None, 'missingSince': None,
                         'follows': None}}}
    manifest.write(folder / 'manifest.json', m)
    return folder


def paths(tmp: Path) -> stages.Paths:
    root = tmp / 'root'
    root.mkdir(exist_ok=True)
    (root / 'NOTICE.md').write_text('notice', encoding='utf-8')
    return stages.Paths(root)


# ---------------------------------------------------------------- previous

def test_previous_downloads_the_highest_version_and_names_the_next(gh: FakeGitHub, tmp_path: Path) -> None:
    gh.add('ships-2026.11', release_folder(tmp_path / 'r0', 'ships-2026.11'))
    gh.add('ships-2026.12', release_folder(tmp_path / 'r1', 'ships-2026.12'), draft=True)
    p = paths(tmp_path)
    assert workflow.previous_stage(p, Reporter(p.out), dt.date(2026, 11, 18)) == 0
    info = json.loads(p.w('previous.json').read_text(encoding='utf-8'))
    assert (info['tag'], info['nextVersion']) == ('ships-2026.11', 'ships-2026.11.1')
    assert (p.w('previous-release') / 'test-a.holo').read_bytes() == b'test-a-ships-2026.11'


def test_previous_refuses_a_hologram_that_differs_from_its_manifest(gh: FakeGitHub, tmp_path: Path) -> None:
    gh.add('ships-2026.11', release_folder(tmp_path / 'r0', 'ships-2026.11'))
    gh.releases['ships-2026.11']['assets']['test-b.holo'] = b'changed'
    p = paths(tmp_path)
    with pytest.raises(workflow.WorkflowError, match='test-b.holo'):
        workflow.previous_stage(p, Reporter(p.out), dt.date(2026, 11, 18))


# ---------------------------------------------------------------- draft

def test_draft_uploads_the_manifest_last_and_never_publishes(gh: FakeGitHub, tmp_path: Path) -> None:
    gh.add('ships-2026.11', release_folder(tmp_path / 'r0', 'ships-2026.11'))
    gh.add('ships-2026.11.1', release_folder(tmp_path / 'old-draft', 'ships-2026.11.1'), draft=True)
    p = paths(tmp_path)
    folder = release_folder(tmp_path / 'new', 'ships-2026.11.1')
    assert workflow.draft_stage(p, Reporter(p.out), folder, target='f' * 40) == 0
    uploads = [c for c in gh.calls if c[1] == 'upload']
    assert [a for a in uploads[-1][3:] if not a.startswith('-')] == [str(folder / 'manifest.json')]
    assert all('manifest.json' not in ' '.join(c) for c in uploads[:-1])
    assert gh.subs().index('delete') < gh.subs().index('create')         # the earlier run's draft goes first
    assert 'edit' not in gh.subs()
    assert gh.releases['ships-2026.11.1']['isDraft'] is True
    assert sorted(gh.releases['ships-2026.11.1']['assets']) == ['NOTICE.md', 'manifest.json', 'ships.zip', 'test-a.holo', 'test-b.holo']


def test_draft_refuses_a_version_that_is_published_already(gh: FakeGitHub, tmp_path: Path) -> None:
    gh.add('ships-2026.11', release_folder(tmp_path / 'r0', 'ships-2026.11'))
    p = paths(tmp_path)
    with pytest.raises(workflow.WorkflowError, match='published'):
        workflow.draft_stage(p, Reporter(p.out), release_folder(tmp_path / 'new', 'ships-2026.11'), target='f' * 40)
    assert 'create' not in gh.subs()


# ---------------------------------------------------------------- publish

def published_setup(gh: FakeGitHub, tmp: Path) -> stages.Paths:
    for i, v in enumerate(('ships-2026.10', 'ships-2026.11')):
        gh.add(v, release_folder(tmp / f'r{i}', v))
    draft = release_folder(tmp / 'draft', 'ships-2026.11.1', models='NEW')
    (draft / 'contact-sheet-1.png').write_bytes(b'png')
    gh.add('ships-2026.11.1', draft, draft=True)
    return paths(tmp)


def test_publish_checks_the_draft_then_publishes_cleans_up_and_prunes(gh: FakeGitHub, tmp_path: Path) -> None:
    p = published_setup(gh, tmp_path)
    p.models.mkdir(parents=True)
    for name in ('NEW_0-000000000000.glb', 'NEW_0-999999999999.glb', 'NEW_1-111111111111.glb', 'GONE-aaaaaaaaaaaa.glb'):
        (p.models / name).write_bytes(b'm')
    assert workflow.publish_stage(p, Reporter(p.out), 'ships-2026.11.1', None, target='e' * 40) == 0
    subs = gh.subs()
    assert subs.index('delete-asset') < subs.index('edit')
    edit = next(c for c in gh.calls if c[1] == 'edit')
    assert {'--draft=false', '--latest', '--target'} <= set(edit) and 'e' * 40 in edit
    assert gh.releases['ships-2026.11.1']['isDraft'] is False
    assert 'contact-sheet-1.png' not in gh.releases['ships-2026.11.1']['assets']
    assert sorted(gh.releases) == ['ships-2026.11', 'ships-2026.11.1']                       # the last two stay
    assert ('release', 'delete', 'ships-2026.10', '--cleanup-tag', '--yes') in gh.calls
    # condition B: older hashes of the published models go, other classes stay for a rollback
    assert sorted(q.name for q in p.models.iterdir()) == ['GONE-aaaaaaaaaaaa.glb', 'NEW_0-000000000000.glb', 'NEW_1-111111111111.glb']


def test_publish_stops_before_publishing_a_draft_with_fewer_assets_than_its_manifest(gh: FakeGitHub, tmp_path: Path) -> None:
    """Martin, 18 Nov: an upload cut off in an earlier run leaves a draft without some assets. publish must stop
    before --draft=false: no half release behind releases/latest."""
    p = published_setup(gh, tmp_path)
    del gh.releases['ships-2026.11.1']['assets']['test-b.holo']
    with pytest.raises(workflow.WorkflowError, match='test-b.holo'):
        workflow.publish_stage(p, Reporter(p.out), 'ships-2026.11.1', None, target='e' * 40)
    assert 'edit' not in gh.subs() and 'delete' not in gh.subs() and 'delete-asset' not in gh.subs()
    assert gh.releases['ships-2026.11.1']['isDraft'] is True


def test_publish_stops_before_publishing_a_draft_without_its_manifest(gh: FakeGitHub, tmp_path: Path) -> None:
    """The manifest goes up last: an upload cut off earlier leaves a draft without it."""
    p = published_setup(gh, tmp_path)
    del gh.releases['ships-2026.11.1']['assets']['manifest.json']
    with pytest.raises(workflow.WorkflowError, match='manifest.json'):
        workflow.publish_stage(p, Reporter(p.out), 'ships-2026.11.1', None, target='e' * 40)
    assert 'edit' not in gh.subs()


def test_publish_stops_on_an_asset_whose_digest_differs(gh: FakeGitHub, tmp_path: Path) -> None:
    p = published_setup(gh, tmp_path)
    gh.releases['ships-2026.11.1']['assets']['test-a.holo'] = b'test-a-ships-X.11.1'      # same size, other bytes
    with pytest.raises(workflow.WorkflowError, match='test-a.holo'):
        workflow.publish_stage(p, Reporter(p.out), 'ships-2026.11.1', None, target='e' * 40)
    assert 'edit' not in gh.subs()


def test_draft_problems_names_unfinished_and_unknown_assets() -> None:
    m = {'assets': {'ships': 'ships.zip'}, 'holo': {'ships': {'a': {'file': 'a.holo', 'bytes': 1, 'sha256': '0' * 64}}}}
    ok = 'sha256:' + '0' * 64
    assets = [{'name': 'manifest.json', 'size': 1, 'digest': ok, 'state': 'uploaded'},
              {'name': 'NOTICE.md', 'size': 1, 'digest': ok, 'state': 'uploaded'},
              {'name': 'ships.zip', 'size': 1, 'digest': ok, 'state': 'starter'},
              {'name': 'a.holo', 'size': 1, 'digest': ok, 'state': 'uploaded'},
              {'name': 'stray.bin', 'size': 1, 'digest': ok, 'state': 'uploaded'},
              {'name': 'contact-sheet-1.png', 'size': 1, 'digest': ok, 'state': 'uploaded'}]
    assert workflow.draft_problems(assets, m) == ['ships.zip: upload not finished (state starter)',
                                                 'stray.bin: not an asset of this release']


def test_publish_after_a_merge_needs_the_draft_the_pr_named(gh: FakeGitHub, tmp_path: Path) -> None:
    """P6: state/pending.json carries the draft's manifest SHA-256; another draft under the same tag is not published."""
    p = published_setup(gh, tmp_path)
    pending = tmp_path / 'pending.json'
    pending.write_text(json.dumps({'tag': 'ships-2026.11.1', 'manifestSha256': '0' * 64}), encoding='utf-8')
    with pytest.raises(workflow.WorkflowError, match='pending'):
        workflow.publish_stage(p, Reporter(p.out), None, pending, target='e' * 40)
    assert 'edit' not in gh.subs()
    real = hashlib.sha256(gh.releases['ships-2026.11.1']['assets']['manifest.json']).hexdigest()
    pending.write_text(json.dumps({'tag': 'ships-2026.11.1', 'manifestSha256': real}), encoding='utf-8')
    assert workflow.publish_stage(p, Reporter(p.out), None, pending, target='e' * 40) == 0
    assert gh.releases['ships-2026.11.1']['isDraft'] is False
