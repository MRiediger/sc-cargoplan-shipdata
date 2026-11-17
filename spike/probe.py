"""spike/probe.py - question 2 of S12.0: are the model URLs reachable from a runner? Throwaway measuring code, stdlib only.

HEAD every model URL of the catalog (200 ms apart, no retry, no GET), pick the spike ship (the first candidate whose
catalog model is the one holo-v3 was built from), GET only that model and check its SHA-256 against holo-v3's
manifest. Writes ship/className/slug/id/glb to $GITHUB_OUTPUT and numbers to $SPIKE_OUT/numbers.tsv.

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

    # 1) HEAD every model URL
    heads, seen = [], {}
    for cls in sorted(urls):
        status, secs, headers, _ = request(urls[cls], 'HEAD', ua)
        heads.append((cls, status, secs, int(headers.get('Content-Length', 0) or 0)))
        for k, v in headers.items():
            if k.lower().startswith(INTERESTING) and k not in seen:
                seen[k] = v
        time.sleep(0.2)
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

    # 2) Pick the ship: the first candidate (preferred first) whose catalog model is holo-v3's
    order = sorted(CANDIDATES, key=lambda c: c[0] != preferred)
    notes, pick = [], None
    for cls, slug, sid in order:
        m = manifest.get(slug)
        url = urls.get(cls, '')
        h12 = url.rsplit('-', 1)[-1].removesuffix('.glb') if url else ''
        if m and h12 and m['rawSha256'].startswith(h12):
            pick = (cls, slug, sid, url, m)
            break
        notes.append(f'{cls}: catalog model {h12 or "none"}, holo-v3 built from {m["rawSha256"][:12] if m else "none"}')
    if not pick:
        say('Pick the spike ship', 'candidates ' + ', '.join(c[0] for c in order), '; '.join(notes),
            'no candidate model is unchanged since holo-v3: pick another ship by hand')
        sys.exit(1)
    cls, slug, sid, url, m = pick

    # 3) GET that one model
    status, secs, headers, body = request(url, 'GET', ua)
    sha = hashlib.sha256(body).hexdigest()
    os.makedirs(glb_dir, exist_ok=True)
    glb = os.path.join(glb_dir, url.rsplit('/', 1)[-1])
    open(glb, 'wb').write(body)
    num('probe.model.get.status', status)
    num('probe.model.get.ms', round(1000 * secs))
    num('probe.model.bytes', len(body))
    num('probe.model.sha256.matches.holo-v3', sha == m['rawSha256'])
    say('Pick the spike ship and GET its model',
        f'candidates in order {", ".join(c[0] for c in order)}; model hash in the catalog URL against holo-v3 rawSha256',
        f'{cls} ({slug}, id {sid}){" after " + "; ".join(notes) if notes else ""}; GET {status} in {round(1000 * secs)} ms, '
        f'{len(body)} bytes, SHA-256 {"equals" if sha == m["rawSha256"] else "DIFFERS from"} holo-v3\'s model',
        'none' if status == 200 and sha == m['rawSha256'] else 'model not as in holo-v3: the byte comparisons below say nothing')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as f:
            f.write(f'cls={cls}\nslug={slug}\nid={sid}\nglb={glb}\nheads={len(heads)}\n')
    if status != 200:
        sys.exit(1)


if __name__ == '__main__':
    main(*sys.argv[1:6])
