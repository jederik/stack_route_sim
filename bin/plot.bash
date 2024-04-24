#!/bin/bash

data=$(mktemp)
PYTHONPATH="src/main:$PYTHONPATH" python -m main "$@" \
| jq '[.candidates.shortest.transmissions_per_node, .candidates.shortest.efficiency, .candidates.optimised.transmissions_per_node, .candidates.optimised.efficiency]' \
| jq -r 'map(tostring) | join("\t")' \
> "$data"
gnuplot -p -e "plot \
  '$data' using 1:2 with lines title 'efficiency (normal)', \
  '$data' using 3:4 with lines title 'efficiency (optimised)'" \
  || head "$data"