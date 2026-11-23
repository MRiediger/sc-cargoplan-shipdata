"""Pool names -> starmap entries, and positions.json (H1, SD14; K1 and K3 of the approval).

starmap_positions.json (StarCitizenWiki/scunpacked-data): {entities: [{uuid, name, type, system, parent_uuid, hidden,
qt_valid, x, y, z}], connections: [...]}, metres in system coordinates (design §9.3).

Resolution of a pool name, in this order:
  1. the alias table (tools/hauling-aliases.json): {"uuid", "starmap"} names the entry by uuid - a rename in the starmap
     stays resolved, with a hint; {"drop": reason} takes the name out of the pool (V6: placeholder texts, caves, generic
     names - no position exists)
  2. the exact name in the template's system; a template without a system (interstellar) needs the name to be unique in
     all three systems
  anything else is a gap: the hauling job stops, and hauling-pr proposes the alias (E1).
K1: a position carries the starmap name; the pools are rewritten to it; the contract forms of the alias table go into
contractNames. One position per uuid. K3: a name is unique per system; the first in starmap order wins, a pool's entry
wins over one that is only in the file by the filter."""
import re
from collections import Counter
from dataclasses import dataclass, field

SYSTEMS = ('stanton', 'pyro', 'nyx')
TYPES = ('Manmade', 'Manmade_VisibleOnInteraction', 'Planet', 'Star')    # stations, planets, the star (map centre)
MOVED_METRES = 1000.0           # SD14: a place counts as moved beyond 1 km (JSON rounding is far below 1 m)
CANDIDATES = 5


@dataclass
class Gap:
    name: str
    system: str | None
    why: str
    templates: list[str]
    candidates: list[dict]


@dataclass
class Resolution:
    templates: list[dict]
    used: set[str] = field(default_factory=set)
    gaps: list[Gap] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    dropped: Counter = field(default_factory=Counter)


class Starmap:
    """The entries of the three systems with an identity of their own: an entry whose uuid other entries share (4.10.3:
    12 uuids for 617 asteroids, points of interest and 'unknown' entries) is neither resolved nor written."""
    def __init__(self, doc: dict) -> None:
        mine = [e for e in doc['entities'] if e.get('system') in SYSTEMS]
        count = Counter(e['uuid'] for e in mine)
        self.entities = [e for e in mine if count[e['uuid']] == 1]
        self.shared = sum(1 for n in count.values() if n > 1)
        self.by_uuid = {e['uuid']: e for e in self.entities}

    def named(self, name: str, system: str | None) -> list[dict]:
        return [e for e in self.entities if e['name'] == name and (system is None or e['system'] == system)]

    def like(self, name: str, system: str | None) -> list[dict]:
        """Proposals for a gap: entries whose name starts the pool name ('Checkmate at the L4 Lagrange of Pyro II' ->
        Checkmate), else entries whose name is part of it or the other way round (case-insensitive, words only). Never
        used to resolve, only to propose."""
        key = f' {words(name)} '
        pool = [(e, f' {words(e["name"])} ') for e in self.entities
                if (system is None or e['system'] == system) and words(e['name'])]
        strong = [e for e, w in pool if key.startswith(w)]
        weak = [e for e, w in pool if w in key or key in w]
        return [brief(e) for e in (strong or weak)[:CANDIDATES]]


def words(text: str) -> str:
    return ' '.join(re.findall(r'[a-z0-9]+', text.casefold()))


def brief(e: dict) -> dict:
    return {'uuid': e['uuid'], 'name': e['name'], 'system': e['system'], 'type': e['type']}


def resolve(templates: list[dict], starmap: Starmap, aliases: dict[str, dict]) -> Resolution:
    """Every pool name of every template; the templates come back with starmap names in their pools (K1)."""
    out = Resolution(templates=[])
    gaps: dict[tuple[str, str | None], Gap] = {}
    hinted: set[str] = set()

    def one(name: str, tpl: dict) -> str | None:
        system = tpl['system']
        alias = aliases.get(name)
        if alias is not None and 'drop' in alias:
            out.dropped[name] += 1
            return None
        if alias is not None:
            e = starmap.by_uuid.get(alias['uuid'])
            if e is None:
                why, cands = 'the alias names a uuid the starmap does not have', starmap.like(alias.get('starmap') or name, system)
            else:
                if e['name'] != alias.get('starmap') and name not in hinted:
                    hinted.add(name)
                    out.hints.append(f"alias {name!r}: the starmap calls {alias['uuid']} {e['name']!r} now, the table says "
                                     f"{alias.get('starmap')!r} (renamed)")
                out.used.add(e['uuid'])
                return e['name']
        else:
            found = starmap.named(name, system)
            if len(found) == 1:
                out.used.add(found[0]['uuid'])
                return name
            why = 'no starmap entry of that name' if not found else f'ambiguous: {len(found)} starmap entries of that name'
            cands = [brief(e) for e in found] if found else starmap.like(name, system)
        g = gaps.setdefault((name, system), Gap(name, system, why, [], cands))
        g.templates.append(tpl['uuid'])
        return None

    for tpl in templates:
        new = dict(tpl)
        for key in ('pickupPool', 'dropoffPool'):
            new[key] = sorted({n for n in (one(x, tpl) for x in tpl[key]) if n is not None})
        out.templates.append(new)
    out.gaps = sorted(gaps.values(), key=lambda g: (g.name, g.system or ''))
    return out


def build(starmap: Starmap, used: set[str], aliases: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """positions[]: the stations, planets and stars of the three systems (not hidden) and every entry a pool resolved
    to; sorted by system, then name."""
    chosen = [e for e in starmap.entities if e['uuid'] in used or (e['type'] in TYPES and not e.get('hidden'))]
    hints: list[str] = []
    keep: dict[tuple[str, str], dict] = {}
    for e in sorted(chosen, key=lambda e: e['uuid'] not in used):      # stable: pool entries first, then starmap order
        k = (e['system'], e['name'])
        if k in keep:
            hints.append(f"{e['name']!r} twice in {e['system']}: {keep[k]['uuid']} kept, {e['uuid']} left out (K3)")
            continue
        keep[k] = e
    names = {e['uuid']: e['name'] for e in keep.values()}
    forms: dict[str, list[str]] = {}
    for name, a in aliases.items():
        if 'uuid' in a and a['uuid'] in names:
            forms.setdefault(a['uuid'], []).append(name)
    out = [{'uuid': e['uuid'], 'name': e['name'], 'system': e['system'], 'type': e['type'],
            'parent': names.get(e.get('parent_uuid')), 'x': e['x'], 'y': e['y'], 'z': e['z'],
            'contractNames': sorted(forms.get(e['uuid'], []))}
           for e in keep.values()]
    return sorted(out, key=lambda x: (x['system'], x['name'])), hints


def propose(aliases: dict[str, dict], gaps: list[Gap]) -> dict[str, dict]:
    """The alias table with one entry per gap, for hauling-pr (E1): a unique candidate by uuid, otherwise a drop with the
    candidates named - Martin's merge accepts it, or he edits the entry in the PR first."""
    out = dict(aliases)
    for g in gaps:
        if len(g.candidates) == 1:
            out[g.name] = {'uuid': g.candidates[0]['uuid'], 'starmap': g.candidates[0]['name']}
        else:
            named = '; '.join(f"{c['name']} ({c['system']}, {c['uuid']})" for c in g.candidates) or 'none'
            out[g.name] = {'drop': f'no unique starmap entry ({g.why}; candidates: {named}) - replace with uuid and '
                                   'starmap if the place exists'}
    return dict(sorted(out.items()))
