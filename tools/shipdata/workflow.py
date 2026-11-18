"""The workflow's stages around the chain (T12.2, docs/plans/T12.2-workflow.md): the last release (previous), the draft
release that carries a run's assets until it is published (draft, SD10), publishing it (publish), the PR for Martin's
merge (pr) and the heartbeat commit (heartbeat, SD9). Pure functions first; gh and git only through shipdata.github.

Release names (SD4): ships-YYYY.MM, a second release in the same month ships-YYYY.MM.1, .2, ... Order is by version,
never by GitHub's latest flag (E1): the flag can be set by hand."""
import datetime as dt
import json
import re
import shutil
from pathlib import Path

from shipdata import fetch, github, manifest, release
from shipdata.log import Reporter

VERSION = re.compile(r'^ships-(?P<year>\d{4})\.(?P<month>\d{2})(?:\.(?P<n>\d+))?$')
KEEP = 2                    # published data releases that stay (SD4)
CONTACT_SHEET = re.compile(r'^contact-sheet-\d+\.png$')     # the gate's pictures on a draft, removed before publishing
CLASS_NAME = re.compile(r'^[A-Za-z0-9_]+$')


class WorkflowError(RuntimeError):
    pass


def version_key(tag: str) -> tuple[int, int, int]:
    """ships-2026.11 -> (2026, 11, 0), ships-2026.11.10 -> (2026, 11, 10): .10 sorts after .9."""
    m = VERSION.match(tag)
    if not m:
        raise WorkflowError(f'{tag!r} is not a data release name (ships-YYYY.MM[.N])')
    return int(m['year']), int(m['month']), int(m['n'] or 0)


def next_version(day: dt.date, tags: list[str]) -> str:
    """The release name for a run on `day`: ships-YYYY.MM, or the next free .N if that month has one already."""
    base = f'ships-{day:%Y.%m}'
    taken = [version_key(t)[2] for t in tags if t == base or t.startswith(base + '.') and VERSION.match(t)]
    return base if not taken else f'{base}.{max(taken) + 1}'


def published(releases: list[dict]) -> list[str]:
    """Tags of the published data releases (gh release list --json tagName,isDraft), oldest version first."""
    return sorted((r['tagName'] for r in releases if not r['isDraft'] and VERSION.match(r['tagName'])), key=version_key)


def pick_previous(releases: list[dict]) -> str:
    """The last release a run compares with: the highest published version (E1), not isLatest."""
    tags = published(releases)
    if not tags:
        raise WorkflowError('no data release yet: upload the seed first (run.py release --seed, draft, publish)')
    return tags[-1]


def to_delete(releases: list[dict], keep: int = KEEP) -> list[str]:
    """Hygiene after a publish (SD4): every published data release but the last `keep`; drafts and other tags stay."""
    tags = published(releases)
    return tags[:-keep] if len(tags) > keep else []


def stale_drafts(releases: list[dict]) -> list[str]:
    """Every data draft: a new run replaces the draft of an earlier one (its PR is superseded)."""
    return sorted(r['tagName'] for r in releases if r['isDraft'] and VERSION.match(r['tagName']))


def expected_assets(m: dict) -> dict[str, tuple[int | None, str | None]]:
    """The flat assets of a release (SD4) by name, with size and SHA-256 where the manifest names them (holograms)."""
    out: dict[str, tuple[int | None, str | None]] = {'manifest.json': (None, None), 'NOTICE.md': (None, None),
                                                     m['assets']['ships']: (None, None)}
    for e in ((m.get('holo') or {}).get('ships') or {}).values():
        out[e['file']] = (e['bytes'], e['sha256'])
    return out


