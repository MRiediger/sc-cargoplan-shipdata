"""The five stages of run.py and what they hand on (all under <root>/work, numbers under <root>/out):

  fetch    -> work/catalog.json, work/fetch.json, cache/models/*.glb
  diff     -> work/previous/ (the last release's ships.zip), work/ships/ (import, first run), work/import-1.json,
              work/model-map-1.csv, work/previous-order.json, work/diff.json
  build    -> work/holo/<className>/PP.holo..., work/outlines.json, work/import-2.json (anchors), work/build.json
  verify   -> work/stage/ (ships/, outlines.json, <slug>.holo, manifest.json), work/verify.json, work/overrides-proposed.json
  release  -> out/release/ (--dry-run) or out/seed/ (--seed): the flat assets manifest.json, NOTICE.md, ships.zip, <slug>.holo

Exit codes: 0 done, 1 error, 2 a rule fired (PR path). Every stage ends with checked / found / to do."""
import csv
import datetime as dt
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from shipdata import chain, diff, fetch, importer, manifest, release, rules
from shipdata.log import Reporter

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import holo_mesh  # noqa: E402  (byte-equal copy, imported for read_map / slug_models / METRIC_KEYS only)

CLASS_NAME = re.compile(r'^[A-Za-z0-9_]+$')
OK_MODEL = ('fetched', 'cached')


class Paths:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.work = root / 'work'
        self.cache = root / 'cache'
        self.models = root / 'cache' / 'models'
        self.out = root / 'out'
        self.work.mkdir(parents=True, exist_ok=True)

    def w(self, name: str) -> Path:
        return self.work / name


def save_json(path: Path, doc: object) -> None:
    path.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8', newline='\n')


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f'{path} is missing: run the stage before this one')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def utc_now() -> str:
    return dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def key_map(m: dict) -> dict[str, str]:
    """className -> modelKey from the last release's holograms (P6 b): created ships keep the key their model is built under."""
    return {e['model']: slug for slug, e in ((m.get('holo') or {}).get('ships') or {}).items()
            if CLASS_NAME.match(e.get('model') or '')}


# ---------------------------------------------------------------- fetch

def fetch_stage(p: Paths, log: Reporter, saved: Path | None, catalog_only: bool) -> int:
    requests = {'api': 0, 'page': 0, 'model': 0}
    if saved:
        api, page = fetch.load_saved(saved)
        origin = f'saved answers in {saved}'
    else:
        day = dt.date.today().isoformat()
        raw = p.cache / 'catalogs' / day / 'raw'
        if (raw / 'api.json').exists():
            raise fetch.SourceError(f'{raw} exists: the API is called once per day at most; use --saved {raw}')
        api_bytes = fetch.fetch_api()
        requests['api'] = 1
        page_text = fetch.fetch_page()
        requests['page'] = 1
        raw.mkdir(parents=True)
        (raw / 'api.json').write_bytes(api_bytes)
        (raw / 'page.txt').write_text(page_text, encoding='utf-8')
        api, page = json.loads(api_bytes.decode('utf-8-sig')), json.loads(fetch.ships_array_text(page_text))
        origin = f'cryon.rocks, saved to {raw}'
    catalog, notes = fetch.join(api, page)
    save_json(p.w('catalog.json'), catalog)
    for n in notes:
        log.line(n)
    with_url = sum(1 for s in catalog['ships'] if s.get('modelUrl'))
    models: dict[str, dict] = {}
    if not catalog_only:
        models = fetch.fetch_models(catalog, p.models)
        requests['model'] = sum(1 for m in models.values() if m['status'] != 'cached')
    unavailable = {c: m for c, m in models.items() if m['status'] == 'unavailable'}
    save_json(p.w('fetch.json'), {'gameBuild': catalog['gameBuild'], 'updatedAt': catalog['updatedAt'], 'origin': origin,
                                  'catalogOnly': catalog_only, 'requests': requests, 'models': models})
    for k, v in requests.items():
        log.num(f'fetch.requests.{k}', v)
    log.num('fetch.ships', len(catalog['ships']))
    log.num('fetch.models.unavailable', len(unavailable))
    counts = {s: sum(1 for m in models.values() if m['status'] == s) for s in ('cached', 'fetched', 'unavailable')}
    log.say('fetch', f"catalog from {origin}; {'no models (--catalog-only)' if catalog_only else f'{with_url} model URLs against cache/models'}",
            f"{catalog['gameBuild']}, updatedAt {catalog['updatedAt']}, {len(catalog['ships'])} ships, {with_url} with a model; "
            f"models {counts}; requests: {requests['api']} API call, {requests['page']} page GET, {requests['model']} model GET",
            'none' if not unavailable else
            f"{len(unavailable)} models unavailable ({', '.join(sorted(unavailable)[:8])}{'...' if len(unavailable) > 8 else ''}): "
            'their ships keep the last hologram and outline')
    return 0


