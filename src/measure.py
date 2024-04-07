import random

from src import routing, net, strategy


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


class Experiment:
    def __init__(self, config, emit_sample):
        self.network: net.Network = generate_network(config["network"])
        self.strategy = strategy.SimpleRoutingStrategy()
        self.routers: list[routing.Router] = [
            self.strategy.build_router(adapter)
            for adapter in self.network.adapters
        ]
        self.config = config["measurement"]
        self.emit_sample = emit_sample

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
            "transmissions_per_node": self.network.get_counter({"name": "transmission_count", "success": "true"}) / len(self.network.nodes),
        }
