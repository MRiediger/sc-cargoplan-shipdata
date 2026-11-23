"""A raw contract of scunpacked-data (contracts/<uuid>.json, the dumper's fields) -> one template of schema 1
(sc-cargoplan/docs/hauling-data-format.md with the addenda of the H1 approval), or the reason it is left out.

Field origin (S-H0: equal to api.star-citizen.wiki for all 1,843 hauling UUIDs of the 20 Nov dump):
  uuid UUID · debugName DebugName · title DisplayTitle (Title when empty) · released = not NotForRelease
  contractor MissionGiver (V4) · missionType MissionType.Name 'Hauling - <Type>' · reward FixedReward.Amount (null: none)
  legs HaulingOrders[] Name, MinScu, MaxScu, MaxContainerSize · pools MissionTokens 'Location<n>|Address' and
  'Destination<n>|Address' (names; resolved to starmap names in positions.py, K1)
Nothing is estimated (V8): a leg without an SCU band (MaxScu 0, the API's min_scu null), a container size outside the
set, or a form without a stop count leaves the template out with its reason."""
import re

PREFIXES = ('HaulCargo_', 'RedWind_Pyro_')
CONTRACTORS = {'Covalex Independent Contractors': 'covalex', 'Red Wind Linehaul': 'redWind'}
RANKS = ('trainee', 'rookie', 'junior', 'member', 'experienced', 'senior', 'master')     # V2: trainee first
SIZES = {'Extra Small': 'xs', 'Small': 'small', 'Medium': 'medium', 'Large': 'large', 'Bulk': 'bulk'}   # V3
SIZE_VALUES = tuple(SIZES.values())
CONTAINERS = (1, 2, 4, 8, 16, 24, 32)
MISSION_TYPES = ('local', 'planetary', 'stellar', 'interstellar')
SHAPES = ('aToB', 'singleToMulti', 'multiToSingle')
FACTIONS = ('hh', 'cfp')
GEO = re.compile(r'^(Stanton\d?|CrossStanton|Interstellar|TEMPLATE)$')
RED_WIND_AREA = re.compile(r'^(Solar|Region[A-D]|Planetary)$')
FORM = re.compile(r'^(?:(?P<atob>AToB)|SingleToMulti(?P<out>\d)|Multi(?P<in>\d)ToSingle)$', re.IGNORECASE)
TITLE = {'covalex': re.compile(r'^(?P<rank>\S+) Rank - (?P<direct>Direct )?(?P<size>.+) Cargo Haul$'),
         'redWind': re.compile(r'^(?P<rank>\S+) Hauler Needed for (?P<direct>Direct )?(?P<size>.+) Shipment$')}
PICKUP = re.compile(r'^Location\d*\|Address$', re.IGNORECASE)
DROPOFF = re.compile(r'^Destination\d*\|Address$', re.IGNORECASE)


class UnknownWord(ValueError):
    """A rank or size word the schema does not know, in a title of the known form: the hauling job stops (contract)."""


def candidate(raw: dict) -> bool:
    """One of the two naming schemes (design §7.1, §7.6); everything else is not a hauling template of schema 1."""
    return str(raw.get('DebugName') or '').startswith(PREFIXES)


def shape_of(token: str) -> tuple[str, int] | None:
    m = FORM.match(token)
    if not m:
        return None
    if m['atob']:
        return 'aToB', 1
    return ('singleToMulti', int(m['out'])) if m['out'] else ('multiToSingle', int(m['in']))