# ---------------------------------------------------------------- diff

def diff_stage(p: Paths, log: Reporter, previous: Path) -> int:
    data = p.w('previous')
    m = release.unpack(previous, data)          # manifest.json + ships.zip, checked; the holograms are not needed here
    catalog = load_json(p.w('catalog.json'))
    order = p.w('previous-order.json')
    save_json(order, diff.order_map(m))
    ships = p.w('ships')
    if ships.exists():
        shutil.rmtree(ships)
    shutil.copytree(data / 'ships', ships)
    r = importer.run_import(p.w('catalog.json'), ships, data / 'outlines.json', p.w('model-map-1.csv'), p.w('import-1.json'),
                            key_map(m), create=True, previous_order=order)
    absent = [e['id'] for e in r.entries if e['status'] == 'absent']
    # Written from the catalog now, but the last release has no order for them (seed: not in the archive): not compared.
    unchecked = sorted(e['id'] for e in r.entries if e['status'] in ('same', 'updated', 'created') and e['id'] in m['ships']
                       and m['ships'][e['id']].get('orderKeys') is None)
    compared = sum(1 for e in r.entries if e['status'] in ('same', 'updated', 'created', 'order') and e['id'] in m['ships']
                   and e['id'] not in unchecked)
    newly_gone, still_gone = diff.split_gone(absent, m['ships'])
    changes = diff.compare_ships(data / 'ships', ships, newly_gone + still_gone)
    changes.gone = newly_gone
    chosen = set(holo_mesh.slug_models(holo_mesh.read_map(str(p.w('model-map-1.csv'))))[0].values())
    models = diff.model_changes((m.get('holo') or {}).get('ships') or {}, catalog, chosen)
    status = {s: sum(1 for e in r.entries if e['status'] == s) for s in sorted({e['status'] for e in r.entries})}
    back = sorted(rules.back(m['ships'], {e['id'] for e in r.entries if e['status'] != 'absent'}))
    order_changed = sorted(e['id'] for e in r.entries if e['status'] == 'order')
    overrides = {o['id'] for o in load_json(p.root / 'overrides.json')['ships']} if (p.root / 'overrides.json').exists() else set()
    import_stops = sorted(e['id'] for e in r.entries
                          if e['status'] == 'handcheck' or (e['status'] == 'kept' and e['id'] not in overrides))
    nothing = diff.nothing_changed(changes, models, back, order_changed, import_stops)
    save_json(p.w('diff.json'), {'previous': str(previous.resolve()), 'previousData': str(data.resolve()),
                                 'previousDataVersion': m['dataVersion'],
                                 'order': {'compared': compared, 'changed': order_changed},
                                 'orderNotCompared': unchecked, 'ships': dict(asdict(changes), stillGone=still_gone, back=back),
                                 'models': asdict(models), 'import': {'rc': r.rc, 'status': status, 'stops': import_stops},
                                 'nothingChanged': nothing})
    for k in ('changed', 'new', 'gone'):
        log.num(f'diff.ships.{k}', len(getattr(changes, k)))
    for k in ('changed', 'new', 'without_url'):
        log.num(f'diff.models.{k}', len(getattr(models, k)))
    show = lambda xs: ', '.join(xs[:10]) + ('...' if len(xs) > 10 else '')
    log.say('diff', f"catalog {catalog['gameBuild']} ({catalog['updatedAt']}) against release {m['dataVersion']}: "
            f"manifest.json and {m['assets']['ships']} checked, {len(list((data / 'ships').glob('*.json')))} ship files without stamps, {len(models.same) + len(models.changed) + len(models.without_url)} models"
            + "; grid order against the release's orderKeys",
            f"ships: {len(changes.changed)} changed ({show(changes.changed)}), {len(changes.new)} new ({show(changes.new)}), "
            f"{len(changes.gone)} newly gone ({show(changes.gone)}), {len(still_gone)} gone before ({show(still_gone)}), "
            f"{len(back)} back ({show(back)}), {len(changes.same)} same; models: {len(models.changed)} changed "
            f"(re-export), {len(models.new)} new, {len(models.without_url)} without URL ({show(models.without_url)}), "
            f"{len(models.unused)} unused ({show(models.unused)}); grid order compared for {compared} ships, "
            f"{status.get('order', 0)} in another order, not compared for {len(unchecked)} ({show(unchecked)}); import {status}",
            'none: nothing changed' if nothing else
            'build the changed and new models, then verify' + (f"; import stops: {show(import_stops)}" if import_stops else ''))
    return 0


