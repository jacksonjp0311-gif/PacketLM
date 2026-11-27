#!/bin/sh
# Verifier repro (3e2783c): a --lean save writes dict keys sorted, the engine iterates dicts in
# insertion order, so a later reply lists events in a different order. Run from the repo root.
for L in "" "--lean"; do
  f=/tmp/lean_order$L.json; rm -f $f $f.bak
  python3 -m packetlm.engine $f --answers $L 'fact a r b' 'fact c r d' 'example zz: a -> b' 'example zz: c -> d' 'example aa: a -> b' 'example aa: c -> d' >/dev/null
  echo "${L:-non-lean}: $(python3 -m packetlm.engine $f --answers $L 'correct a r q')"
done
