#!/usr/bin/env bash
# spike/chain-job.sh <preferred className> - the chain job of spike.yml after the fetch (S12.0), one script for the runner
# and for a local test in WSL Ubuntu 24.04: catalog through fetch-motherlode.ps1 (offline) -> probe and models -> chain
# (old model = holo-v3's, new model = the catalog's if it differs) -> outlines-v2 + anchor -> comparisons -> built/.
# Expects in the working directory: cache/raw/{api.json,page.txt,api.status,page.status,*.headers}, app/ (sc-cargoplan at
# the tag). Env: SPIKE_OUT, HOLO_WORK, UA, APP_REPO, HOLO_TAG, FETCHED (1 = the API was called in this run), PY,
# PROBE_HEAD (0 = no HEAD burst, local tests). Every stage ends with "checked / found / to do"; exit 1 if a stage failed.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/say.sh"
PREFERRED=${1:-ORIG_100i}
PY=${PY:-python}
ROOT=$PWD
failed=()
mkdir -p work/motherlode built "$HOLO_WORK"

hdr() { grep -iE '^(HTTP/|x-?ratelimit|ratelimit|retry-after|cf-|server:|content-type:|age:|x-vercel|via:)' "$1" 2>/dev/null | tr -d '\r' | paste -sd ' ' -; }

# 1) API answer and page, as cached
origin=$([ "${FETCHED:-0}" = 1 ] && echo "fetched in this run" || echo "from the cache, fetched $(cat cache/raw/fetched-at 2>/dev/null)")
read -r ac at as < cache/raw/api.status || true
read -r pc pt pb < cache/raw/page.status || true
num api.status "$ac"; num api.s "$at"; num api.bytes "$as"; num page.status "$pc"; num page.s "$pt"; num page.bytes "$pb"
num api.headers "$(hdr cache/raw/api.headers)"; num page.headers "$(hdr cache/raw/page.headers)"
marks=$(grep -c '"ships":\[' cache/raw/page.txt 2>/dev/null || true)
say "Motherlode API and cargo page" \
    "API GET /api/public/v1/cargo-grids (Bearer secret) and page GET /ops/cargo (RSC: 1), $origin" \
    "API HTTP $ac in ${at} s, $as bytes, headers: $(hdr cache/raw/api.headers); page HTTP $pc in ${pt} s, $pb bytes, \"ships\" array: ${marks:-0}, headers: $(hdr cache/raw/page.headers)" \
    "$([ "$ac" = 200 ] && [ "$pc" = 200 ] && [ "${marks:-0}" != 0 ] && echo none || echo 'API or page not usable from the runner: finding for T12.1')"

# 2) Catalog through the unchanged fetch script, offline
pagefile=cache/raw/page.txt
if [ "${marks:-0}" = 0 ]; then
    $PY -c "import json, sys; sys.path.insert(0, '$HERE'); import probe; print(json.dumps({'ships': [{'modelUrl': u} for u in probe.FALLBACK.values()]}, separators=(',', ':')))" > work/page-fallback.txt
    pagefile=work/page-fallback.txt
    echo "page not usable: model URLs from the 16 Nov catalog (fallback)"
fi
rc=0; t=$(now)
pwsh -NoProfile -File "$HERE/fetch-motherlode.ps1" -ApiResponse "$ROOT/cache/raw/api.json" -PageResponse "$ROOT/$pagefile" \
     -OutDir "$ROOT/work/motherlode" -SkipModels || rc=$?
num catalog.fetch-ps1.s "$(since "$t")"; num catalog.fetch-ps1.rc "$rc"
CAT=$(ls "$ROOT"/work/motherlode/catalog-*.json 2>/dev/null | head -n 1 || true)
if [ -n "$CAT" ]; then
    read -r build nships nmodels sha bytes crlf < <($PY -c "import hashlib, json, sys; b = open(sys.argv[1], 'rb').read(); c = json.loads(b.decode('utf-8-sig')); print(c['gameBuild'], len(c['ships']), sum(1 for s in c['ships'] if s.get('modelUrl')), hashlib.sha256(b).hexdigest(), len(b), b.count(b'\r\n'))" "$CAT")
    appsrc=$($PY -c "import json; print(json.load(open('app/ships/100i.json'))['source'])")
    num catalog.gameBuild "$build"; num catalog.ships "$nships"; num catalog.withModel "$nmodels"
    num catalog.sha256 "$sha"; num catalog.bytes "$bytes"; num catalog.crlf "$crlf"
    found="exit $rc; game build $build (v0.5.1 ships say: $appsrc); $nships ships, $nmodels with a model URL; $bytes bytes, SHA-256 ${sha:0:16}, CRLF lines $crlf"
