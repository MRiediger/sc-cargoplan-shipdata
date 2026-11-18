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
            f'{cache} bytes left',
            'none')
    return 0