def draft_problems(assets: list[dict], m: dict) -> list[str]:
    """A release's assets as gh shows them (gh release view --json assets: name, size, digest 'sha256:...', state)
    against its manifest. Missing, unfinished (state other than 'uploaded', an upload cut off) or different assets are
    problems, so are assets the release does not have - except the gate's contact sheets on a draft."""
    want, have = expected_assets(m), {a['name']: a for a in assets}
    problems = []
    for name in sorted(want):
        a = have.get(name)
        size, sha = want[name]
        if a is None:
            problems.append(f'{name}: missing')
        elif a.get('state') != 'uploaded':
            problems.append(f"{name}: upload not finished (state {a.get('state')})")
        elif size is not None and a['size'] != size:
            problems.append(f"{name}: {a['size']} bytes, the manifest says {size}")
        elif sha is not None and a.get('digest') and a['digest'] != f'sha256:{sha}':
            problems.append(f'{name}: digest differs from the manifest')
    problems += [f'{n}: not an asset of this release' for n in sorted(have) if n not in want and not CONTACT_SHEET.match(n)]
    return problems


def holo_problems(folder: Path, m: dict) -> list[str]:
    """The holograms of a release folder against its manifest (size and SHA-256)."""
    out = []
    for e in sorted(((m.get('holo') or {}).get('ships') or {}).values(), key=lambda e: e['file']):
        q = folder / e['file']
        if not q.exists():
            out.append(f"{e['file']}: missing")
        elif q.stat().st_size != e['bytes'] or manifest.sha256(q) != e['sha256']:
            out.append(f"{e['file']}: size or SHA-256 differs from the manifest")
    return out


def model_files(m: dict) -> set[str]:
    """The model files a release was built from (<className>-<first 12 hex of rawSha256>.glb, as the bucket names them):
    what the model cache keeps after publishing (condition B)."""
    return {f"{e['model']}-{e['rawSha256'][:12]}.glb" for e in ((m.get('holo') or {}).get('ships') or {}).values()
            if CLASS_NAME.match(e.get('model') or '') and e.get('rawSha256')}


def releases() -> list[dict]:
    return github.gh_json('release', 'list', '--limit', '200', '--json', 'tagName,isDraft,isLatest')


def save_json(path: Path, doc: object) -> None:
    path.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')


# ---------------------------------------------------------------- previous

def previous_stage(p, log: Reporter, today: dt.date) -> int:
    """The last release for diff and verify: every asset of the highest published version (E1), checked against its
    manifest; the name of this run's release (the manifest's dataVersion, so it is known before build)."""
    rels = releases()
    tag = pick_previous(rels)
    flagged = [r['tagName'] for r in rels if r.get('isLatest')]
    into = p.w('previous-release')
    if into.exists():
        shutil.rmtree(into)
    github.gh('release', 'download', tag, '--dir', str(into))
    m = manifest.read(into / 'manifest.json')
    if m['dataVersion'] != tag:
        raise WorkflowError(f"{tag}: its manifest says dataVersion {m['dataVersion']}")
    release.unpack(into, p.w('previous'))       # ships.zip against files (boundary: a release asset)
    problems = holo_problems(into, m)
    if problems:
        raise WorkflowError(f'{tag} differs from its manifest: {"; ".join(problems[:8])}')
    nxt = next_version(today, published(rels))
    save_json(p.w('previous.json'), {'tag': tag, 'nextVersion': nxt, 'latestFlag': flagged})
    holos = len(((m.get('holo') or {}).get('ships') or {}))
    total = sum(q.stat().st_size for q in into.iterdir())
    log.output('previous', tag)
    log.output('version', nxt)
    log.num('previous.bytes', total)
    log.say('previous', f'published data releases ({len(published(rels))}); {tag}: every asset against its manifest',
            f"{tag}: {len(list(into.iterdir()))} assets, {total} bytes, {holos} holograms, {m['assets']['ships']} unpacked; "
            f'this run releases as {nxt}' + ('' if flagged == [tag] else f"; note: GitHub's latest flag is on {flagged or 'none'}, "
                                             'the version decides (E1)'),
            'none')
    return 0


# ---------------------------------------------------------------- draft