else
    found="exit $rc; no catalog written"; failed+=(catalog)
fi
num cache.bytes "$(du -sb cache | cut -f1)"
say "Catalog (fetch-motherlode.ps1 offline under pwsh $(pwsh -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'))" \
    "the saved API answer and page through the unchanged script: format checks, join by className" \
    "$found; cache folder $(du -sb cache | cut -f1) bytes" \
    "$([ -n "$CAT" ] && echo none || echo 'no catalog: anchor skipped, the chain runs from the fallback model URL')"

# 3) Scraper probe, ship and models
curl -sSL -o work/holo-v3-manifest.json "https://github.com/$APP_REPO/releases/download/$HOLO_TAG/manifest.json"
export PROBE_OUT="$SPIKE_OUT/ship.env"
if ! $PY "$HERE/probe.py" "${CAT:--}" work/holo-v3-manifest.json "$PREFERRED" work/models "$UA"; then
    say "Spike ship" "probe.py" "no model could be fetched" "see the log above"
    exit 1
fi
source "$PROBE_OUT"
num requests "${FETCHED:-0} API, ${FETCHED:-0} page GET, $HEADS HEAD, $GETS model GET"
say "Outbound requests to Motherlode and its model bucket (E2)" "every request to cryon.rocks and the Supabase bucket in this run" \
    "${FETCHED:-0} API call, ${FETCHED:-0} page GET, $HEADS HEAD, $GETS model GET" \
    "$([ "$GETS" -gt 1 ] && echo 'second model GET: the catalog model differs from holo-v3s (re-export), both are measured' || echo none)"

# 4) Chain: old model (platform drift), new model (re-export) if it differs
chain() {   # <label> <glb> <work root>
    local rc=0 t; t=$(now)
    CHAIN_KEY=chain-$1 HOLO_WORK=$3 bash "$HERE/chain.sh" "$CLS" "$2" || rc=$?
    num "chain.$1.total.s" "$(since "$t")"; num "chain.$1.rc" "$rc"
    say "Chain on ubuntu, $1 model ($CLS, $(basename "$2"))" \
        "holo_mesh.py flatten-model, cull, simplify.mjs ref + PP ladder, export, outline - as decimate.ps1 -Source Motherlode, called from bash" \
        "exit $rc; $(grep -P "^chain-$1\." "$SPIKE_OUT/numbers.tsv" | tr '\t' '=' | paste -sd ' ' -)" \
        "$([ $rc = 0 ] && echo 'none; decimate.ps1/run-all.ps1 themselves would need .venv/bin/python and forward slashes' || echo 'chain failed: see the log')"
    return $rc
}
chain old "$GLB" "$HOLO_WORK" || failed+=(chain-old)
[ -n "$GLB_NEW" ] && { chain new "$GLB_NEW" "$ROOT/work/holo-new" || failed+=(chain-new); }

# 5) Outlines and anchor (old model's outline, so gate-b measures platform drift)
prev="$ROOT/app/outlines/ship-outlines.json"
read -r gen dv < <($PY -c "import json, sys; d = json.load(open(sys.argv[1])); print(d['generatedAt'], d['dataVersion'])" "$prev")
keep=$($PY -c "import json, sys; print(' '.join(s['slug'] for s in json.load(open(sys.argv[1]))['ships'] if s['slug'] != sys.argv[2]))" "$prev" "$SLUG")
if [ -n "$CAT" ]; then
    # Date fix (review of the S12.0 findings): pwsh 7 reads updatedAt as a DateTime and writes it into "source" in the
    # culture's format. -DateKind String (pwsh >= 7.5) keeps the API's string; Windows PowerShell 5.1 has no such
    # parameter and keeps strings anyway. Measured on the 16 Nov archive: 0 of 108 ship files differ on pwsh 7.6.10 and
    # on 5.1 (without the fix 104 on pwsh 7; with ToString("o") still 104: seven fraction digits instead of three).
    # Patched into the checked-out copy only; the import moves into this repo with T12.1.
    sed -i 's/^\(\s*\)\$parsed = Get-Content -LiteralPath \$Path -Raw -Encoding UTF8 | ConvertFrom-Json$/\1$cf = @{}; if ((Get-Command ConvertFrom-Json).Parameters.ContainsKey("DateKind")) { $cf.DateKind = "String" }\n\1$parsed = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json @cf/' app/tools/import-motherlode.ps1
    grep -q 'ConvertFrom-Json @cf' app/tools/import-motherlode.ps1 || { echo "date fix did not apply"; failed+=(date-fix); }
    rm -rf work/ships; cp -r app/ships work/ships
    rc1=0; t=$(now)
    pwsh -NoProfile -File app/tools/import-motherlode.ps1 -Catalog "$CAT" -ShipsFolder "$ROOT/work/ships" -Outlines "$prev" \
         -ModelMap "$ROOT/work/model-map.csv" > work/import1.log 2>&1 || rc1=$?
    num anchor.import1.s "$(since "$t")"; num anchor.import1.rc "$rc1"
    tail -n 40 work/import1.log | sed 's/^/  /'
