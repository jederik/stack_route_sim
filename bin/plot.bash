#!/bin/bash

data=$(mktemp)
PYTHONPATH="src/main:$PYTHONPATH" python -m main "$@" \
| jq '[.candidates.random.transmissions_per_node, .candidates.random.efficiency, .candidates.shortest.transmissions_per_node, .candidates.shortest.efficiency]' \
| jq -r 'map(tostring) | join("\t")' \
> "$data"
head "$data"
gnuplot -p -e "plot \
  '$data' using 1:2 with lines title 'efficiency (normal)', \
  '$data' using 3:4 with lines title 'efficiency (optimised)'" \
  || head "$data"