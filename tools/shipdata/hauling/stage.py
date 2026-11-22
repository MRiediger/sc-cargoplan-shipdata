"""run.py hauling and run.py hauling-pr (H1, SD14), and what verify puts into the release (K2).

  hauling     source -> templates -> positions -> check -> diff, five summaries (hauling-fetch ... hauling-diff); writes
              work/hauling/ (the two files), work/hauling.json (status), work/hauling-changelog.md, and on a gap
              work/hauling-aliases-proposed.json. A gap is a pool name without a position, or a drop that empties the
              pool of a stellar template (emptied_by_drops). A source error, an unknown title word, a gap or a failed
              check ends with status `failed` and exit 0: the ship data go on (K2). A bug ends red - the workflow step has
              continue-on-error, and verify then carries the last files as for any failure.
  verify      release_files(): this run's files when the status is ok, else the last release's files unchanged when
              they match their manifest, else none (hauling: null)
  hauling-pr  every failure is reported (E1): a gap as a PR with the proposed alias table on data/hauling-aliases (the
              merge extends the table; the data follow with the next run), anything else as the issue "Hauling job
              failed" (opened once, then commented)"""
import datetime as dt
import json
import shutil
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from shipdata import github, manifest, workflow
from shipdata.hauling import check, diff, positions as ps, source, templates as ts
from shipdata.log import Reporter

ALIASES = 'tools/hauling-aliases.json'
STATUS, FOLDER, CHANGELOG, NOTES = 'hauling.json', 'hauling', 'hauling-changelog.md', 'hauling-notes.md'
PROPOSED = 'hauling-aliases-proposed.json'
ISSUE_TITLE = 'Hauling job failed'


class Stop(Exception):
    def __init__(self, kind: str, reason: str) -> None:
        super().__init__(reason)
        self.kind, self.reason = kind, reason


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path: Path, doc: object) -> None:
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def previous_hauling(folder: Path) -> tuple[str, dict | None, dict | None, list[str]]:
    """(tag, templates, positions, problems) of the last release folder (run.py previous: work/previous-release). Files
    that differ from their manifest or fail a check are no last files: neither diffed against nor carried."""
    m = manifest.read(folder / 'manifest.json')
    sec = m.get('hauling')
    if not sec:
        return m['dataVersion'], None, None, []
    problems = check.file_problems(folder, sec)
    if problems:
        return m['dataVersion'], None, None, problems
    t, pos = load(folder / sec['templates']['file']), load(folder / sec['positions']['file'])
    problems = check.problems(t, pos)
    return (m['dataVersion'], None, None, problems) if problems else (m['dataVersion'], t, pos, [])


def emptied_by_drops(kept: list[dict], resolved: list[dict], starmap: ps.Starmap, aliases: dict[str, dict]) -> list[ps.Gap]:
    """Stellar pools that held names before resolution and only drops emptied (H1 addendum, 22 Nov): each such name is a
    gap, so the alias PR asks for a decision instead of the board losing an edge in silence. Planetary and local pools may
    empty (their rooms and caves have no position); a stellar pool that keeps one place stays. resolved: resolve()'s
    templates, in the order of kept."""
    gaps: dict[tuple[str, str | None], ps.Gap] = {}
    for raw, new in zip(kept, resolved, strict=True):
        if raw['missionType'] != 'stellar':
            continue
        for key in ('pickupPool', 'dropoffPool'):
            if raw[key] and not new[key] and all('drop' in aliases.get(n, {}) for n in raw[key]):
                for n in raw[key]:
                    g = gaps.setdefault((n, raw['system']), ps.Gap(
                        n, raw['system'], f"its drop empties the {key} of a stellar template", [], starmap.like(n, raw['system'])))
                    g.templates.append(raw['uuid'])
    return sorted(gaps.values(), key=lambda g: (g.name, g.system or ''))


