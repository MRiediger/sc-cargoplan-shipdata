"""The rules of CLAUDE.md as code, used by verify. A finding with stop=True sends the run to the PR path (exit 2); the
others are hints in the summary. Pure functions on data, no files."""
from dataclasses import dataclass

MISSING_STOP = 3            # more newly gone ships without base than this stop the run (TASKS.md, Martin 17.11.)
BUDGET_SLACK = 1.1          # above 110 % of its budget step a hologram fails (judge in holo_mesh.py, run-all.ps1)


@dataclass
class Finding:
    rule: str
    id: str
    detail: str
    stop: bool
    proposal: dict | None = None


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


def judge(slug: str, pp: dict, previous: dict | None, new_model: bool) -> Finding | None:
    """A newly built hologram (PP.json). Martin, 17 Nov (plan P9): only a turn for the worse stops - passed=false when the
    last release had passed=true, the ship is new or got a new model. Above 110 % of the budget always stops. A ship
    published with passed=false (holo-v3: 22, approved on the contact sheet) and the same model is a hint."""
    if pp['triangles'] > BUDGET_SLACK * pp['budget']:
        return Finding('judge', slug, f"{pp['triangles']} triangles, above 110 % of its budget {pp['budget']}", True)
    if pp['passed']:
        return None
    fails = ', '.join(pp.get('fails', [])) or 'passed=false'
    if previous is None or previous.get('passed') or new_model:
        why = 'new ship' if previous is None else 'new model' if new_model else 'passed before'
        return Finding('judge', slug, f'fails {fails} ({why})', True)
    return Finding('judge', slug, f'fails {fails}, as published', False)
