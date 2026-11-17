#!/usr/bin/env bash
# spike/chain.sh <className> <model.glb> - the hologram chain of sc-ship-outlines' decimate.ps1 -Source Motherlode
# (called by run-all.ps1) for one model, step by step with timings (S12.0). Same order and arguments: MinPixels 2,
# ref error 0.0005 x length, PP ladder 20k/30k/40k with error 0.005 x length, SliverLimit 0.1563, stop at the first
# step without fails; then holo_mesh.py outline (TOOLS.md step 4). Works in $HOLO_WORK/<className>/.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/say.sh"
CLS=$1
GLB=$2
PY=${PY:-python}
MESH="$HERE/holo_mesh.py"
SIMP="$HERE/simplify.mjs"
W="$HOLO_WORK/$CLS"
mkdir -p "$W"

step() {
    local name=$1; shift
    local t; t=$(now)
    "$@" > "$W/$name.out"
    num "${CHAIN_KEY:-chain}.$name.s" "$(since "$t")"
    sed 's/^/  /' "$W/$name.out"
}
jget() { $PY -c "import json,sys; v=json.load(open(sys.argv[1]))$2; print(v)" "$1"; }

step flatten $PY -I "$MESH" flatten-model "$CLS" "$GLB"
LEN=$(jget "$W/flat.json" "['lengthM']")
step cull $PY -I "$MESH" cull "$CLS" 2
step ref node "$SIMP" "$W/shell.bin" "$W/ref.idx" 200000 "$($PY -c "print(0.0005 * $LEN)")" ref
final=
for b in 20000 30000 40000; do
    step "simplify-$b" node "$SIMP" "$W/shell.bin" "$W/PP-$b.idx" "$b" "$($PY -c "print(0.005 * $LEN)")" PP
    cp "$W/simplify-$b.out" "$W/PP-$b.simplify.json"
    read -r err sloppy ms < <($PY -c "import json,sys; s=json.load(open(sys.argv[1])); print(s['errorM'], 'true' if s['sloppy'] else 'false', s['ms'])" "$W/PP-$b.simplify.json")
    step "export-$b" $PY -I "$MESH" export "$CLS" "PP-$b" "$b" "$err" "$sloppy" "$ms" 0.1563
    final=$b
    [ "$(jget "$W/PP-$b.json" ".get('fails', [])" | $PY -c "import sys, ast; print(len(ast.literal_eval(sys.stdin.read())))")" = 0 ] && break
done
cp "$W/PP-$final.holo" "$W/PP.holo"
$PY -c "
import json, sys
r = json.load(open(sys.argv[1])); r['passed'] = len(r['fails']) == 0; r['budget'] = int(sys.argv[2])
open(sys.argv[3], 'w').write(json.dumps(r, separators=(',', ':')))" "$W/PP-$final.json" "$final" "$W/PP.json"
step outline $PY -I "$MESH" outline "$CLS"

num "${CHAIN_KEY:-chain}.lengthM" "$LEN"
num "${CHAIN_KEY:-chain}.budget" "$final"
num "${CHAIN_KEY:-chain}.workdir.bytes" "$(du -sb "$W" | cut -f1)"
num "${CHAIN_KEY:-chain}.holo.bytes" "$(stat -c %s "$W/PP.holo")"
echo "work folder $W:"
ls -l "$W" | sed 's/^/  /'