def draft_stage(p, log: Reporter, folder: Path | None, target: str) -> int:
    """The draft release (SD10): created as a draft, holograms, ships.zip and NOTICE.md up, manifest.json last, then
    its assets checked against the manifest. Never published here. The tag is the manifest's dataVersion; drafts of
    earlier runs go first. folder: a packed release folder (the seed); default: pack work/stage to out/release."""
    if folder is None:
        folder = p.out / 'release'
        release.pack(p.w('stage'), folder, p.root / 'NOTICE.md')
    m = manifest.read(folder / 'manifest.json')
    tag = m['dataVersion']
    version_key(tag)
    problems = holo_problems(folder, m)
    if problems:
        raise WorkflowError(f'{folder} differs from its manifest: {"; ".join(problems[:8])}')
    release.unpack(folder, p.w('draft-check'))
    rels = releases()
    if tag in published(rels):
        raise WorkflowError(f'{tag} is published already: a run names its release in previous (work/previous.json)')
    stale = stale_drafts(rels)
    for t in stale:
        github.gh('release', 'delete', t, '--yes')
    motherlode = (m.get('builtFrom') or {}).get('motherlode') or {}
    notes = p.out / 'release-notes.md'
    notes.write_text(f"Ship data {tag} for SC-CargoPlan, built from Motherlode {motherlode.get('gameBuild', '?')} "
                     f"({motherlode.get('updatedAt', '?')}).\n\nShip data and holograms are CIG material under "
                     'NOTICE.md, not MIT. The app reads manifest.json.\n', encoding='utf-8', newline='\n')
    github.gh('release', 'create', tag, '--draft', '--target', target, '--title', tag, '--notes-file', str(notes))
    first = sorted(str(q) for q in folder.iterdir() if q.is_file() and q.name != 'manifest.json')
    github.gh('release', 'upload', tag, *first, '--clobber')
    github.gh('release', 'upload', tag, str(folder / 'manifest.json'), '--clobber')
    view = github.gh_json('release', 'view', tag, '--json', 'assets,isDraft')
    problems = draft_problems(view['assets'], m)
    if problems:
        raise WorkflowError(f'draft {tag} differs from its manifest after the upload: {"; ".join(problems[:8])}')
    sha = manifest.sha256(folder / 'manifest.json')
    log.output('tag', tag)
    log.output('manifest', sha)
    log.num('draft.assets', len(view['assets']))
    log.say('draft', f'{folder} against its manifest; draft {tag} (target {target[:12]}), manifest.json uploaded last',
            f"{len(view['assets'])} assets uploaded and checked against the manifest (manifest {sha[:12]}); "
            f"{len(stale)} drafts of earlier runs deleted ({', '.join(stale) or '-'})",
            'none: the gate renders the draft; it is published only after a green gate (or a merged PR)')
    return 0


# ---------------------------------------------------------------- publish

def publish_stage(p, log: Reporter, tag: str | None, pending: Path | None, target: str) -> int:
    """Publish a draft (after a green gate, or after Martin's merge of the PR that names it): its assets against its
    manifest first - missing, unfinished or different assets stop here, before --draft=false, so releases/latest never
    shows half a release. Then the contact sheets go, the draft is published as latest, releases beyond the last two
    are deleted (SD4) and the model cache keeps the published release's models (condition B)."""
    doc = json.loads(pending.read_text(encoding='utf-8')) if pending else None
    tag = doc['tag'] if doc else tag
    if not tag:
        raise WorkflowError('publish needs --tag or --pending')
    view = github.gh_json('release', 'view', tag, '--json', 'assets,isDraft,tagName')
    if not view['isDraft']:
        raise WorkflowError(f'{tag} is published already')
    names = {a['name'] for a in view['assets']}
    if 'manifest.json' not in names:
        raise WorkflowError(f'draft {tag}: manifest.json missing (uploaded last; an upload cut off?): not published')
    tmp = p.w('publish')
    if tmp.exists():
        shutil.rmtree(tmp)
    github.gh('release', 'download', tag, '--pattern', 'manifest.json', '--dir', str(tmp))
    m = manifest.read(tmp / 'manifest.json')
    sha = manifest.sha256(tmp / 'manifest.json')
    if doc and doc['manifestSha256'] != sha:
        raise WorkflowError(f"draft {tag}: manifest {sha[:12]}, state/pending.json names {doc['manifestSha256'][:12]}: "
                            'not the draft the PR showed, not published')
    if m['dataVersion'] != tag:
        raise WorkflowError(f"draft {tag}: its manifest says dataVersion {m['dataVersion']}")
    problems = draft_problems(view['assets'], m)
    if problems:
        raise WorkflowError(f'draft {tag} is not complete, not published: {"; ".join(problems[:8])}')
    sheets = sorted(n for n in names if CONTACT_SHEET.match(n))
    for n in sheets:
        github.gh('release', 'delete-asset', tag, n, '--yes')
    github.gh('release', 'edit', tag, '--target', target, '--draft=false', '--latest')
    gone = to_delete(releases())
    for t in gone:
        github.gh('release', 'delete', t, '--cleanup-tag', '--yes')
    superseded = close_superseded(f'release {tag}', None)
    keep = model_files(m)
    removed = fetch.prune_models(p.models, keep) if p.models.exists() else []
    cache = sum(q.stat().st_size for q in p.models.glob('*.glb')) if p.models.exists() else 0
    log.output('published', tag)
    log.num('publish.assets', len(names) - len(sheets))
    log.num('publish.cache.bytes', cache)
    log.say('publish', f"draft {tag}: {len(names) - len(sheets)} assets against its manifest"
            + (' and state/pending.json' if doc else ''),
            f'published {tag} as latest (target {target[:12]}); {len(sheets)} contact sheets removed; '
            f"{len(gone)} old releases deleted ({', '.join(gone) or '-'}); model cache: {len(removed)} older hashes removed, "
            f'{cache} bytes left; {len(superseded)} open data PRs closed as superseded',
            'none')
    return 0


