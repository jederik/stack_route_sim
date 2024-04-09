#!/bin/bash

data=$(mktemp)
python -m src.main \
| jq '[.transmissions_per_node, .efficiency, .routability_rate]' \
| jq -r 'map(tostring) | join("\t")' \
> "$data"
gnuplot -p -e "plot \
  '$data' using 1:2 with lines title 'efficiency', \
  '$data' using 1:3 with lines title 'routability rate'"