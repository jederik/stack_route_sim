import random

import experimentation
import instrumentation
from . import net, routing, strategies, graphs
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
    strategy = config["strategy"] if "strategy" in config else "gilbert"
    if strategy == "gilbert":
        graph = graphs.generate_gilbert_graph(
            n=config["node_count"],
            p=config["density"],
            rnd=rnd,
            cost_generator=lambda i, j: (1, 1),
        )
    elif strategy == "watts_strogatz":
        graph = graphs.generate_watts_strogatz_graph(
            n=config["node_count"],
            k=config["degree"],
            beta=config["beta"],
            rnd=rnd,
            cost_generator=lambda i, j: (1, 1),
        )
    else:
        raise Exception(f"unknown network generation strategy: {strategy}")
    return _graph_to_network(graph, tracker)


def _graph_to_network(graph: graphs.CostGraph, tracker: instrumentation.Tracker) -> net.Network:
    network = net.Network(len(graph), tracker)
    for vertex_id, vertex in graph.items():
        for successor_id, forward_cost in vertex.items():
            if successor_id > vertex_id:
                backward_cost = graph[successor_id][vertex_id]
                network.connect(vertex_id, successor_id, forward_cost, backward_cost)
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


def create_candidate(config, rnd: random.Random) -> experimentation.Candidate:
    tracker, measurement_reader = instrumentation.setup()
    return RoutingCandidate(
        router_factory=_create_strategy(config["routing"]),
        tracker=tracker,
        measurement_reader=measurement_reader,
        network=generate_network(config["network"], rnd, tracker),
    )
