"""Hauling data against the last release (H1, SD14): what the release's changelog says, and whether the content changed
at all - a change alone releases (SD14). Stamps (dataVersion, source.*) are never compared (rule C of T12.1)."""
import math

from shipdata.hauling.positions import MOVED_METRES


def by_uuid(doc: dict | None, key: str) -> dict[str, dict]:
    return {x['uuid']: x for x in (doc or {}).get(key) or []}


def compare(old_t: dict | None, new_t: dict, old_p: dict | None, new_p: dict) -> dict:
    a, b = by_uuid(old_t, 'templates'), by_uuid(new_t, 'templates')
    reward = [{'uuid': u, 'title': b[u]['title'], 'old': a[u]['reward'], 'new': b[u]['reward']}
              for u in sorted(a.keys() & b.keys()) if a[u]['reward'] != b[u]['reward']]
    other = [u for u in sorted(a.keys() & b.keys()) if a[u]['reward'] == b[u]['reward'] and a[u] != b[u]]
    pa, pb = by_uuid(old_p, 'positions'), by_uuid(new_p, 'positions')
    both = sorted(pa.keys() & pb.keys(), key=lambda u: pb[u]['name'])
    dist = {u: math.dist([pa[u][k] for k in 'xyz'], [pb[u][k] for k in 'xyz']) for u in both}
    d = {'templates': {'new': sorted(b.keys() - a.keys()), 'gone': sorted(a.keys() - b.keys()), 'reward': reward,
                       'otherwiseChanged': other, 'same': sum(1 for u in a.keys() & b.keys() if a[u] == b[u])},
         'positions': {'new': sorted(pb[u]['name'] for u in pb.keys() - pa.keys()),
                       'gone': sorted(pa[u]['name'] for u in pa.keys() - pb.keys()),
                       'renamed': [{'uuid': u, 'old': pa[u]['name'], 'new': pb[u]['name']} for u in both
                                   if pa[u]['name'] != pb[u]['name']],
                       'moved': [{'name': pb[u]['name'], 'metres': round(dist[u], 1)} for u in both if dist[u] > MOVED_METRES],
                       'contractNames': [pb[u]['name'] for u in both
                                         if pa[u].get('contractNames', []) != pb[u].get('contractNames', [])],
                       'same': sum(1 for u in both if pa[u] == pb[u])}}
    d['changed'] = ((old_t or {}).get('templates') != new_t.get('templates')
                    or (old_p or {}).get('positions') != new_p.get('positions'))
    return d


def changelog(d: dict | None, *, legs_off: int, excluded: dict[str, int], dropped: int,
              carried: tuple[str, str] | None) -> str:
    """The hauling paragraph of the release notes (Markdown). carried: (tag, reason) when this release carries the
    last release's files because the hauling job failed (K2)."""
    if carried is not None:
        tag, reason = carried
        return (f'**Hauling data:** carried forward unchanged from {tag} - this run\'s hauling job failed ({reason}); '
                'an issue or PR names the cause.\n')
    if d is None:
        return '**Hauling data:** none in this release.\n'
    t, p = d['templates'], d['positions']
    lines = [f"**Hauling templates:** {len(t['new'])} new, {len(t['gone'])} gone, {len(t['reward'])} reward changed, "
             f"{len(t['otherwiseChanged'])} otherwise changed, {t['same']} unchanged.",
             *[f"- {r['title']}: {r['old']} → {r['new']} aUEC" for r in t['reward'][:20]],
             f"**Places:** {len(p['new'])} new, {len(p['gone'])} gone, {len(p['renamed'])} renamed, "
             f"{len(p['moved'])} moved (> 1 km), {len(p['contractNames'])} with other contract names, {p['same']} unchanged.",
             *[f"- renamed {r['old']} → {r['new']}" for r in p['renamed'][:20]],
             *[f"- moved {r['name']} by {r['metres']:.0f} m" for r in p['moved'][:20]],
             f"Hints: {legs_off} templates whose leg count is not min(stops × commodities, 4) (K2); {dropped} pool names "
             'dropped by the alias table (V6); left out: '
             + (', '.join(f'{k} {v}' for k, v in sorted(excluded.items(), key=lambda kv: (-kv[1], kv[0]))) or 'none') + '.']
    return '\n'.join(lines) + '\n'