def hauling_stage(p, log: Reporter, saved: Path | None, fetched_at: str | None = None, previous: Path | None = None) -> int:
    fetched_at = fetched_at or utc_now()
    version = load(p.w('previous.json'))['nextVersion']
    tag, old_t, old_p, prev_problems = previous_hauling(previous or p.w('previous-release'))
    out = p.w(FOLDER)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in (PROPOSED, CHANGELOG):
        p.w(name).unlink(missing_ok=True)
    doc: dict = {'status': 'failed', 'kind': None, 'reason': None, 'changed': False, 'dataVersion': version,
                 'previous': tag, 'previousProblems': prev_problems, 'source': None, 'counts': {}, 'excluded': {},
                 'dropped': 0, 'gaps': [], 'hints': [], 'diff': None}
    try:
        src = source.fetch(saved)
        doc['source'] = {'repository': source.REPOSITORY, 'commit': src.commit, 'gameBuild': src.game_build,
                         'fetchedAt': fetched_at}
        log.num('hauling.requests', src.requests)
        log.say('hauling-fetch', f"{source.REPOSITORY} at {src.commit[:12]} ({'saved: ' + str(saved) if saved else 'gh api + one tarball GET'})",
                f'{src.contract_files} contract files, {len(src.contracts)} of the two naming schemes; '
                f"starmap {len(src.starmap['entities'])} entries; game build {src.game_build}; {src.requests} requests",
                'none' if src.game_build[:1].isdigit() else 'the commit message names no build: the first line is written')

        kept, excluded = [], Counter()
        for raw in src.contracts:
            tpl, why = ts.normalize(raw)
            if why:
                excluded[why] += 1
            else:
                kept.append(tpl)
        doc['excluded'] = dict(excluded.most_common())
        by = Counter(f"{t['contractor']} {t['missionType']}" for t in kept)
        log.say('hauling-templates', f'{len(src.contracts)} contracts against schema 1 (filter, both naming schemes, V8)',
                f"{len(kept)} templates ({', '.join(f'{k} {v}' for k, v in sorted(by.items()))}); left out: "
                + (', '.join(f'{k} {v}' for k, v in excluded.most_common()) or 'none'), 'none')

        aliases_doc = load(p.root / ALIASES)
        sm = ps.Starmap(src.starmap)
        res = ps.resolve(kept, sm, aliases_doc['aliases'])
        doc['dropped'] = sum(res.dropped.values())
        emptied = emptied_by_drops(kept, res.templates, sm, aliases_doc['aliases'])
        gaps = res.gaps + emptied
        doc['gaps'] = [asdict(g) for g in gaps]
        if gaps:
            write(p.w(PROPOSED), dict(aliases_doc, aliases=ps.propose(aliases_doc['aliases'], gaps)))
            raise Stop('gap', f"{len(res.gaps)} pool names without a position, {len(emptied)} drops that empty a stellar "
                              f"pool: {', '.join(g.name for g in gaps[:8])}" + ('...' if len(gaps) > 8 else ''))
        pos, hints = ps.build(ps.Starmap(src.starmap), res.used, aliases_doc['aliases'])
        doc['hints'] = res.hints + hints
        per = Counter(x['system'] for x in pos)
        log.say('hauling-positions', f"pool names against the starmap and {ALIASES} ({len(aliases_doc['aliases'])} entries)",
                f"{len(res.used)} places named by pools; {len(pos)} positions ({', '.join(f'{k} {v}' for k, v in sorted(per.items()))}); "
                f"{doc['dropped']} pool names dropped (V6); {len(doc['hints'])} hints", 'none' if not doc['hints'] else
                '; '.join(doc['hints'][:5]))

        templates_doc = {'schemaVersion': check.SCHEMA_VERSION, 'dataVersion': version, 'source': doc['source'],
                         'templates': sorted(res.templates, key=lambda t: t['uuid'])}
        positions_doc = {'schemaVersion': check.SCHEMA_VERSION, 'dataVersion': version,
                         'source': {'repository': source.REPOSITORY, 'file': source.STARMAP, 'commit': src.commit,
                                    'fetchedAt': fetched_at},
                         'positions': pos}
        problems = check.problems(templates_doc, positions_doc)
        if problems:
            raise Stop('verify', '; '.join(problems[:5]) + ('...' if len(problems) > 5 else ''))
        write(out / check.TEMPLATES_FILE, templates_doc)
        write(out / check.POSITIONS_FILE, positions_doc)
        sec = check.section(out)
        for key in ('templates', 'positions'):
            log.num(f'hauling.{key}.bytes', sec[key]['bytes'])
        log.say('hauling-verify', "the app's loader checks (K2, K3) and the pipeline's rules on both files",
                f"0 problems; {check.TEMPLATES_FILE} {sec['templates']['bytes']} bytes, {check.POSITIONS_FILE} "
                f"{sec['positions']['bytes']} bytes", 'none')

        d = diff.compare(old_t, templates_doc, old_p, positions_doc)
        legs_off = sum(1 for t in res.templates if not ts.legs_as_expected(t))
        p.w(CHANGELOG).write_text(diff.changelog(d, legs_off=legs_off, excluded=dict(excluded), dropped=doc['dropped'],
                                                 carried=None), encoding='utf-8', newline='\n')
        doc.update(status='ok', changed=d['changed'], files=sec, counts={'templates': len(kept), 'positions': len(pos),
                                                                         'legsOff': legs_off},
                   diff={k: {x: (len(v) if isinstance(v, list) else v) for x, v in d[k].items()} for k in ('templates', 'positions')})
        dt_, dp = d['templates'], d['positions']
        log.say('hauling-diff', f"against {tag}" + (' (no hauling data there)' if old_t is None else '')
                + (f"; its files were not used: {'; '.join(prev_problems[:3])}" if prev_problems else ''),
                f"templates {len(dt_['new'])} new, {len(dt_['gone'])} gone, {len(dt_['reward'])} reward changed; places "
                f"{len(dp['new'])} new, {len(dp['gone'])} gone, {len(dp['renamed'])} renamed, {len(dp['moved'])} moved; "
                f"{legs_off} templates off the leg count (K2)",
                'none: changed - a release even if no ship changed (SD14)' if d['changed'] else 'none: content unchanged')
    except source.SourceError as e:
        doc.update(kind='source', reason=str(e))
    except ts.UnknownWord as e:
        doc.update(kind='words', reason=str(e))
    except Stop as e:
        doc.update(kind=e.kind, reason=e.reason)
    write(p.w(STATUS), doc)
    log.output('status', doc['status'])
    if doc['status'] != 'ok':
        log.num('hauling.failed', 1)
        log.say('hauling', 'run.py hauling', f"failed ({doc['kind']}): {doc['reason']}",
                'none for the ship data (K2): verify carries the last hauling files; hauling-pr reports it'
                + (' with the proposed aliases' if doc['kind'] == 'gap' else ' as an issue'))
    return 0


