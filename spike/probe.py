"""spike/probe.py - question 2 of S12.0: are the model URLs reachable from a runner? Throwaway measuring code, stdlib only.

HEAD every model URL of the catalog (200 ms apart, no retry, no GET), GET the spike ship's model as holo-v3 had it and as the catalog has it now (one GET each),
and check both SHA-256 against holo-v3's manifest. Writes CLS/SLUG/ID/GLB/GLB_NEW/HEADS/GETS to $PROBE_OUT (default $SPIKE_OUT/ship.env) and numbers to $SPIKE_OUT/numbers.tsv.

usage: python probe.py <catalog.json or -> <holo-v3 manifest.json> <preferred className> <glb out dir> <user agent>
"""
import hashlib, json, os, statistics, sys, time, urllib.error, urllib.request

# Candidates (plan S12.0): one internal grid, translation only, holo in holo-v3, budget step 1 without simplification.
CANDIDATES = [('ORIG_100i', 'orig-100i', '100i'),
              ('AEGS_Avenger_Titan', 'aegs-avenger-titan', 'avenger_titan'),
              ('CNOU_Nomad', 'cnou-nomad', 'nomad')]
# Model URLs from the catalog of 2026-11-16 (sc-ship-outlines 0062b4f): used only if this run has no catalog.
FALLBACK = {c: f'https://pjacfaoziybemsgwartu.supabase.co/storage/v1/object/public/ship-models/{c}-{h}.glb'
            for c, h in [('ORIG_100i', 'da8168ea3720'), ('AEGS_Avenger_Titan', '654ea0397171'), ('CNOU_Nomad', 'b4cf924689ea')]}
INTERESTING = ('ratelimit', 'retry-after', 'cf-', 'server', 'x-cache', 'age', 'via', 'x-served-by', 'cache-control')
OUT = os.environ.get('SPIKE_OUT', 'out')


def num(key, value):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'numbers.tsv'), 'a', encoding='utf-8') as f:
        f.write(f'{key}\t{value}\n')
    print(f'  # {key} = {value}')


