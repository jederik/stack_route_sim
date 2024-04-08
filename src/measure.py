import random

from src import routing, net, strategy, graphs


def generate_network(config):
    # create nodes
    network = net.Network(
        node_count=config["node_count"]
    )

    # connect nodes
    p = config["density"]
    for n1 in range(len(network.nodes)):
        for n2 in range(len(network.nodes)):
            if p > random.random():
                network.connect(n1, n2)

    return network


def to_graph(network: net.Network) -> list[list[int]]:
    return [
        [
            port.target_node
            for port in node.ports.values()
        ]
        for node in network.nodes
    ]


class MetricsCalculator:
    def __init__(self, network: net.Network, routers: list[routing.Router]):
        self.network = network
        self.routers = routers
        self.graph = to_graph(self.network)

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
            router = self.routers[i]
            for j in range(len(self.network.nodes)):
                if router.has_route(j):
                    shortest_route = router.shortest_route(j)
                    route_lengths += len(shortest_route)
                    node_distances += distances[i][j]
        if route_lengths == 0:
            return 1
        return node_distances / route_lengths


class Experiment:
    def __init__(self, config, emit_sample):
        self.network: net.Network = generate_network(config["network"])
        self.strategy = strategy.SimpleRoutingStrategy(config["strategy"])
        self.routers: list[routing.Router] = [
            self.strategy.build_router(adapter, node_id)
            for node_id, adapter in enumerate(self.network.adapters)
        ]
        self.config = config["measurement"]
        self.emit_sample = emit_sample
        self.metrics_calculator = MetricsCalculator(self.network, self.routers)

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
        for router in self.routers:
            router.tick()

    def scrape(self):
        return {
            "transmissions_per_node": self.metrics_calculator.transmissions_per_node(),
            "routability_rate": self.metrics_calculator.routability_rate(),
            "efficiency": self.metrics_calculator.efficiency(),
        }
