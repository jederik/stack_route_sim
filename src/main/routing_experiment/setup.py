import random

import experimentation
import instrumentation
from experimentation.metering import MetricName
from . import measurements, graphs, net, routing, strategies
from .routing import Route, RouterFactory
from .net import NodeId, Cost


class RoutingCandidate(experimentation.Candidate):
    def __init__(self, config, router_factory: RouterFactory, tracker: instrumentation.Tracker, rnd: random.Random,
                 measurement_reader: instrumentation.MeasurementReader):
        self.measurement_reader = measurement_reader
        self.network: net.Network = generate_network(config["network"], rnd, tracker)
        self.router_factory = router_factory
        self.routers: list[routing.Router] = [
            self.router_factory.create_router(adapter, node_id, tracker)
            for node_id, adapter in enumerate(self.network.adapters)
        ]

    def run_step(self):
        for router in self.routers:
            router.tick()

    def scrape_metrics(self, metrics: list[str]) -> dict[str, float]:
        metrics_calculator = MetricsCalculator(
            network=self.network,
            routers=self.routers,
            measurement_reader=self.measurement_reader,
        )
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


def to_graph(network: net.Network) -> graphs.CostGraph:
    return {
        node_id: {
            port.target_node: port.cost
            for port in node.ports.values()
        }
        for node_id, node in enumerate(network.nodes)
    }


class MetricsCalculator:
    def __init__(self, network: net.Network, routers: list[routing.Router], measurement_reader: instrumentation.MeasurementReader):
        self.measurement_session = measurement_reader.session()
        self.network = network
        self.routers = routers
        self.graph = to_graph(self.network)

    def _calculate_metric(self, name) -> float:
        if name == "transmissions_per_node":
            return self.transmissions_per_node()
        if name == "routability_rate":
            return self.routability_rate()
        if name == "efficiency":
            return self.efficiency()
        if name == "efficient_routability":
            return self.routability_rate() * self.efficiency()
        if name == "route_insertion_duration":
            return self.route_update_duration()
        if name == "distance_update_duration":
            return self.distance_update_time()
        if name == "propagated_route_length":
            return self.propagated_route_length()
        raise Exception(f"metric not supported: {name}")

    def route_cost(self, source: NodeId, route: Route) -> Cost:
        route_cost = 0
        node = source
        for port_num in route:
            port = self.network.nodes[node].ports[port_num]
            route_cost += port.cost
            node = port.target_node
        return route_cost

    def transmissions_per_node(self):
        return self.measurement_session.get(measurements.TRANSMISSION_COUNT)

    def routability_rate(self):
        routable_pairs = 0
        for i in range(len(self.network.nodes)):
            router = self.routers[i]
            for j in range(len(self.network.nodes)):
                if router.has_route(j):
                    routable_pairs += 1

        reachable_pairs = 0
        reachabilities = graphs.reachabilities(self.graph)
        for i in range(len(self.network.nodes)):
            for j in range(len(self.network.nodes)):
                if reachabilities[i][j]:
                    reachable_pairs += 1

        return routable_pairs / reachable_pairs

    def efficiency(self):
        route_lengths = 0
        node_distances = 0
        distances = graphs.distances(self.graph)
        for i in range(len(self.network.nodes)):
            for j in range(len(self.network.nodes)):
                route = self.routers[i].route(j)
                if route is not None:
                    route_lengths += self.route_cost(i, route)
                    node_distances += distances[i][j]
        if route_lengths == 0:
            return 1
        return node_distances / route_lengths

    def route_update_duration(self) -> float:
        return self.measurement_session.rate(measurements.ROUTE_UPDATE_SECONDS_SUM, measurements.ROUTE_INSERTION_COUNT)

    def distance_update_time(self) -> float:
        return self.measurement_session.rate(measurements.DISTANCE_UPDATE_SECONDS_SUM, measurements.ROUTE_INSERTION_COUNT)

    def propagated_route_length(self) -> float:
        return self.measurement_session.rate(measurements.RECEIVED_ROUTE_LENGTH, measurements.ROUTE_INSERTION_COUNT)

    def scrape(self, metrics: list[MetricName]):
        return {
            metric_name: self._calculate_metric(metric_name)
            for metric_name in metrics
        }


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
        config=config,
        router_factory=_create_strategy(config["routing"]),
        tracker=tracker,
        measurement_reader=measurement_reader,
        rnd=rnd,
    )


def create_experiment(rnd: random.Random, config) -> experimentation.Experiment:
    return experimentation.Experiment(
        candidates={
            name: _create_candidate(
                config=candidate_config,
                rnd=rnd,
            )
            for name, candidate_config in config["candidates"].items()
        }
    )
