#!/usr/bin/env bash
# spike/swap.sh - gate-b (S12.0, E3): put the chain's built files into the app checkout and rebuild, since ShipPictureTests
# reads ships/ and outlines/ from bin. Expects built/ (artifact of the chain job), app/ (sc-cargoplan at the tag, built
# once) and holo-v3/. Writes the ship id to $SPIKE_OUT/swap.id (empty: nothing to swap). Git Bash on windows-latest or
# locally.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/say.sh"
PY=${PY:-python}
: > "$SPIKE_OUT/swap.id"
if [ ! -f built/ship.txt ] || [ ! -f "built/$(cut -d' ' -f2 built/ship.txt).holo" ]; then
    say "Swap built files" "artifact built from the chain job" "missing: the chain did not build" "run B skipped; B0 against A1 still gives VM-to-VM"
    exit 0
fi
read -r ID SLUG CLS < built/ship.txt
same() { $PY -c "import sys; n = lambda p: open(p, 'rb').read().replace(b'\r\n', b'\n'); print('same' if n(sys.argv[1]) == n(sys.argv[2]) else 'different')" "$1" "$2"; }
s1=$(same "built/$ID.json" "app/ships/$ID.json")
s2=$(same built/ship-outlines.json app/outlines/ship-outlines.json)
s3=$(same "built/$SLUG.holo" "holo-v3/$SLUG.holo")
t=$(now)
cp "built/$ID.json" "app/ships/$ID.json"
cp built/ship-outlines.json app/outlines/ship-outlines.json
cp "built/$SLUG.holo" "holo-v3/$SLUG.holo"
if ! dotnet build app/tests/CargoPlan.App.Tests -c Release > "$SPIKE_OUT/rebuild.log" 2>&1; then
    tail -n 60 "$SPIKE_OUT/rebuild.log"
    say "Swap built files into the app checkout (E3)" "rebuild after the swap" "dotnet build failed" "see the log"
    exit 1
fi
s=$(since "$t"); num gate.swap-rebuild.s "$s"
# bin must hold the swapped file, or run B would measure the old data
binship=$(find app/tests/CargoPlan.App.Tests/bin/Release -path "*/ships/$ID.json" | head -n 1)
s4=$(same "built/$ID.json" "$binship")
echo "$ID" > "$SPIKE_OUT/swap.id"
say "Swap built files into the app checkout (E3)" \
    "ships/$ID.json, outlines/ship-outlines.json, $SLUG.holo from the ubuntu chain; rebuild, since ships/ and outlines/ are copied to bin" \
    "against $APP_TAG/holo-v3: ship json $s1, outlines $s2, holo $s3; bin copy of $ID.json after the rebuild: $s4 to the built one; swap + rebuild $s s" \
    "$([ "$s4" = same ] && echo 'none; E3 decides whether the test gets a data-folder override instead' || echo 'the rebuild did not copy the ship file into bin: run B would measure old data')"
