#!/bin/bash

data=$(mktemp)
python -m src.main \
| jq '[.candidates.random.transmissions_per_node, .candidates.random.efficiency, .candidates.shortest.transmissions_per_node, .candidates.shortest.efficiency]' \
| jq -r 'map(tostring) | join("\t")' \
> "$data"
gnuplot -p -e "plot \
  '$data' using 1:2 with lines title 'efficiency (random)', \
  '$data' using 3:4 with lines title 'efficiency (shortest)'" \
  || head "$data"