# ---------------------------------------------------------------- the outcome of a run (SD11) and its one line

JOBS = ('chain', 'gate', 'publish', 'pr', 'publish-merged', 'heartbeat', 'local')
SD5 = {1: 'passed turns false', 2: 'above 110 % of its budget', 3: 'Hausdorff worse by more than the tolerance',
       4: 'no comparable hologram (new ship or new source)', 5: 'fails another metric'}
GRID_RULES = ('order', 'overlap', 'handcheck', 'no-transform')
BOT = ('-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com')


def plural(n: int, word: str) -> str:
    return f'{n} {word}' + ('' if n == 1 else 's')


def counts(d: dict, v: dict) -> dict:
    """The numbers of a run's one line, from diff.json and verify.json: holos refreshed = rebuilt and not byte-equal."""
    holo = v.get('holo') or {}
    return {'changed': len(d['ships']['changed']), 'new': len(d['ships']['new']), 'gone': len(d['ships']['gone']),
            'holosRefreshed': holo.get('built', 0) - holo.get('byteEqualToPrevious', 0),
            'findings': sum(1 for f in v['findings'] if f['stop'])}


def summary_line(result: str, *, tag: str | None = None, counts: dict | None = None, pr: object = None,
                 unexpected: list[str] | None = None, error: str | None = None) -> str:
    """The line Martin reads without the log (SD11): in the heartbeat's summary, state/last-run.json and the commit."""
    c = counts or {}
    if result == 'release':
        return (f"Release {tag}: {plural(c.get('changed', 0), 'ship')} changed, {c.get('new', 0)} new"
                + (f", {c['gone']} gone" if c.get('gone') else '') + f", {plural(c.get('holosRefreshed', 0), 'holo')} refreshed")
    if result == 'pr':
        return f"PR #{pr}: {plural(c.get('findings', 0), 'finding')}"
    if result == 'nothing':
        return 'nothing changed'
    if result == 'gate-red':
        u = unexpected or []
        return f"gate red: {plural(len(u), 'ship')} differ unexpectedly ({', '.join(u[:10])}{'...' if len(u) > 10 else ''})"
    return f'error {error}'


