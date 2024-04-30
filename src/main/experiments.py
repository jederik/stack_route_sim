import random
from typing import Callable, Any

import graphs
import instrumentation
import measurements
import net
import routing
import strategies
from routes import Route, Cost, NodeId
from strategy import RouterFactory


def generate_network(config, rnd: random.Random = random.Random()):
    # create nodes
    network = net.Network(
        node_count=config["node_count"]
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
    def __init__(self, tracker: instrumentation.Tracker):
        self.scraped_measurements: set[str] = set()
        self.tracker = tracker
        self._last_measurement: dict[str, float] = {}

    def calculate_metric(self, metric_name):
        raise Exception("not implemented")

    def reset(self) -> None:
        for measurement in self.scraped_measurements:
            self._reset_measurement(measurement)
        self.scraped_measurements = set()

    def _reset_measurement(self, name):
        self._last_measurement[name] = self.tracker.get_counter_value(name)

    def scrape(self, metrics) -> dict[str, float]:
        result = {
            metric_name: self.calculate_metric(metric_name)
            for metric_name in metrics
        }
        self.reset()
        return result

    def rate(self, sum_metric: str, count_metric: str) -> float:
        sum_delta = self._get_measurement_delta(sum_metric)
        count_delta = self._get_measurement_delta(count_metric)
        if count_delta == 0:
            return 0
        return sum_delta / count_delta

    def _get_measurement_delta(self, name) -> float:
        old_value = float(0)
        if name in self._last_measurement:
            old_value = self._last_measurement[name]
        new_value = self._get_measurement(name)
        return new_value - old_value

    def _get_measurement(self, name):
        self.scraped_measurements.add(name)
        return self.tracker.get_counter_value(name)


class MyMetricsCalculator(MetricsCalculator):
    def __init__(self, network: net.Network, routers: list[routing.Router], tracker: instrumentation.Tracker):
        super().__init__(tracker)
        self.network = network
        self.routers = routers
        self.graph = to_graph(self.network)

    def calculate_metric(self, name) -> float:
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
        return self.network.get_counter({"name": "transmission_count", "success": "true"}) / len(self.network.nodes)

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
        return self.rate(measurements.ROUTE_UPDATE_SECONDS_SUM, measurements.ROUTE_INSERTION_COUNT)

    def distance_update_time(self) -> float:
        return self.rate(measurements.DISTANCE_UPDATE_SECONDS_SUM, measurements.ROUTE_INSERTION_COUNT)


class Candidate:
    def __init__(self, config, router_factory: RouterFactory, tracker: instrumentation.Tracker):
        self.network: net.Network = generate_network(config["network"])
        self.router_factory = router_factory
        self.routers: list[routing.Router] = [
            self.router_factory.create_router(adapter, node_id, tracker)
            for node_id, adapter in enumerate(self.network.adapters)
        ]
        self.metrics_calculator: MetricsCalculator = MyMetricsCalculator(self.network, self.routers, tracker)

    def run_step(self):
        for router in self.routers:
            router.tick()

    def scrape(self, metrics: list[str]) -> dict[str, float]:
        return self.metrics_calculator.scrape(metrics)


def _create_candidate(config, tracker_factory_method: Callable[[], instrumentation.Tracker]):
    return Candidate(
        config=config,
        router_factory=_create_strategy(config["routing"]),
        tracker=tracker_factory_method(),
    )


def _create_strategy(strategy_config):
    strategy: str = strategy_config["strategy"]
    if strategy == "simple":
        constructor = strategies.simple.SimpleRouterFactory
    elif strategy == "optimised":
        constructor = strategies.optimised.OptimisedRouterFactory
    else:
        raise Exception(f"unknown routing strategy: {strategy}")
    return constructor(strategy_config, random.Random())


class Experiment:
    def __init__(
            self,
            config,
            sample_emitter: Callable[[Any], None],
            metrics: list[str],
            tracker_factory_method: Callable[[], instrumentation.Tracker],
    ):
        self.metrics = metrics
        self.emit_sample = sample_emitter
        self.candidates: dict[str, Candidate] = {
            name: _create_candidate(candidate_config, tracker_factory_method)
            for name, candidate_config in config["candidates"].items()
        }
        self.steps: int = config["measurement"]["steps"]
        samples = config["measurement"]["samples"]
        self.scrape_interval: int = self.steps // samples

    def run(self):
        for step in range(self.steps):
            if step % self.scrape_interval == 0:
                sample = self.scrape()
                self.emit_sample(sample)
            self.run_step()
        sample = self.scrape()
        self.emit_sample(sample)

    def run_step(self):
        for _, candidate in self.candidates.items():
            candidate.run_step()

    def scrape(self):
        return {
            "candidates": {
                name: candidate.scrape(self.metrics)
                for name, candidate in self.candidates.items()
            },
        }