def place(debug: str, contractor: str) -> tuple[dict, str | None]:
    """Area, system, faction and form from the debug name, or the reason it does not parse."""
    parts = debug.split('_')
    if debug.startswith('RedWind_Pyro_'):
        area, faction = (parts[3], parts[4].lower()) if len(parts) > 5 else ('', '')
        if not RED_WIND_AREA.match(area) or faction not in FACTIONS:
            return {}, 'no area in the name'
        form = shape_of(parts[-1])
        if form is None:
            return {}, f'form without a stop count ({parts[-1]})'
        return {'system': 'pyro', 'areaKey': area, 'faction': faction, 'shape': form[0], 'stops': form[1]}, None
    geo = next((x for x in parts[2:] if GEO.match(x)), None)
    if geo is None:
        return {}, 'no area in the name'
    if geo == 'TEMPLATE':
        return {}, 'abstract template (TEMPLATE)'
    form = shape_of(parts[1])
    if form is None:
        return {}, f'form without a stop count ({parts[1]})'
    return {'system': None if geo == 'Interstellar' else 'stanton', 'areaKey': geo, 'faction': None,
            'shape': form[0], 'stops': form[1]}, None


def leg(o: dict) -> tuple[dict | None, str | None]:
    if o.get('Kind') != 'Resource':
        return None, f"order kind {o.get('Kind')}"
    lo, hi, box = o.get('MinScu'), o.get('MaxScu'), o.get('MaxContainerSize')
    if not hi:
        return None, 'leg without an SCU band'
    if box not in CONTAINERS:
        return None, f'container size {box}'
    if not isinstance(lo, int) or not isinstance(hi, int) or not 1 <= lo <= hi:
        return None, f'SCU band {lo}..{hi}'
    return {'commodity': o['Name'], 'minScu': lo, 'maxScu': hi, 'containerScu': box}, None


def pool(tokens: dict, key: re.Pattern) -> list[str]:
    return sorted({name for k, names in tokens.items() if key.match(k) for name in names or []})


def normalize(raw: dict) -> tuple[dict | None, str | None]:
    """(template, None) or (None, reason). Raises UnknownWord for a new rank or size word."""
    debug = raw['DebugName']
    if raw.get('NotForRelease') is not False:
        return None, 'not released'
    giver = raw.get('MissionGiver')
    contractor = CONTRACTORS.get(giver)
    if contractor is None:
        return None, f'other contractor ({giver})'
    where, why = place(debug, contractor)
    if why:
        return None, why
    title = raw.get('DisplayTitle') or raw.get('Title') or ''
    m = TITLE[contractor].match(title)
    if not m:
        return None, 'title not in the form of its contractor'
    rank, size = m['rank'].lower(), SIZES.get(m['size'])
    if rank not in RANKS or size is None:
        raise UnknownWord(f"{raw['UUID']} {debug}: title {title!r} has an unknown rank or size word")
    mission = (raw.get('MissionType') or {}).get('Name') or ''
    kind = mission.removeprefix('Hauling - ').lower()
    if not mission.startswith('Hauling - ') or kind not in MISSION_TYPES:
        return None, f'mission type {mission}'
    orders = raw.get('HaulingOrders') or []
    if not orders:
        return None, 'no hauling orders'
    legs = []
    for o in orders:
        one, why = leg(o)
        if why:
            return None, why
        legs.append(one)
    reward = (raw.get('FixedReward') or {}).get('Amount')
    tokens = raw.get('MissionTokens') or {}
    return {'uuid': raw['UUID'], 'debugName': debug, 'contractor': contractor, 'title': title, 'rank': rank, 'size': size,
            'direct': bool(m['direct']), 'shape': where['shape'], 'stops': where['stops'], 'system': where['system'],
            'areaKey': where['areaKey'], 'missionType': kind, 'faction': where['faction'],
            'reward': reward if isinstance(reward, int) else None, 'legs': legs,
            'pickupPool': pool(tokens, PICKUP), 'dropoffPool': pool(tokens, DROPOFF)}, None


def legs_as_expected(tpl: dict) -> bool:
    """K2: the leg count the dump shows for nearly all templates, min(stops x distinct commodities, 4). A hint in the
    changelog when it does not hold - never a loader rule."""
    return len(tpl['legs']) == min(tpl['stops'] * len({x['commodity'] for x in tpl['legs']}), 4)
