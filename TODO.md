## Tasks

- introduce routing strategy with
  - forwarding layer
  - registerable actors, each actor being able to
    - handle incoming messages
    - send message
    - tick
- implement actors
  - self-promotion
  - route storage
  - foreign route propagation


## Goals

- investigate different node types:
  - micro nodes (only forwarding)
  - service nodes (propagating own ID)
  - client nodes (collecting foreign routes)
  - landmark nodes (propagating and collecting foreign routes)
- investigate heterogeneous demand for certain services
- use same network for all candidates
- run multiple rounds for each candidate
- write README.md
- split into experimentation framework and routing experiment
