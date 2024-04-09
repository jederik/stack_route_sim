import random
from typing import Optional, Callable

from src import net, routing


class RoutePropagationMessage:
    def __init__(self, node_id: int, route: list[int]):
        self.route = route
        self.node_id = node_id


_NodeId = int
_PortNumber = int
_Route = list[_PortNumber]
_NodeRoutes = list[_Route]
_RouteStore = dict[_NodeId, _NodeRoutes]


def _shortest_route(routes, target):
    if target not in routes:
        return None
    target_routes = routes[target]
    if len(target_routes) == 0:
        return None
    shortest_route = min(target_routes, key=lambda route: len(route))
    return shortest_route


class SimpleRouter(routing.Router, net.Adapter.Handler):
    def __init__(
            self,
            adapter: net.Adapter,
            node_id: _NodeId,
            propagation_route_picker: Callable[[_RouteStore], _Route],
    ):
        self.pick_propagation_route = propagation_route_picker
        self.routes: _RouteStore = {
            node_id: [[]]
        }
        self.adapter = adapter
        adapter.register_handler(self)

    def has_route(self, target: _NodeId) -> bool:
        return target in self.routes and len(self.routes[target]) != 0

    def tick(self):
        self.propagate_route()

    def propagate_route(self):
        ports = self.adapter.ports()
        port_num = ports[int(random.random() * len(ports))]
        target_id, route = self.pick_propagation_route(self.routes)
        prop_msg = RoutePropagationMessage(target_id, route)
        self.adapter.send(port_num, prop_msg)

    def handle(self, port_num: _PortNumber, message):
        prop: RoutePropagationMessage = message
        node_routes = self._get_node_routes(prop.node_id)
        route = prop.route
        route.append(port_num)
        node_routes.append(route)

    def shortest_route(self, target: _NodeId) -> Optional[_Route]:
        return _shortest_route(self.routes, target)

    def _get_node_routes(self, node_id: _NodeId):
        if node_id in self.routes:
            return self.routes[node_id]
        else:
            self.routes[node_id] = []
            return self.routes[node_id]


def _pick_propagation_route_random(routes: _RouteStore) -> (_NodeId, _Route):
    nodes = list(routes.keys())
    node_id = nodes[int(random.random() * len(nodes))]
    node_routes = routes[node_id]
    return node_id, node_routes[int(random.random() * len(node_routes))]


def _pick_propagation_route_shortest(routes: _RouteStore) -> (_NodeId, _Route):
    nodes = list(routes.keys())
    node_id = nodes[int(random.random() * len(nodes))]
    return node_id, _shortest_route(routes, node_id)


class RoutingStrategy:
    def build_router(self, adapter: net.Adapter, node_id: _NodeId):
        raise Exception("not implemented")


class SimpleRoutingStrategy(RoutingStrategy):
    def __init__(self, config):
        self.config = config

    def build_router(self, adapter: net.Adapter, node_id: _NodeId):
        return SimpleRouter(
            adapter=adapter,
            node_id=node_id,
            propagation_route_picker=_pick_propagation_route_shortest if self.config[
                "propagate_shortest_route"] else _pick_propagation_route_random,
        )
