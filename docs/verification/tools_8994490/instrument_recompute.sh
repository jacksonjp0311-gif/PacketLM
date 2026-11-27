#!/bin/sh
# Verifier: run the pinned learning-amortization instrument (70297af, 5000 resamples) on the G57b
# CSVs (registered, or a re-run's), for every registered primary and secondary contrast.
# Usage: instrument_recompute.sh DIR_WITH_CSVs
D=${1:-docs/evidence/g57b}
I=/workspace/vendor/learning-amortization
echo "instrument head $(git -C $I rev-parse --short HEAD) dirty=[$(git -C $I status --porcelain)]"
for c in comp unrel; do
  n=$( [ $c = comp ] && echo 36 || echo 24 )
  for pair in "Cj+maint Bj" "Cj+maint Ci+maint" "Ci+maint Bi" "Bj Bi" "Pj+maint Pi+maint" "Cj+maint Pj+maint" "Cj Bj" "Fj+maint Fi+maint" "Cj+maint Fj+maint"; do
    set -- $pair
    [ $c = unrel ] && case $1$2 in *F*) continue;; esac
    out=$(PYTHONPATH=$I python3 -m amortization $D/${c}_total.csv --cont "$1" --base "$2" --n $n --bootstrap 5000 2>&1 | head -1)
    echo "$c | $1 || $2 | $out"
  done
done
