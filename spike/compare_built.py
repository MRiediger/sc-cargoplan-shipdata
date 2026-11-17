"""spike/compare_built.py - question 1 of S12.0, platform drift: what the ubuntu chain built against what Windows built for
holo-v3 / v0.5.1. Throwaway measuring code, numpy only.

usage: python compare_built.py <slug> <id> <built PP.holo> <holo-v3 .holo> <holo-v3 manifest.json> <built PP.json>
                               <built ship-outlines.json> <v0.5.1 ship-outlines.json> <built ships dir> <v0.5.1 ships dir>
"""
import difflib, hashlib, json, os, struct, sys

import numpy as np

HEADER = struct.Struct('<4sHHI5I7f')        # as holo_mesh.py: magic, version, headerBytes, flags, 5 counts, lengthM, bounds
OUT = os.environ.get('SPIKE_OUT', 'out')
findings, todos = [], []


def num(key, value):
    with open(os.path.join(OUT, 'numbers.tsv'), 'a', encoding='utf-8') as f:
        f.write(f'{key}\t{value}\n')
    print(f'  # {key} = {value}')


def say(step, checked, found, todo):
    print(f'\n=== {step}\n  checked: {checked}\n  found:   {found}\n  to do:   {todo}\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(f'### {step}\n- **checked:** {checked}\n- **found:** {found}\n- **to do:** {todo}\n\n')


def holo(built, ref):
    a, b = open(built, 'rb').read(), open(ref, 'rb').read()
    same = a == b
    num('compare.holo.bytes.equal', same)
    if same:
        return f'holo byte-equal ({len(a)} B, SHA-256 {hashlib.sha256(a).hexdigest()[:12]})'
    ha, hb = HEADER.unpack_from(a), HEADER.unpack_from(b)
    counts_a, counts_b = ha[4:9], hb[4:9]
    text = f'holo differs: {len(a)} B vs {len(b)} B, counts {counts_a} vs {counts_b}'
    if counts_a[0] == counts_b[0]:
        n = counts_a[0]
        va = np.frombuffer(a, '<f4', 3 * n, HEADER.size).reshape(-1, 3)
        vb = np.frombuffer(b, '<f4', 3 * n, HEADER.size).reshape(-1, 3)
        dev = float(np.abs(va.astype(np.float64) - vb).max())
        num('compare.holo.vertex.maxdev.m', dev)
        text += f', max vertex deviation {dev:.3g} m'
    todos.append('holo not byte-equal: the gate compares pictures (gate-b), the threshold of question 4 applies')
    return text


def pp(pp_path, manifest_path, slug):
    built = json.load(open(pp_path, encoding='utf-8'))
    ref = next(s for s in json.load(open(manifest_path, encoding='utf-8'))['ships'] if s['slug'] == slug)
    # PP.json holds the metrics flat; release_v2 nests them under "metrics" in the manifest
    flat = dict(ref, **ref.get('metrics', {}))
    keys = ['budget', 'triangles', 'edges', 'passed', 'bytes'] + sorted(ref.get('metrics', {}))
    diff = {k: (built.get(k), flat.get(k)) for k in keys if built.get(k) != flat.get(k)}
    num('compare.pp.metrics.equal', not diff)
    return 'PP.json metrics equal to the manifest' if not diff else f'PP.json differs from the manifest: {json.dumps(diff)}'


def outlines(built, ref, slug):
    a, b = open(built, 'rb').read(), open(ref, 'rb').read()
    num('compare.outlines.file.bytes.equal', a == b)
    ea = next(s for s in json.loads(a)['ships'] if s['slug'] == slug)
    eb = next(s for s in json.loads(b)['ships'] if s['slug'] == slug)
    others = [s for s in json.loads(a)['ships'] if s['slug'] != slug] == [s for s in json.loads(b)['ships'] if s['slug'] != slug]
    if ea == eb:
        num('compare.outline.entry.equal', True)
        return f'ship-outlines.json {"byte-equal" if a == b else "differs outside the entry"}; entry {slug} equal'
    num('compare.outline.entry.equal', False)
    text = f'entry {slug} differs: points {len(ea["outline"])} vs {len(eb["outline"])}'
    for k in ('lengthM', 'beamM', 'heightM', 'floorM'):
        if ea.get(k) != eb.get(k):
            text += f', {k} {ea.get(k)} vs {eb.get(k)}'
    if len(ea['outline']) == len(eb['outline']):
        dev = float(np.abs(np.array(ea['outline']) - np.array(eb['outline'])).max()) * 1000
        num('compare.outline.points.maxdev.mm', dev)
        text += f', max point deviation {dev:.3g} mm'
    todos.append('outline not equal: compare pictures (look outline) in gate-b')
    return text + f'; other entries {"equal" if others else "DIFFER"}'


def ships(built_dir, ref_dir, sid):
    norm = lambda p: open(p, 'rb').read().replace(b'\r\n', b'\n')
    changed = []
    for name in sorted(os.listdir(ref_dir)):
        if name.endswith('.json') and os.path.exists(os.path.join(built_dir, name)):
            if norm(os.path.join(built_dir, name)) != norm(os.path.join(ref_dir, name)):
                changed.append(name[:-5])
    num('compare.ships.changed.count', len(changed))
    num('compare.ships.changed', ','.join(changed))
    f = f'{sid}.json'
    a, b = norm(os.path.join(built_dir, f)), norm(os.path.join(ref_dir, f))
    num('compare.ship.json.equal.lf', a == b)
    if a == b:
        text = f'{f} byte-equal to v0.5.1 (LF-normalized)'
    else:
        diff = ''.join(difflib.unified_diff(b.decode().splitlines(True), a.decode().splitlines(True), 'v0.5.1', 'built', n=1))
        print(diff)
        text = f'{f} DIFFERS from v0.5.1 (diff in the log)'
        todos.append(f'{f} not byte-equal: see the diff, decide whether the import must be pinned to one PowerShell')
    return text + f'; the import rewrote {len(changed)} of the ship files: {", ".join(changed[:15]) or "none"}'


def main(slug, sid, built_holo, ref_holo, manifest, pp_json, built_outlines, ref_outlines, built_ships, ref_ships):
    for part in (lambda: holo(built_holo, ref_holo), lambda: pp(pp_json, manifest, slug),
                 lambda: outlines(built_outlines, ref_outlines, slug), lambda: ships(built_ships, ref_ships, sid)):
        try:
            findings.append(part())
        except Exception as e:                              # a measurement that fails is a finding, not a stop
            findings.append(f'comparison failed: {type(e).__name__}: {e}')
            todos.append('fix the comparison')
    say('Compare built data with holo-v3 / v0.5.1',
        f'{slug}: .holo bytes, PP.json against the holo-v3 manifest, ship-outlines.json, ships/{sid}.json',
        '; '.join(findings), '; '.join(todos) or 'none: the ubuntu chain is byte-equal to the Windows build')


if __name__ == '__main__':
    main(*sys.argv[1:11])
