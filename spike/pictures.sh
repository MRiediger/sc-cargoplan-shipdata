#!/usr/bin/env bash
# spike/pictures.sh <name> <holo dir> [<baseline dir>] [<expected ids>] - one ShipPictureTests run of the checked-out app
# (app/, built Release) into pics/<name> (S12.0, question 3). Always exits 0; the test's exit code goes to
# pics/<name>.rc and into the summary. Run under Git Bash on windows-latest.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/say.sh"
name=$1; holo=$2; base=${3:-}; expected=${4:-}
out="$PWD/pics/$name"
rm -rf "$out"; mkdir -p "$out"
export CARGOPLAN_PICTURES_OUT; CARGOPLAN_PICTURES_OUT=$(cygpath -w "$out")
# Absolute: the test host's working directory is not this one.
export CARGOPLAN_HOLO_FOLDER; CARGOPLAN_HOLO_FOLDER=$(cygpath -w "$(cd "$holo" && pwd)")
unset CARGOPLAN_PICTURES_BASELINE CARGOPLAN_PICTURES_EXPECTED
[ -n "$base" ] && { export CARGOPLAN_PICTURES_BASELINE; CARGOPLAN_PICTURES_BASELINE=$(cygpath -w "$(cd "$base" && pwd)"); }
[ -n "$expected" ] && export CARGOPLAN_PICTURES_EXPECTED="$expected"

t=$(now)
dotnet test app/tests/CargoPlan.App.Tests -c Release --no-build -p:RunSettingsFilePath= \
    --filter FullyQualifiedName~ShipPictureTests > "$out.log" 2>&1
rc=$?
secs=$(since "$t")
echo "$rc" > "$out.rc"
tail -n 25 "$out.log" | sed 's/^/  /'
pictures=$(wc -l < "$out/pictures.csv" 2>/dev/null || echo 0)
pngs=$(find "$out/png" -name '*.png' 2>/dev/null | wc -l)
bytes=$(du -sb "$out" | cut -f1)
report=$( [ -f "$out/report.txt" ] && head -c 600 "$out/report.txt" | tr '\n' ' ' || echo 'no report.txt' )
num "pictures.$name.rc" "$rc"
num "pictures.$name.s" "$secs"
num "pictures.$name.count" "$pictures"
num "pictures.$name.png" "$pngs"
num "pictures.$name.bytes" "$bytes"
if [ -f "$out/report.txt" ]; then echo "  report.txt (head):"; head -n 40 "$out/report.txt" | sed 's/^/    /'; fi

todo='none'
[ "$rc" != 0 ] && todo="test exit $rc: read pics/$name.log and report.txt (A2 is expected to fail: real v2->v3 changes)"
say "ShipPictureTests run $name" \
    "holo $holo, baseline ${base:-none}, expected ${expected:-none}" \
    "exit $rc in ${secs} s; $pictures pictures, $pngs PNGs, $bytes bytes; report: $report" \
    "$todo"
exit 0