def changed(p) -> bool:
    """For diff: the hauling data alone release when their content changed (SD14)."""
    h = workflow.load_optional(p.w(STATUS))
    return bool(h and h['status'] == 'ok' and h['changed'])


def release_files(p, previous: Path) -> tuple[Path | None, str, str]:
    """(folder holding the two files, state, note) for verify (K2): updated | unchanged | carried | none. previous: the
    last release folder (diff --previous)."""
    h = workflow.load_optional(p.w(STATUS))
    if h and h['status'] == 'ok' and all((p.w(FOLDER) / n).exists() for n in check.FILES):
        return p.w(FOLDER), 'updated' if h['changed'] else 'unchanged', f"from {h['source']['repository']} at {h['source']['commit'][:12]}"
    reason = f"{h['kind']}: {h['reason']}" if h else 'the hauling step did not finish (see its log)'
    tag, t, _, problems = previous_hauling(previous)
    if t is not None:
        return previous, 'carried', f'carried unchanged from {tag}; this run failed ({reason})'
    return None, 'none', f'no hauling data; this run failed ({reason})' + (
        f"; the files of {tag} were not carried: {'; '.join(problems[:3])}" if problems else '')


def write_notes(p, state: str, note: str) -> None:
    """The hauling paragraph of the release notes (draft reads work/hauling-notes.md)."""
    text = (p.w(CHANGELOG).read_text(encoding='utf-8') if state in ('updated', 'unchanged') and p.w(CHANGELOG).exists()
            else f'**Hauling data:** {note}.\n')
    p.w(NOTES).write_text(text, encoding='utf-8', newline='\n')


# ---------------------------------------------------------------- hauling-pr (E1)