# ---------------------------------------------------------------- build

def build_stage(p: Paths, log: Reporter, ship_ids: list[str], build_all: bool, data_version: str, generated_at: str) -> int:
    d = load_json(p.w('diff.json'))
    previous = Path(d['previous'])
    m = manifest.read(previous / 'manifest.json')
    fetch_info = load_json(p.w('fetch.json'))
    if fetch_info['catalogOnly']:
        raise RuntimeError('fetch ran with --catalog-only: build needs the models')
    fetched = fetch_info['models']
    rows = holo_mesh.read_map(str(p.w('model-map-1.csv')))
    slugs, shared = holo_mesh.slug_models(rows)
    prev_holo = (m.get('holo') or {}).get('ships') or {}
    if build_all:
        want = set(slugs)
    elif ship_ids:
        want = {r['modelKey'] for r in rows if r['id'] in ship_ids and r['modelKey']}
        unknown = sorted(set(ship_ids) - {r['id'] for r in rows})
        if unknown:
            raise RuntimeError(f'not in the model map (no model, or not written): {", ".join(unknown)}')
    else:
        moved = set(d['models']['changed']) | set(d['models']['new'])
        want = {s for s, c in slugs.items() if c in moved or s not in prev_holo}
    holo_work = p.w('holo')
    built, unavailable, failed = {}, {}, {}
    for slug in sorted(want):
        cls = slugs[slug]
        info = fetched.get(cls)
        if not info or info['status'] not in OK_MODEL:
            unavailable[slug] = cls
            continue
        try:
            r = chain.build_model(cls, p.models / info['file'], holo_work)
        except subprocess.CalledProcessError as e:
            failed[slug] = f'{cls}: {e.cmd[3] if len(e.cmd) > 3 else e.cmd}: exit {e.returncode}: {(e.stderr or "").strip()[-400:]}'
            log.line(f'FAILED {failed[slug]}')
            continue
        chain.report(log, r)
        built[slug] = {'className': cls, 'model': info['file'], 'budget': r.budget, 'triangles': r.pp['triangles'],
                       'passed': r.pp['passed'], 'seconds': round(sum(r.seconds.values()), 1)}
    # Outlines: rebuilt slugs from their models, every other entry of the last release kept byte for byte.
    built_map = p.w('model-map-built.csv')
    with built_map.open('w', encoding='utf-8', newline='\n') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['id', 'className', 'modelKey', 'sx', 'sy', 'sz'])
        for row in csv.DictReader(p.w('model-map-1.csv').open(encoding='utf-8', newline='')):
            if row['modelKey'] in built:
                w.writerow([row[k] for k in ('id', 'className', 'modelKey', 'sx', 'sy', 'sz')])
    prev_data = Path(d['previousData'])
    prev_slugs = [s['slug'] for s in load_json(prev_data / 'outlines.json')['ships']]
    keep = [s for s in prev_slugs if s not in built]
    subprocess.run([sys.executable, '-I', str(chain.MESH), 'outlines-v2', str(built_map), str(prev_data / 'outlines.json'),
                    str(p.w('outlines.json')), generated_at, data_version, *keep], check=True,
                   env=dict(os.environ, HOLO_WORK=str(holo_work)), stdout=subprocess.DEVNULL)
    # Anchors: the import once more, now with the new models' floors.
    r2 = importer.run_import(Path(p.w('catalog.json')), p.w('ships'), p.w('outlines.json'), p.w('model-map-2.csv'),
                             p.w('import-2.json'), key_map(m), create=True, previous_order=p.w('previous-order.json'))
    status = {s: sum(1 for e in r2.entries if e['status'] == s) for s in sorted({e['status'] for e in r2.entries})}
    save_json(p.w('build.json'), {'built': built, 'unavailable': unavailable, 'failed': failed, 'sharedSlugs': shared,
                                  'dataVersion': data_version, 'generatedAt': generated_at, 'import2': status})
    total = sum(b['seconds'] for b in built.values())
    log.num('build.models', len(built))
    log.num('build.seconds', round(total, 1))
    log.num('build.unavailable', len(unavailable))
    log.num('build.failed', len(failed))
    log.say('build', f"{len(want)} models ({'all' if build_all else 'chosen ships' if ship_ids else 'changed and new'}): flatten, cull, "
            f'ladder 20k/30k/40k, export, outline; outlines-v2 ({len(keep)} entries kept); import with the new floors',
            f'{len(built)} built in {total:.0f} s, {len(unavailable)} without model ({", ".join(sorted(unavailable)) or "-"}), '
            f'{len(failed)} failed; import {status}',
            'none' if not failed else f'chain failed for {", ".join(sorted(failed))}: see the log above')
    return 1 if failed else 0


