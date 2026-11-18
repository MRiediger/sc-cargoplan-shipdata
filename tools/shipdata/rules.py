"""The rules of CLAUDE.md as code, used by verify. A finding with stop=True sends the run to the PR path (exit 2); the
others are hints in the summary. Pure functions on data, no files."""
from dataclasses import dataclass

MISSING_STOP = 3            # more newly gone ships without base than this stop the run (TASKS.md, Martin 17.11.)
BUDGET_SLACK = 1.1          # above 110 % of its budget step a hologram fails (judge in holo_mesh.py, run-all.ps1)
HAUSDORFF_TOLERANCE = 0.0025    # SD5 case 3: one judge pixel at 512 px (~0.002) passes, two stop; T12.1b: re-export noise 0 px
HAUSDORFF_KEYS = ('topHausdorff', 'sideHausdorff', 'frontHausdorff')


@dataclass
class Finding:
    rule: str
    id: str
    detail: str
    stop: bool
    proposal: dict | None = None
    data: dict | None = None        # the finding as fields for verify.json and the PR text (E1); detail is for the log


@dataclass
class Missing:
    follows: dict[str, str]                 # gone variant -> base ship whose data it takes
    missing_since: dict[str, str]           # gone ship -> date it was first missed
    newly_without_base: list[str]           # gone in this run for the first time, no base


def missing(gone: list[str], previous: dict[str, dict], present: set[str], today: str) -> Missing:
    """Rule "gone from the catalog": never delete. A gone ship whose racks were hash-equal to a present ship's of the same
    modelKey in the last manifest is a variant of it and takes its data (S12.0: the six variants of 17 Nov); any other gone
    ship keeps its last state with missingSince, the date stays from the run that first missed it."""
    follows, since, newly = {}, {}, []
    for sid in sorted(gone):
        p = previous.get(sid, {})
        base = next((b for b in sorted(present) if b in previous and b != sid and previous[b].get('modelKey') == p.get('modelKey')
                     and previous[b].get('racksSha256') == p.get('racksSha256')), None) if p.get('modelKey') else None
        if base:
            follows[sid] = base
            continue
        since[sid] = p.get('missingSince') or today
        if not p.get('missingSince'):
            newly.append(sid)
    return Missing(follows, since, newly)


def back(previous: dict[str, dict], present: set[str]) -> dict[str, str]:
    """Rule "back" (SD6, E1): a ship the last manifest had as gone (missingSince) or as a variant following its base
    (follows), in the catalog again. Both fields are cleared; the ship goes through diff, build and judge like any other
    (a change of source is judge case 4). Returns id -> what it was."""
    out = {}
    for sid in sorted(present & set(previous)):
        p = previous[sid]
        if p.get('missingSince'):
            out[sid] = f"missing since {p['missingSince']}"
        elif p.get('follows'):
            out[sid] = f"followed {p['follows']}"
    return out


def too_many_gone(newly_without_base: list[str]) -> Finding | None:
    n = len(newly_without_base)
    if n <= MISSING_STOP:
        return None
    return Finding('gone', ','.join(newly_without_base), f'{n} ships newly gone without a base ship (more than {MISSING_STOP}): '
                   'a catalog change this big needs a look', True)


def import_findings(entries: list[dict], overrides: dict[str, dict]) -> list[Finding]:
    """The import's report: overlapping grids (K1) and any other hand check stop, so do grids in another order and a
    modeled ship without anchors. A grid without transform keeps the ship as it is: a hint with its entry in
    overrides.json, a stop with a proposed entry without one (A15: the PR carries the entry, nobody types it)."""
    out = []
    for e in entries:
        sid, status, detail = e['id'], e['status'], e.get('detail') or ''
        if status == 'handcheck':
            out.append(Finding('overlap' if detail.startswith('grids overlap') else 'handcheck', sid, detail, True))
        elif status == 'order':
            out.append(Finding('order', sid, detail, True))
        elif status == 'kept':
            if sid in overrides:
                out.append(Finding('no-transform', sid, f"stays as it is (overrides.json: {overrides[sid].get('reason', '')})", False))
            else:
                out.append(Finding('no-transform', sid, f'{detail}; no entry in overrides.json', True,
                                   {'id': sid, 'reason': 'a grid without transform in the catalog: the ship stays as it is',
                                    'date': None}))
        elif e.get('anchorsKept') and status in ('same', 'updated', 'created'):
            out.append(Finding('anchors', sid, f"no floorM for {e.get('modelKey')}: no anchors from the model", True))
    return out


def hausdorff(numbers: dict) -> float | None:
    """The judge's Hausdorff distance: the worst of the three views, as holo_mesh.judge measures it (plan P4)."""
    if not all(k in numbers for k in HAUSDORFF_KEYS):
        return None
    return max(numbers[k] for k in HAUSDORFF_KEYS)


def judge(slug: str, pp: dict, previous: dict | None, class_name: str) -> Finding | None:
    """A newly built hologram (PP.json) against its entry in the last manifest (SD5, replaces P9): a turn for the worse
    is a metric, not a flag. The last hologram is comparable when it was built from the same className - a re-export is;
    a new ship or a change of source (fleetyards (holo-v1) -> a Motherlode model) is not. Cases that stop:
      1 passed turns false; 2 above 110 % of the budget; 3 both failed and Hausdorff worse by more than the tolerance;
      4 no comparable hologram; 5 failed and a metric fails that did not before.
    Otherwise a failed hologram is a note and a passed one nothing."""
    comparable = previous is not None and previous.get('model') == class_name
    old = previous or {}
    new_h, old_h = hausdorff(pp), hausdorff(old.get('metrics') or {})
    delta = round(new_h - old_h, 4) if new_h is not None and old_h is not None else None
    fails, old_fails = list(pp.get('fails', [])), old.get('fails')
    cases = []
    if pp['triangles'] > BUDGET_SLACK * pp['budget']:
        cases.append(2)
    if not comparable:
        cases.append(4)
    elif old['passed'] and not pp['passed']:
        cases.append(1)
    elif not old['passed'] and not pp['passed']:
        if set(fails) - set(old_fails):
            cases.append(5)
        if delta is not None and delta > HAUSDORFF_TOLERANCE:
            cases.append(3)
    if not cases and pp['passed']:
        return None
    cases.sort()
    data = {'cases': cases, 'model': {'old': old.get('model'), 'new': class_name},
            'passed': {'old': old.get('passed'), 'new': pp['passed']}, 'fails': {'old': old_fails, 'new': fails},
            'hausdorff': {'old': old_h, 'new': new_h, 'delta': delta, 'tolerance': HAUSDORFF_TOLERANCE},
            'triangles': {'old': old.get('triangles'), 'new': pp['triangles']},
            'budget': {'old': old.get('budget'), 'new': pp['budget']}}
    why = {1: 'passed turns false', 2: f"{pp['triangles']} triangles, above 110 % of its budget {pp['budget']}",
           3: f'hausdorff worse by more than {HAUSDORFF_TOLERANCE}', 5: f"fails {', '.join(sorted(set(fails) - set(old_fails or [])))} now too",
           4: 'new ship' if previous is None else f"no comparable hologram ({old.get('model')} -> {class_name})"}
    detail = (('; '.join(f'SD5 case {c}: {why[c]}' for c in cases) or f"fails {', '.join(fails)}, comparable to the last release")
              + (f'; hausdorff {old_h} -> {new_h} ({delta:+})' if delta is not None else ''))
    return Finding('judge', slug, detail, bool(cases), data=data)