def gap_body(h: dict, run_url: str) -> str:
    rows = []
    for g in h['gaps']:
        cands = '; '.join(f"{c['name']} ({c['system']}, {c['type']}, `{c['uuid']}`)" for c in g['candidates']) or '–'
        rows.append(f"| `{g['name']}` | {g['system'] or 'any'} | {g['why']} | {len(g['templates'])} | {cands} |")
    return '\n'.join([
        f"## Hauling aliases: {len(h['gaps'])} place names without a position", '',
        f"The hauling job of run {run_url} stopped: these pool names match no starmap entry, or their `drop` empties the "
        'pool of a stellar template (column Why). The ship data were released '
        'without it (K2); the last hauling files are carried.', '',
        f'This PR adds one entry per name to `{ALIASES}`: a unique candidate by `uuid`, otherwise a `drop` with the '
        'candidates named. **Merge = the table is extended**; the hauling data follow with the next run (dispatch or the '
        'first of the month). Edit an entry in the PR first if the proposal is wrong.', '',
        '| Name | System | Why | Templates | Candidates |', '|---|---|---|---|---|', *rows, ''])


def issue_body(reason: str, run_url: str) -> str:
    return '\n'.join([f'## {ISSUE_TITLE}', '', f'Run: {run_url}', '', f'**Cause:** {reason}', '',
                      'The ship data were not held up (K2): the release carries the last hauling files unchanged, or '
                      'none. This issue stays open until a run succeeds; each failed run adds a comment.', ''])


def hauling_pr_stage(p, log: Reporter, run_url: str, dry_run: bool) -> int:
    h = workflow.load_optional(p.w(STATUS))
    if h and h['status'] == 'ok':
        log.say('hauling-pr', 'work/hauling.json', 'status ok: nothing to report', 'none')
        return 0
    if h and h['kind'] == 'gap':
        body = p.out / 'hauling-pr-body.md'
        body.write_text(gap_body(h, run_url), encoding='utf-8', newline='\n')
        if dry_run:
            log.say('hauling-pr --dry-run', 'work/hauling.json', f"{len(h['gaps'])} gaps; text in {body}", 'none')
            return 0
        branch = workflow.ALIAS_BRANCH
        github.git('switch', '-C', branch, cwd=p.root)
        shutil.copyfile(p.w(PROPOSED), p.root / ALIASES)
        github.git('add', ALIASES, cwd=p.root)
        github.git(*workflow.BOT, 'commit', '-q', '-m', f"data: hauling aliases - {len(h['gaps'])} names", cwd=p.root)
        github.git('push', '--force', 'origin', branch, cwd=p.root)
        title = f"Hauling aliases: {len(h['gaps'])} place names without a position"
        open_ = github.gh_json('pr', 'list', '--head', branch, '--state', 'open', '--json', 'number,headRefName') or []
        if open_:
            number = open_[0]['number']
            github.gh('pr', 'edit', str(number), '--title', title, '--body-file', str(body))
        else:
            number = int(github.gh('pr', 'create', '--base', 'main', '--head', branch, '--title', title,
                                   '--body-file', str(body)).strip().rsplit('/', 1)[-1])
        log.output('pr', number)
        log.say('hauling-pr', f"{len(h['gaps'])} gaps of work/hauling.json", f"PR #{number} on {branch} "
                f"({'updated' if open_ else 'opened'})", f'Martin: read PR #{number}; merge = the alias table is extended')
        return 0
    if h:
        reason = f"{h['kind']}: {h['reason']}"
    else:
        lines = [s for s in workflow.said(p.out) if s['step'] == 'hauling']
        reason = workflow.error_text(lines, 'chain') if lines else 'the hauling step did not run to its end (see the run log)'
    body = p.out / 'hauling-issue.md'
    body.write_text(issue_body(reason, run_url), encoding='utf-8', newline='\n')
    if dry_run:
        log.say('hauling-pr --dry-run', 'work/hauling.json', f'failed: {reason}; text in {body}', 'none')
        return 0
    found = [x for x in github.gh_json('issue', 'list', '--state', 'open', '--search', f'in:title "{ISSUE_TITLE}"',
                                       '--json', 'number,title') or [] if x['title'] == ISSUE_TITLE]
    if found:
        number = found[0]['number']
        github.gh('issue', 'comment', str(number), '--body-file', str(body))
    else:
        number = int(github.gh('issue', 'create', '--title', ISSUE_TITLE, '--body-file', str(body)).strip().rsplit('/', 1)[-1])
    log.output('issue', number)
    log.say('hauling-pr', 'work/hauling.json', f"issue #{number} {'commented' if found else 'opened'}: {reason}",
            f'Martin: read issue #{number}')
    return 0