# ---------------------------------------------------------------- verify

STAMP_KEYS = ('id', 'name', 'manufacturer', 'notes')


def follow_base(variant_text: str, base_text: str) -> str:
    """A gone variant takes its base ship's file (rule "variant"): the base's lines, with the variant's id, name,
    manufacturer and notes (one field per line, ShipJson.ps1's format)."""
    own = {}
    for line in variant_text.split('\n'):
        mt = re.match(r'^  "(\w+)": ', line)
        if mt and mt[1] in STAMP_KEYS:
            own[mt[1]] = line
    out = []
    for line in base_text.split('\n'):
        mt = re.match(r'^  "(\w+)": ', line)
        if mt and mt[1] in STAMP_KEYS:
            if mt[1] in own:
                out.append(own[mt[1]])
            continue
        out.append(line)
    return '\n'.join(out)


def tool_versions() -> dict[str, str]:
    """The versions that ran, as the pins name them: package versions (importlib.metadata), since cv2.__version__ says
    5.0.0 for the pinned opencv-python-headless 5.0.0.93."""
    from importlib.metadata import version
    run = lambda *a: subprocess.run(list(a), capture_output=True, text=True, check=True).stdout.strip()
    return {'python': platform.python_version(), 'numpy': version('numpy'), 'opencv': version('opencv-python-headless'),
            'node': run('node', '-v').lstrip('v'),
            'meshoptimizer': json.loads((TOOLS / 'node_modules' / 'meshoptimizer' / 'package.json').read_text())['version'],
            'pwsh': run('pwsh', '-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()')}


