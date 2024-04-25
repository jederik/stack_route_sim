#!/bin/bash

data=$(mktemp)
PYTHONPATH="src/main:$PYTHONPATH" time python -m main "$@" \
| jq '[.candidates.shortest.transmissions_per_node, .candidates.shortest.efficiency, .candidates.random.transmissions_per_node, .candidates.random.efficiency]' \
| jq -r 'map(tostring) | join("\t")' \
> "$data"
cat "$data"
gnuplot -p -e "plot \
  '$data' using 1:2 with lines title 'efficiency (shortest)', \
  '$data' using 3:4 with lines title 'efficiency (random)'" \
  || head "$data"