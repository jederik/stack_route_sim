import random

import graphs
import net
import routing
import strategies
from routes import Route, Cost, NodeId
from strategy import RoutingStrategy


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
    def __init__(self, network: net.Network, routers: list[routing.Router]):
        self.network = network
        self.routers = routers
        self.graph = to_graph(self.network)

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


class Candidate:
    def __init__(self, config, routing_strategy: RoutingStrategy):
        self.network: net.Network = generate_network(config["network"])
        self.routing_strategy = routing_strategy
        self.routers: list[routing.Router] = [
            self.routing_strategy.build_router(adapter, node_id)
            for node_id, adapter in enumerate(self.network.adapters)
        ]
        self.metrics_calculator = MetricsCalculator(self.network, self.routers)

    def run_step(self):
        for router in self.routers:
            router.tick()

    def scrape(self):
        return {
            "transmissions_per_node": self.metrics_calculator.transmissions_per_node(),
            "routability_rate": self.metrics_calculator.routability_rate(),
            "efficiency": self.metrics_calculator.efficiency(),
        }


def _create_candidate(config):
    return Candidate(
        config=config,
        routing_strategy=_create_strategy(config["routing"]),
    )


def _create_strategy(strategy_config):
    strategy_name: str = strategy_config["name"]
    if strategy_name == "simple":
        constructor = strategies.simple.SimpleRoutingStrategy
    elif strategy_name == "optimised":
        constructor = strategies.optimised.OptimisedRoutingStrategy
    else:
        raise Exception(f"unknown routing strategy: {strategy_name}")
    strategy = constructor(strategy_config, random.Random())
    return strategy


class Experiment:
    def __init__(self, config, sample_emitter):
        self.config = config["measurement"]
        self.emit_sample = sample_emitter
        self.candidates: dict[str, Candidate] = {
            name: _create_candidate(candidate_config)
            for name, candidate_config in config["candidates"].items()
        }

    def run(self):
        steps = self.config["steps"]
        samples = self.config["samples"]
        scrape_interval = steps // samples
        for step in range(steps):
            if step % scrape_interval == 0:
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
                name: candidate.scrape()
                for name, candidate in self.candidates.items()
            },
        }
