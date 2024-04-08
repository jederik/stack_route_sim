import random
from typing import Optional

from src import net, routing


class RoutePropagationMessage:
    def __init__(self, node_id: int, route: list[int]):
        self.route = route
        self.node_id = node_id


class SimpleRouter(routing.Router, net.Adapter.Handler):
    def __init__(self, adapter: net.Adapter, node_id: int):
        self.routes: dict[int, list[list[int]]] = {
            node_id: [[]]
        }
        self.adapter = adapter
        adapter.register_handler(self)

    def has_route(self, target) -> bool:
        return target in self.routes and len(self.routes[target]) != 0

    def tick(self):
        ports = self.adapter.ports()
        port_num = ports[int(random.random() * len(ports))]
        target_id, route = self._pick_random_route()
        prop_msg = RoutePropagationMessage(target_id, route)
        self.adapter.send(port_num, prop_msg)

    def handle(self, port_num: int, message):
        prop: RoutePropagationMessage = message
        node_routes = self._get_node_routes(prop.node_id)
        route = prop.route
        route.append(port_num)
        node_routes.append(route)

    def shortest_route(self, target) -> Optional[list[int]]:
        if target not in self.routes:
            return None
        target_routes = self.routes[target]
        if len(target_routes) == 0:
            return None
        shortest_route = min(target_routes, key=lambda route: len(route))
        return shortest_route

    def _get_node_routes(self, node_id):
        if node_id in self.routes:
            return self.routes[node_id]
        else:
            self.routes[node_id] = []
            return self.routes[node_id]

    def _pick_random_route(self) -> (int, list[int]):
        nodes = list(self.routes.keys())
        node_id = nodes[int(random.random() * len(nodes))]
        node_routes = self.routes[node_id]
        return node_id, node_routes[int(random.random() * len(node_routes))]


class RoutingStrategy:
    def build_router(self, adapter: net.Adapter, node_id: int):
        raise Exception("not implemented")


class SimpleRoutingStrategy(RoutingStrategy):
    def build_router(self, adapter: net.Adapter, node_id: int):
        return SimpleRouter(adapter, node_id)