def outcome(needs: dict, event: str) -> dict:
    """What a run ended with, from the jobs' results and outputs (toJSON(needs)): nothing, release, pr, or red -
    gate-red or error (SD11). `job` names the job that failed."""
    def res(j: str) -> str | None:
        return (needs.get(j) or {}).get('result')

    def out(j: str) -> dict:
        return (needs.get(j) or {}).get('outputs') or {}

    if event == 'push':
        if res('publish-merged') == 'success':
            return {'result': 'release', 'tag': out('publish-merged').get('published'), 'merged': True}
        return {'result': 'error', 'job': 'publish-merged'}
    chain = out('chain')
    if res('chain') != 'success':
        return {'result': 'error', 'job': 'chain'}
    if chain.get('changed') == 'false':
        return {'result': 'nothing'}
    if res('gate') != 'success':
        return {'result': 'gate-red' if res('gate') == 'failure' else 'error', 'job': 'gate', 'tag': chain.get('tag')}
    path = chain.get('path')
    if path == 'release' and res('publish') == 'success':
        return {'result': 'release', 'tag': out('publish').get('published') or chain.get('tag')}
    if path == 'pr' and res('pr') == 'success':
        return {'result': 'pr', 'tag': chain.get('tag'), 'pr': out('pr').get('pr')}
    return {'result': 'error', 'job': 'publish' if path == 'release' else 'pr', 'tag': chain.get('tag')}


def said(out_dir: Path) -> list[dict]:
    """Every stage's three lines of this run, job by job (out/say-<job>.jsonl, sent on as reports)."""
    def order(q: Path) -> tuple[int, str]:
        job = q.stem[len('say-'):]
        return (JOBS.index(job) if job in JOBS else len(JOBS), q.name)

    return [json.loads(line) for q in sorted(out_dir.glob('say-*.jsonl'), key=order)
            for line in q.read_text(encoding='utf-8').splitlines() if line.strip()]


def error_text(stages: list[dict], job: str | None) -> str:
    """'in <stage>: <message>' from the last stage that reported an error (run.py's boundary), else the failed job."""
    failed = [s for s in stages if s['found'].startswith('error:')]
    if failed:
        return f"in {failed[-1]['step']}: {failed[-1]['found'][len('error:'):].strip()}"
    return f"in job {job or '?'}: see the log"


