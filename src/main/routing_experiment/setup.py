import random
from typing import Callable

import experimentation
import instrumentation
from . import net, routing, strategies, graphs
from .metering import _create_metrics_calculator

CostGenerator = Callable[[random.Random, int, int], tuple[float, float]]


class RoutingCandidate(experimentation.Candidate):
    def __init__(
            self,
            routers: list[routing.Router],
            measurement_reader: instrumentation.MeasurementReader,
            network: net.Network
    ):
        self.measurement_reader = measurement_reader
        self.network = network
        self.routers = routers

    def run_step(self):
        for router in self.routers:
            router.tick()

    def scrape_metrics(self, metrics: list[str]) -> dict[str, float]:
        measurement_session = self.measurement_reader.session()
        metrics_calculator = _create_metrics_calculator(self.network, self.routers, measurement_session)
        return metrics_calculator.scrape(metrics)


def cost_generator_same(rnd: random.Random, i: int, j: int) -> tuple[float, float]:
    return 1, 1


def cost_generator_uniform(rnd: random.Random, i: int, j: int) -> tuple[float, float]:
    return rnd.random(), rnd.random()


def generate_network(config, rnd: random.Random, tracker: instrumentation.Tracker):
    cost_generator = _create_cost_generator(config)
    graph = _generate_graph(config, rnd, cost_generator)
    return _graph_to_network(graph, tracker)


def _generate_graph(config, rnd, cost_generator: CostGenerator):
    strategy = config["strategy"] if "strategy" in config else "gilbert"
    if strategy == "gilbert":
        graph = graphs.generate_gilbert_graph(
            n=config["node_count"],
            p=config["density"],
            rnd=rnd,
            cost_generator=lambda i, j: cost_generator(rnd, i, j),
        )
    elif strategy == "watts_strogatz":
        graph = graphs.generate_watts_strogatz_graph(
            n=config["node_count"],
            k=config["degree"],
            beta=config["beta"],
            rnd=rnd,
            cost_generator=lambda i, j: cost_generator(rnd, i, j),
        )
    else:
        raise Exception(f"unknown graph generation strategy: {strategy}")
    return graph


def _create_cost_generator(config) -> CostGenerator:
    cost_distribution = config["cost_distribution"] if "cost_distribution" in config else "same"
    cost_generator: Callable[[random.Random, int, int], tuple[float, float]]
    if cost_distribution == "same":
        return cost_generator_same
    elif cost_distribution == "uniform":
        return cost_generator_uniform
    else:
        raise Exception(f"unknown cost distribution: {cost_distribution}")


def _graph_to_network(graph: graphs.CostGraph, tracker: instrumentation.Tracker) -> net.Network:
    network = net.Network(len(graph), tracker)
    for vertex_id, vertex in graph.items():
        for successor_id, forward_cost in vertex.items():
            if successor_id > vertex_id:
                backward_cost = graph[successor_id][vertex_id]
                network.connect(vertex_id, successor_id, forward_cost, backward_cost)
    return network


def _create_router_factory(strategy_config) -> routing.RouterFactory:
    strategy: str = strategy_config["strategy"]
    constructor: Callable[[dict[str], random.Random], routing.RouterFactory]
    if strategy == "simple":
        constructor = strategies.simple.SimpleRouterFactory
    elif strategy == "optimised":
        constructor = strategies.optimised.OptimisedRouterFactory
    elif strategy == "roles":
        constructor = strategies.roles.RolesRouterFactory
    else:
        raise Exception(f"unknown routing strategy: {strategy}")
    return constructor(strategy_config, random.Random())


def create_candidate(config, rnd: random.Random) -> experimentation.Candidate:
    tracker, measurement_reader = instrumentation.setup()
    router_factory = _create_router_factory(config["routing"])
    network = generate_network(config["network"], rnd, tracker)
    routers = [
        router_factory.create_router(adapter, node_id, tracker)
        for node_id, adapter in enumerate(network.adapters)
    ]
    for router, adapter in zip(routers, network.adapters):
        adapter.register_handler(router.handler())
    return RoutingCandidate(
        routers=routers,
        measurement_reader=measurement_reader,
        network=network,
    )