def say(step, checked, found, todo):
    print(f'\n=== {step}\n  checked: {checked}\n  found:   {found}\n  to do:   {todo}\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(f'### {step}\n- **checked:** {checked}\n- **found:** {found}\n- **to do:** {todo}\n\n')


def request(url, method, ua):
    req = urllib.request.Request(url, method=method, headers={'User-Agent': ua})
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read() if method == 'GET' else b''
            return r.status, time.perf_counter() - t, dict(r.headers), body
    except urllib.error.HTTPError as e:
        return e.code, time.perf_counter() - t, dict(e.headers), b''
    except Exception as e:                                  # network error: no status
        return f'error:{type(e).__name__}', time.perf_counter() - t, {}, b''


def main(catalog_path, manifest_path, preferred, glb_dir, ua):
    manifest = {s['slug']: s for s in json.load(open(manifest_path, encoding='utf-8'))['ships']}
    if catalog_path != '-' and os.path.exists(catalog_path):
        catalog = json.load(open(catalog_path, encoding='utf-8-sig'))
        urls = {s['className']: s['modelUrl'] for s in catalog['ships'] if s.get('className') and s.get('modelUrl')}
        source = 'catalog'
    else:
        urls, source = dict(FALLBACK), 'fallback (no catalog in this run)'

    # 1) HEAD every model URL (PROBE_HEAD=0 skips it, for local tests)
    heads, seen = [], {}
    for cls in sorted(urls) if os.environ.get('PROBE_HEAD', '1') != '0' else []:
        status, secs, headers, _ = request(urls[cls], 'HEAD', ua)
        heads.append((cls, status, secs, int(headers.get('Content-Length', 0) or 0)))
        for k, v in headers.items():
            if k.lower().startswith(INTERESTING) and k not in seen:
                seen[k] = v
        time.sleep(0.2)
    if heads:
        by_status = {}
        for _, s, _, _ in heads:
            by_status[str(s)] = by_status.get(str(s), 0) + 1
        lat = [h[2] for h in heads]
        total = sum(h[3] for h in heads)
        num('probe.head.count', len(heads))
        num('probe.head.status', json.dumps(by_status, sort_keys=True))
        num('probe.head.latency.p50.ms', round(1000 * statistics.median(lat)))
        num('probe.head.latency.max.ms', round(1000 * max(lat)))
        num('probe.models.bytes.total', total)
        num('probe.models.bytes.max', max(h[3] for h in heads))
        num('probe.headers', json.dumps(seen, sort_keys=True))
        bad = [f'{c}:{s}' for c, s, _, _ in heads if s != 200]
        say('Scraper probe: HEAD on every model URL',
            f'{len(heads)} model URLs from the {source}, HEAD with User-Agent "{ua}", 200 ms apart, no retry',
            f'status {json.dumps(by_status, sort_keys=True)}; latency p50 {round(1000 * statistics.median(lat))} ms, '
            f'max {round(1000 * max(lat))} ms; {total} bytes in all (cold model cache); headers seen: {json.dumps(seen, sort_keys=True)}',
            'none' if not bad else f'not reachable: {", ".join(bad[:10])} - the pipeline needs another route for these')

    # 2) The ship: the preferred candidate with a holo-v3 entry. Run 2 (17 Nov) found every candidate's model re-exported
    #    under a new hash at the same game build, so two models are fetched: the one holo-v3 was built from (old: the pure
    #    platform drift) and the catalog's (new: what a re-export changes).
    order = sorted(CANDIDATES, key=lambda c: c[0] != preferred)
    cls, slug, sid = next(c for c in order if c[1] in manifest)
    m = manifest[slug]
    base = 'https://pjacfaoziybemsgwartu.supabase.co/storage/v1/object/public/ship-models/'
    old_url = f'{base}{cls}-{m["rawSha256"][:12]}.glb'
    new_url = urls.get(cls, '')
    os.makedirs(glb_dir, exist_ok=True)
    got, texts = {}, []
    for kind, url in (('old', old_url), ('new', new_url)):
        if not url or (kind == 'new' and url == old_url):
            continue
        status, secs, headers, body = request(url, 'GET', ua)
        sha = hashlib.sha256(body).hexdigest()
        num(f'probe.model.{kind}.get.status', status)
        num(f'probe.model.{kind}.get.ms', round(1000 * secs))
        num(f'probe.model.{kind}.bytes', len(body))
        num(f'probe.model.{kind}.sha256', sha)
        texts.append(f'{kind} {url.rsplit("/", 1)[-1]}: GET {status} in {round(1000 * secs)} ms, {len(body)} bytes, '
                     f'SHA-256 {"= holo-v3 rawSha256" if sha == m["rawSha256"] else sha[:12]}')
        if status == 200:
            path = os.path.join(glb_dir, url.rsplit('/', 1)[-1])
            open(path, 'wb').write(body)
            got[kind] = (path, sha)
    same_model = 'new' not in got or got['new'][1] == m['rawSha256']
    num('probe.model.changed.since.holo-v3', not same_model)
    say('Spike ship and its models',
        f"{cls} ({slug}, id {sid}); the model holo-v3 was built from (rawSha256 {m['rawSha256'][:12]}) and the catalog's",
        '; '.join(texts) + ('' if same_model else "; the catalog model DIFFERS from holo-v3's at the same game build"),
        'none' if 'old' in got and same_model else
        'the old model is the platform-drift measurement, the new one shows what a re-export changes' if 'old' in got else
        "holo-v3's model is gone from the bucket: the comparisons mix platform drift and model change")
    glb = got.get('old', got.get('new', ('',)))[0]
    glb_new = got['new'][0] if 'new' in got and 'old' in got and not same_model else ''
    with open(os.environ.get('PROBE_OUT', os.path.join(OUT, 'ship.env')), 'w', encoding='utf-8') as f:
        f.write(f'CLS={cls}\nSLUG={slug}\nID={sid}\nGLB={glb}\nGLB_NEW={glb_new}\nHEADS={len(heads)}\nGETS={len(texts)}\n')
    if not got:
        sys.exit(1)


if __name__ == '__main__':
    main(*sys.argv[1:6])
