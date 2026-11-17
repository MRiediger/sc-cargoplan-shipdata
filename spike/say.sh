# spike/say.sh - sourced by the spike's bash steps (S12.0). Throwaway measuring code.
#   say <step> <checked> <found> <to do>   three lines in the log and in the job's step summary
#   num <key> <value>                      one number, to $SPIKE_OUT/numbers.tsv (uploaded per job)
#   now / since <t0>                       seconds, for timings
SPIKE_OUT=${SPIKE_OUT:-$PWD/out}
mkdir -p "$SPIKE_OUT"

say() {
    printf '\n=== %s\n  checked: %s\n  found:   %s\n  to do:   %s\n\n' "$1" "$2" "$3" "$4"
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        printf '### %s\n- **checked:** %s\n- **found:** %s\n- **to do:** %s\n\n' "$1" "$2" "$3" "$4" >> "$GITHUB_STEP_SUMMARY"
    fi
}

num() {
    printf '%s\t%s\n' "$1" "$2" >> "$SPIKE_OUT/numbers.tsv"
    echo "  # $1 = $2"
}

now() { date +%s.%N; }
since() { awk -v a="$1" -v b="$(date +%s.%N)" 'BEGIN { printf "%.1f", b - a }'; }