def load_optional(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


# ---------------------------------------------------------------- heartbeat (SD9)

def heartbeat_stage(p, log: Reporter, needs: dict, event: str, run_id: str, run_url: str, today: str) -> int:
    """state/last-run.json - date, run, result, the one line and every stage's three lines - committed to main in every
    run but a dry run (SD9: GitHub turns scheduled workflows off after 60 days without repository activity). After a
    merged PR's release, state/pending.json goes in the same commit."""
    oc = outcome(needs, event)
    stages = said(p.out)
    d, v, g = (load_optional(p.w(n)) for n in ('diff.json', 'verify.json', 'gate.json'))
    pending = load_optional(p.root / 'state' / 'pending.json') if oc.get('merged') else None
    c = pending['counts'] if pending else counts(d, v) if d and v else {}
    r = oc['result']
    if r == 'gate-red' and not (g and g.get('unexpected')):
        r = 'error'                 # the gate job failed before it compared pictures: a technical error
    line = summary_line(r, tag=oc.get('tag'), counts=c, pr=oc.get('pr'), unexpected=(g or {}).get('unexpected'),
                        error=error_text(stages, oc.get('job')))
    chain = (needs.get('chain') or {}).get('outputs') or {}
    doc = {'date': today, 'runId': run_id, 'runUrl': run_url, 'event': event, 'result': r, 'line': line,
           'dataVersion': oc.get('tag') or chain.get('tag'), 'previous': chain.get('previous'), 'counts': c, 'stages': stages}
    (p.root / 'state').mkdir(exist_ok=True)
    save_json(p.root / 'state' / 'last-run.json', doc)
    github.git('add', 'state/last-run.json', cwd=p.root)
    if pending is not None:
        github.git('rm', '-q', '--ignore-unmatch', 'state/pending.json', cwd=p.root)
    github.git(*BOT, 'commit', '-q', '-m', f'data: heartbeat {today} - {line}', cwd=p.root)
    github.git('pull', '--rebase', '-q', 'origin', 'main', cwd=p.root)
    github.git('push', '-q', 'origin', 'HEAD:main', cwd=p.root)
    log.headline(line)
    log.say('heartbeat', f"{event} run {run_id}: results of {', '.join(sorted(needs))}",
            f'{r}: {line}; state/last-run.json with {len(stages)} stage summaries'
            + ('; state/pending.json removed' if pending is not None else ''),
            'none' if r in ('nothing', 'release', 'pr') else 'the run ended red: read the stage named above')
    return 0


# ---------------------------------------------------------------- pr (P6)

def cell(x: object) -> str:
    if x is None:
        return '–'
    if isinstance(x, bool):
        return str(x).lower()
    if isinstance(x, float):
        return f'{x:.4f}'
    if isinstance(x, list):
        return ', '.join(x) or '–'
    return str(x)


def stop_row(f: dict) -> str:
    """One table row per stop: a judge finding with its SD5 cases and metrics old -> new, any other with its detail."""
    data = f.get('data') or {}
    if f['rule'] != 'judge' or 'model' not in data:
        return f"| `{f['id']}` | {f['rule']}: {f['detail']} | – | – | – | – | – |"
    cases, h = data['cases'], data['hausdorff']
    hd = f"{cell(h['old'])} → {cell(h['new'])}"
    if h['delta'] is not None:
        hd += f" ({h['delta']:+.4f}, tolerance {h['tolerance']})"
    return (f"| `{f['id']}` | SD5 case {', '.join(map(str, cases))}: {'; '.join(SD5[k] for k in cases)} "
            f"| {cell(data['model']['old'])} → {data['model']['new']} | {cell(data['passed']['old'])} → {cell(data['passed']['new'])} "
            f"| {cell(data['fails']['old'])} → {cell(data['fails']['new'])} | {hd} "
            f"| {cell(data['triangles']['old'])} → {data['triangles']['new']} / {data['budget']['new']} |")


def pr_body(tag: str, manifest_sha: str, draft_url: str, run_url: str, d: dict, v: dict, g: dict | None) -> str:
    """The PR text, from fields only (E1): one row per stop with its SD5 case and metrics old -> new, the gate, the
    changes, the notes. Grid findings carry Motherlode's request for reports (cryon.rocks/developers)."""
    stops = [f for f in v['findings'] if f['stop']]
    notes = [f for f in v['findings'] if not f['stop']]
    c = counts(d, v)
    s, m = d['ships'], d['models']
    out = [f"## {tag}: {plural(len(stops), 'finding')}", '',
           f"**Merge = approval:** the draft release `{tag}` is published as it is (manifest `{manifest_sha[:12]}`), "
           'from the merge commit. Close this PR to drop it; the next run replaces the draft.', '',
           f'Draft release with the contact sheets (visible with write access): {draft_url}  ', f'Run: {run_url}', '',
           '### Findings that stop the release', '',
           '| Ship | Rule | Model | passed | fails | Hausdorff (Δ, tolerance) | Triangles / budget |',
           '|---|---|---|---|---|---|---|', *[stop_row(f) for f in stops], '']
    grid = [f['id'] for f in stops if f['rule'] in GRID_RULES]
    if grid:
        out += [f"**Grid findings** ({', '.join(f'`{i}`' for i in grid)}): the grid data comes from Motherlode's catalog, "
                'and Motherlode asks for reports of grids that look wrong in-game - please report these to Motherlode '
                '(cryon.rocks).', '']
    out += ['### Changes', '',
            f"- Ships: {c['changed']} changed ({', '.join(s['changed']) or '-'}), {c['new']} new ({', '.join(s['new']) or '-'}), "
            f"{c['gone']} newly gone ({', '.join(s['gone']) or '-'}), {len(s.get('stillGone', []))} gone before, "
            f"{len(s.get('back', []))} back",
            f"- Models: {len(m['changed'])} re-exported, {len(m['new'])} new, {len(m['without_url'])} without URL",
            f"- Holograms: {c['holosRefreshed']} refreshed", '']
    out += ['### Gate', '']
    if g:
        pic = g['pictures']
        out += [f"- Pictures: {pic['equal']} equal, {pic['different']} different, {len(g['unexpected'])} unexpected "
                f"({g.get('expectedShips', '?')} ships expected to change)", '']
    else:
        out += [f'- no gate result for {tag}', '']
    proposals = [f['proposal']['id'] for f in v['findings'] if f.get('proposal')]
    if proposals:
        out += ['### overrides.json', '', f"This PR adds {', '.join(f'`{i}`' for i in proposals)} to `overrides.json`: "
                'the ship stays as it is until its grid has a transform.', '']
    out += ['<details><summary>' + plural(len(notes), 'note') + '</summary>', '',
            *[f"- {f['rule']} `{f['id']}`: {f['detail']}" for f in notes], '', '</details>', '']
    return '\n'.join(out)


def close_superseded(by: str, keep: str | None) -> list[int]:
    """Open data PRs other than `keep`: their draft was replaced, merging them could only fail. Closed with a comment."""
    closed = []
    for x in github.gh_json('pr', 'list', '--state', 'open', '--json', 'number,headRefName') or []:
        if x['headRefName'].startswith('data/') and x['headRefName'] != keep:
            github.gh('pr', 'close', str(x['number']), '--comment', f'Superseded by {by}: the draft release of this PR was replaced.')
            closed.append(x['number'])
    return closed


def pr_stage(p, log: Reporter, tag: str, run_id: str, run_url: str, dry_run: bool) -> int:
    """The PR path (P6): branch data/YYYY.MM with state/pending.json (the draft and its manifest SHA-256) and the
    proposed overrides.json, the PR opened or its text updated. Martin's merge pushes pending.json to main, and
    publish-merged publishes exactly that draft. --dry-run writes out/pr-body.md only."""
    v, d = (json.loads(p.w(n).read_text(encoding='utf-8')) for n in ('verify.json', 'diff.json'))
    g = load_optional(p.w('gate.json'))
    if g and g.get('new') != tag:       # a gate.json of another release (left from an earlier run) says nothing here
        g = None
    c = counts(d, v)
    if dry_run:
        sha, url = '(dry run)', '(dry run)'
    else:
        tmp = p.w('pr')
        if tmp.exists():
            shutil.rmtree(tmp)
        github.gh('release', 'download', tag, '--pattern', 'manifest.json', '--dir', str(tmp))
        sha = manifest.sha256(tmp / 'manifest.json')
        url = github.gh_json('release', 'view', tag, '--json', 'url')['url']
    body = p.out / 'pr-body.md'
    body.write_text(pr_body(tag, sha, url, run_url, d, v, g), encoding='utf-8', newline='\n')
    if dry_run:
        log.say('pr --dry-run', 'verify.json, diff.json, gate.json', f"{c['findings']} findings; text in {body}", 'none')
        return 0
    year, month, _ = version_key(tag)
    branch = f'data/{year}.{month:02d}'
    github.git('switch', '-C', branch, cwd=p.root)
    (p.root / 'state').mkdir(exist_ok=True)
    save_json(p.root / 'state' / 'pending.json', {'tag': tag, 'manifestSha256': sha, 'runId': run_id, 'runUrl': run_url, 'counts': c})
    files = ['state/pending.json']
    if p.w('overrides-proposed.json').exists():
        shutil.copyfile(p.w('overrides-proposed.json'), p.root / 'overrides.json')
        files.append('overrides.json')
    github.git('add', *files, cwd=p.root)
    github.git(*BOT, 'commit', '-q', '-m', f"data: {tag} pending ({plural(c['findings'], 'finding')})", cwd=p.root)
    github.git('push', '--force', 'origin', branch, cwd=p.root)
    title = f"Ship data {tag}: {plural(c['findings'], 'finding')}"
    open_ = github.gh_json('pr', 'list', '--head', branch, '--state', 'open', '--json', 'number,headRefName') or []
    if open_:
        number = open_[0]['number']
        github.gh('pr', 'edit', str(number), '--title', title, '--body-file', str(body))
    else:
        created = github.gh('pr', 'create', '--base', 'main', '--head', branch, '--title', title, '--body-file', str(body))
        number = int(created.strip().rsplit('/', 1)[-1])
    closed = close_superseded(f'#{number}', branch)
    log.output('pr', number)
    log.say('pr', f"verify.json ({c['findings']} stops), diff.json, gate.json; draft {tag} (manifest {sha[:12]})",
            f"PR #{number} on {branch} ({'updated' if open_ else 'opened'}); committed {', '.join(files)}; "
            f'{len(closed)} superseded PRs closed',
            f'Martin: read PR #{number}; merge = the draft is published')
    return 0
