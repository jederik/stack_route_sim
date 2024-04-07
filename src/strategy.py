import random

from src import net, routing


class SimpleRouter(routing.Router, net.Adapter.Handler):
    def __init__(self, adapter: net.Adapter):
        self.adapter = adapter
        adapter.register_handler(self)

    def tick(self):
        ports = self.adapter.ports()
        port_num = ports[int(random.random() * len(ports))]
        self.adapter.send(port_num)

    def handle(self):
        pass


class RoutingStrategy:
    def build_router(self, adapter: net.Adapter):
        raise Exception("not implemented")


class SimpleRoutingStrategy(RoutingStrategy):
    def build_router(self, adapter: net.Adapter):
        return SimpleRouter(adapter)