fi
{ echo 'id,className,modelKey,sx,sy,sz'; grep "^$ID,$CLS," work/model-map.csv 2>/dev/null || echo "$ID,$CLS,$SLUG,0,0,0"; } > work/map-one.csv
t=$(now)
HOLO_WORK=$HOLO_WORK $PY -I "$HERE/holo_mesh.py" outlines-v2 work/map-one.csv "$prev" work/ship-outlines.json "$gen" "$dv" $keep || failed+=(outlines-v2)
num anchor.outlines-v2.s "$(since "$t")"
[ -n "$GLB_NEW" ] && HOLO_WORK=$ROOT/work/holo-new $PY -I "$HERE/holo_mesh.py" outlines-v2 work/map-one.csv "$prev" work/ship-outlines-new.json "$gen" "$dv" $keep
if [ -n "$CAT" ]; then
    rc2=0; t=$(now)
    pwsh -NoProfile -File app/tools/import-motherlode.ps1 -Catalog "$CAT" -ShipsFolder "$ROOT/work/ships" -Outlines "$ROOT/work/ship-outlines.json" \
         -ModelMap "$ROOT/work/model-map-2.csv" > work/import2.log 2>&1 || rc2=$?
    num anchor.import2.s "$(since "$t")"; num anchor.import2.rc "$rc2"
    tail -n 40 work/import2.log | sed 's/^/  /'
    [ "$rc1" = 2 ] || [ "$rc2" = 2 ] && failed+=(import)
    say "Outlines and anchor" \
        "import-motherlode.ps1 ($APP_TAG) under pwsh on Linux with the catalog: model map, racks; outlines-v2 with only $SLUG rebuilt (old model); import again for the anchor from the new floorM" \
        "import 1 exit $rc1, import 2 exit $rc2 (0 done, 1 something to look at, 2 error); map row: $(sed -n 2p work/map-one.csv)" \
        "$([ "$rc1" = 2 ] || [ "$rc2" = 2 ] && echo 'the import errs on Linux: see the log' || echo 'none; exit 1 lists what a person would look at')"
fi

# 6) Comparisons with holo-v3 / v0.5.1
curl -sSL -o work/ref.holo "https://github.com/$APP_REPO/releases/download/$HOLO_TAG/$SLUG.holo"
COMPARE_LABEL="old model = holo-v3's" COMPARE_KEY=compare $PY "$HERE/compare_built.py" "$SLUG" "$ID" \
    "$HOLO_WORK/$CLS/PP.holo" work/ref.holo work/holo-v3-manifest.json "$HOLO_WORK/$CLS/PP.json" \
    work/ship-outlines.json app/outlines/ship-outlines.json "$([ -d work/ships ] && echo work/ships || echo -)" app/ships
if [ -n "$GLB_NEW" ]; then
    COMPARE_LABEL="new model = the catalog's" COMPARE_KEY=compare-new $PY "$HERE/compare_built.py" "$SLUG" "$ID" \
        "$ROOT/work/holo-new/$CLS/PP.holo" work/ref.holo work/holo-v3-manifest.json "$ROOT/work/holo-new/$CLS/PP.json" \
        work/ship-outlines-new.json app/outlines/ship-outlines.json - app/ships
fi

# 7) Built data for gate-b (old model)
echo "$ID $SLUG $CLS" > built/ship.txt
cp "$HOLO_WORK/$CLS/PP.holo" "built/$SLUG.holo" 2>/dev/null || true
cp "$HOLO_WORK/$CLS"/*.json built/ 2>/dev/null || true
cp work/ship-outlines.json built/ 2>/dev/null || true
cp "work/ships/$ID.json" built/ 2>/dev/null || cp "app/ships/$ID.json" built/
cp work/model-map.csv work/*.log built/ 2>/dev/null || true
[ -n "$GLB_NEW" ] && { mkdir -p built/new; cp "$ROOT/work/holo-new/$CLS/PP.holo" "built/new/$SLUG.holo"; cp "$ROOT/work/holo-new/$CLS"/*.json work/ship-outlines-new.json built/new/ 2>/dev/null || true; }
ls -l built
if [ ${#failed[@]} -gt 0 ]; then
    echo "failed stages: ${failed[*]}"
    exit 1
fi
