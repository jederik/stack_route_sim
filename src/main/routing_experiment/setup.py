import random

import experimentation
import instrumentation
from . import net, routing, strategies
from .metering import _create_metrics_calculator
from .routing import RouterFactory


class RoutingCandidate(experimentation.Candidate):
    def __init__(
            self,
            router_factory: RouterFactory,
            tracker: instrumentation.Tracker,
            measurement_reader: instrumentation.MeasurementReader,
            network: net.Network
    ):
        self.measurement_reader = measurement_reader
        self.network = network
        self.router_factory = router_factory
        self.routers: list[routing.Router] = [
            self.router_factory.create_router(adapter, node_id, tracker)
            for node_id, adapter in enumerate(self.network.adapters)
        ]

    def run_step(self):
        for router in self.routers:
            router.tick()

    def scrape_metrics(self, metrics: list[str]) -> dict[str, float]:
        metrics_calculator = _create_metrics_calculator(self.network, self.routers, self.measurement_reader)
        return metrics_calculator.scrape(metrics)


def generate_network(config, rnd: random.Random, tracker: instrumentation.Tracker):
    # create nodes
    network = net.Network(
        node_count=config["node_count"],
        tracker=tracker,
    )

    # connect nodes
    p = config["density"]
    for n1 in range(len(network.nodes)):
        for n2 in range(len(network.nodes)):
            if p > rnd.random():
                network.connect(n1, n2, 1, 1)

    return network


def _create_strategy(strategy_config):
    strategy: str = strategy_config["strategy"]
    if strategy == "simple":
        constructor = strategies.simple.SimpleRouterFactory
    elif strategy == "optimised":
        constructor = strategies.optimised.OptimisedRouterFactory
    else:
        raise Exception(f"unknown routing strategy: {strategy}")
    return constructor(strategy_config, random.Random())


def _create_candidate(config, rnd: random.Random) -> experimentation.Candidate:
    tracker, measurement_reader = instrumentation.setup()
    return RoutingCandidate(
        router_factory=_create_strategy(config["routing"]),
        tracker=tracker,
        measurement_reader=measurement_reader,
        network=generate_network(config["network"], rnd, tracker),
    )


def create_experiment(rnd: random.Random, candidate_configs) -> experimentation.Experiment:
    return experimentation.Experiment(
        candidates={
            name: _create_candidate(
                config=candidate_config,
                rnd=rnd,
            )
            for name, candidate_config in candidate_configs.items()
        }
    )