def pipeline_commit() -> str:
    return subprocess.run(['git', '-C', str(TOOLS), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True,
                          check=True).stdout.strip()


def verify_stage(p: Paths, log: Reporter, app_tag: str, today: str) -> int:
    d = load_json(p.w('diff.json'))
    b = load_json(p.w('build.json'))
    previous = Path(d['previous'])
    m = manifest.read(previous / 'manifest.json')
    catalog = load_json(p.w('catalog.json'))
    entries = load_json(p.w('import-2.json'))
    overrides = {o['id']: o for o in load_json(p.root / 'overrides.json')['ships']} if (p.root / 'overrides.json').exists() else {}
    findings: list[rules.Finding] = []

    # Ships: new ships still without anchors (their model is unavailable) wait outside the release.
    waiting = {e['id'] for e in entries if e['status'] == 'created' and e.get('anchorsKept')}
    findings += [rules.Finding('new-ship', sid, 'new ship without anchors (no model yet): not released, built when its model loads', False)
                 for sid in sorted(waiting)]
    findings += [f for f in rules.import_findings([e for e in entries if e['id'] not in waiting], overrides)]
    present = {e['id'] for e in entries if e['status'] != 'absent'}
    gone = rules.missing(d['ships']['gone'] + d['ships']['stillGone'], m['ships'], present, today)
    stop = rules.too_many_gone(gone.newly_without_base)
    if stop:
        findings.append(stop)
    findings += [rules.Finding('gone', sid, f'missing since {since}', False) for sid, since in sorted(gone.missing_since.items())]
    findings += [rules.Finding('variant', sid, f'gone, takes the data of {base} (racks were equal)', False) for sid, base in sorted(gone.follows.items())]
    findings += [rules.Finding('order-unchecked', sid, 'order not compared: the last release has no orderKeys for it', False)
                 for sid in d['orderNotCompared']]
    returned = rules.back(m['ships'], present)
    findings += [rules.Finding('back', sid, f'back in the catalog ({was}): missingSince and follows cleared, built and judged like any ship', False)
                 for sid, was in returned.items()]

    stage = p.w('stage')
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(p.w('ships'), stage / 'ships')
    for sid in waiting:
        (stage / 'ships' / f'{sid}.json').unlink()
    for sid, base in gone.follows.items():
        text = follow_base((stage / 'ships' / f'{sid}.json').read_text(encoding='utf-8'),
                           (stage / 'ships' / f'{base}.json').read_text(encoding='utf-8'))
        (stage / 'ships' / f'{sid}.json').write_text(text, encoding='utf-8', newline='\n')
    shutil.copyfile(p.w('outlines.json'), stage / 'outlines.json')

    # Holograms (flat, SD4): rebuilt ones from work/holo, every other one of the last release byte for byte.
    prev_holo = (m.get('holo') or {}).get('ships') or {}
    holo_ships: dict[str, dict] = {}
    same_bytes = 0
    for slug, info in sorted(b['built'].items()):
        work = p.w('holo') / info['className']
        pp, flat = load_json(work / 'PP.json'), load_json(work / 'flat.json')
        shutil.copyfile(work / 'PP.holo', stage / f'{slug}.holo')
        holo_ships[slug] = {'model': info['className'], 'rawSha256': flat['rawSha256'], 'budget': pp['budget'],
                            'triangles': pp['triangles'], 'edges': pp['edges'], 'passed': pp['passed'], 'fails': pp['fails'],
                            'metrics': {k: pp[k] for k in holo_mesh.METRIC_KEYS}}
        f = rules.judge(slug, pp, prev_holo.get(slug), info['className'])
        if f:
            findings.append(f)
        if slug in prev_holo and manifest.sha256(stage / f'{slug}.holo') == prev_holo[slug]['sha256']:
            same_bytes += 1
    for slug, e in sorted(prev_holo.items()):
        if slug not in holo_ships:
            if not (previous / e['file']).exists():
                raise FileNotFoundError(f"{previous / e['file']} is missing: verify needs every hologram asset of the last "
                                        'release (the unchanged ones go into the new release byte for byte)')
            shutil.copyfile(previous / e['file'], stage / f'{slug}.holo')
            holo_ships[slug] = {k: v for k, v in e.items() if k not in ('file', 'bytes', 'sha256')}

    # orderKeys: the catalog's for a ship written from it in this run, otherwise the last release's (gone, kept, order).
    written = {e['id']: e['orderKeys'] for e in entries if e['status'] in ('same', 'updated', 'created')}
    order_keys = {sid: written[sid] if sid in written else (m['ships'].get(sid) or {}).get('orderKeys')
                  for sid in sorted(q.stem for q in (stage / 'ships').glob('*.json'))}
    extra = {sid: {'missingSince': None, 'follows': None} for sid in returned}
    extra.update({sid: {'missingSince': since, 'follows': None} for sid, since in gone.missing_since.items()})
    extra.update({sid: {'missingSince': None, 'follows': base} for sid, base in gone.follows.items()})
    for sid, k in order_keys.items():
        extra.setdefault(sid, {})['orderKeys'] = k
    new_m = manifest.build(stage, data_version=b['dataVersion'], generated_at=b['generatedAt'],
                           motherlode={'gameBuild': catalog['gameBuild'], 'updatedAt': catalog['updatedAt']}, app_tag=app_tag,
                           pipeline_commit=pipeline_commit(), tools=tool_versions(),
                           holo_ships=holo_ships if m.get('holo') is not None else None, ships=extra)
    manifest.write(stage / 'manifest.json', new_m)
    problems = manifest.check(stage, new_m)
    findings += [rules.Finding('manifest', '-', pr, True) for pr in problems]

    # Byte-equality against the last release (S12.0: the chain is byte-equal across platforms).
    same_files = sum(1 for rel, h in new_m['files'].items() if h == m['files'].get(rel))
    stops = [f for f in findings if f.stop]
    proposals = [f.proposal for f in findings if f.proposal]
    if proposals:
        save_json(p.w('overrides-proposed.json'), {'ships': sorted(list(overrides.values()) + [dict(x, date=today) for x in proposals],
                                                                   key=lambda o: o['id'])})
    save_json(p.w('verify.json'), {'findings': [asdict(f) for f in findings], 'stop': bool(stops),
                                   'files': {'same': same_files, 'of': len(new_m['files'])},
                                   'holo': {'built': len(b['built']), 'byteEqualToPrevious': same_bytes,
                                            'unavailable': b['unavailable']}})
    log.num('verify.files.same', same_files)
    log.num('verify.files', len(new_m['files']))
    log.num('verify.holo.byte-equal', same_bytes)
    log.num('verify.holo.built', len(b['built']))
    log.num('verify.stops', len(stops))
    for f in findings:
        log.line(f"{'STOP ' if f.stop else 'note '} {f.rule:<12} {f.id:<28} {f.detail}")
    unav = b['unavailable']
    log.say('verify', f"rules on {len(entries)} ships, {len(holo_ships)} holograms, overrides.json ({len(overrides)} entries); "
            f"manifest {b['dataVersion']} written and every file checked against it",
            f"files equal to {m['dataVersion']}: {same_files} / {len(new_m['files'])}; rebuilt holograms byte-equal: "
            f"{same_bytes} / {len(b['built'])}, {len(unav)} models no longer available ({', '.join(sorted(unav.values())) or '-'}); "
            f"{len(stops)} stops, {len(findings) - len(stops)} notes",
            'none: release' if not stops else
            f"PR path: {'; '.join(f'{f.rule} {f.id}' for f in stops[:8])}" + ('; overrides-proposed.json written' if proposals else ''))
    return 2 if stops else 0


# ---------------------------------------------------------------- release

def release_stage(p: Paths, log: Reporter, dry_run: bool) -> int:
    stage = p.w('stage')
    m = manifest.read(stage / 'manifest.json')
    problems = manifest.check(stage, m)
    if problems:
        raise release.ReleaseError(f'stage differs from its manifest: {problems[:5]}')
    if not dry_run:
        raise release.ReleaseError('release publishes nothing: run.py draft and run.py publish do (T12.2)')
    assets = release.pack(stage, p.out / 'release', p.root / 'NOTICE.md')
    total, holos = sum(a.bytes for a in assets), [a for a in assets if a.name.endswith('.holo')]
    for a in assets:
        if not a.name.endswith('.holo'):
            log.line(f'{a.name:<16} {a.bytes:>10} bytes')
    log.line(f"{f'{len(holos)} x .holo':<16} {sum(a.bytes for a in holos):>10} bytes")
    log.num('release.assets', len(assets))
    log.num('release.holo', len(holos))
    log.num('release.bytes', total)
    log.say('release --dry-run', f"stage of {m['dataVersion']} against its manifest, packed to {p.out / 'release'} with NOTICE.md",
            f"{len(assets)} assets, {total} bytes: manifest.json, NOTICE.md, {m['assets']['ships']}, {len(holos)} x .holo; "
            'nothing uploaded, the model cache untouched',
            'none (publishing comes with T12.2)')
    return 0


def seed_stage(p: Paths, log: Reporter, app: Path, holo: Path, catalog_raw: Path, out: Path, app_tag: str,
               data_version: str, generated_at: str) -> int:
    # orderKeys from the catalog v0.5.1 was built from (Martin, 18 Nov): the import against it on a copy of the ships.
    api, page = fetch.load_saved(catalog_raw)
    cat, _ = fetch.join(api, page)
    save_json(p.w('seed-catalog.json'), cat)
    ships = p.w('seed-ships')
    if ships.exists():
        shutil.rmtree(ships)
    shutil.copytree(app / 'ships', ships)
    r = importer.run_import(p.w('seed-catalog.json'), ships, app / 'outlines' / 'ship-outlines.json', p.w('seed-map.csv'),
                            p.w('seed-import.json'), {}, create=False)
    keys, unchecked = release.seed_order_keys(r.entries, [q.stem for q in sorted((app / 'ships').glob('*.json'))])
    s = release.seed(app, holo, p.w('seed-stage'), app_tag=app_tag, data_version=data_version, generated_at=generated_at,
                     pipeline_commit=pipeline_commit(), tools=tool_versions(), order_keys=keys)
    assets = release.pack(s.folder, out, p.root / 'NOTICE.md')
    log.num('seed.ships', s.ships)
    log.num('seed.holos', s.holos)
    log.num('seed.orderKeys', len(keys) - len(unchecked))
    log.num('seed.assets', len(assets))
    log.say('release --seed', f'{app} (ships/, outlines/), {holo} (holograms, manifest) and the catalog {catalog_raw} '
            f'(grid order) into {out}',
            f"{s.ships} ship files, {s.holos} holograms; built from {s.motherlode['gameBuild']}, {s.motherlode['updatedAt']}; "
            f"{len(s.other_sources)} ships of another source: {', '.join(f'{k} ({v})' for k, v in s.other_sources.items())}; "
            f"orderKeys from {cat['gameBuild']} ({cat['updatedAt']}) for {len(keys) - len(unchecked)} ships, "
            f"order not compared for {len(unchecked)} ({', '.join(unchecked)}); {len(assets)} assets",
            f'none: {out} is the last release for diff --previous')
    return 0

