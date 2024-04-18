import random

import net
from routes import NodeId, Route, PortNumber
from routing import Router
from strategy import RoutingStrategy


class _PathFinder:
    def __init__(self, best_pred: NodeId):
        self.paths: dict[NodeId, list[Route]] = {}
        self.best_pred = best_pred


class PropagationMessage:
    def __init__(self, target: NodeId, route: Route):
        self.route = route
        self.target = target


def is_prefix(short: Route, long: Route) -> bool:
    return short == long[:len(short)]


class _Edge:
    def __init__(self):
        self.routes: list[Route] = []


class OptimisedRouter(Router, net.Adapter.Handler):
    def __init__(self, adapter: net.Adapter, node_id: NodeId):
        self.edges: dict[NodeId, dict[NodeId, _Edge]] = {
            node_id: {
                node_id: _Edge()
            }
        }
        self.adapter = adapter
        self.node_id = node_id
        self.path_finders: dict[NodeId, _PathFinder] = {
            node_id: _PathFinder(node_id)
        }
        self.path_finders[node_id].paths[node_id] = [[]]
        adapter.register_handler(self)

    def shortest_route(self, target: NodeId) -> Route:
        if target == self.node_id:
            return []
        if target not in self.path_finders:
            raise Exception(f"no route found to {target}")
        path_finder = self.path_finders[target]
        pred = path_finder.best_pred
        path = path_finder.paths[pred][0]
        return self.shortest_route(pred) + path

    def has_route(self, target: NodeId) -> bool:
        return target in self.path_finders

    def handle(self, port_num: PortNumber, message):
        message: PropagationMessage = message
        self._store_route(
            source=self.node_id,
            target=message.target,
            route=[port_num] + message.route,
        )

    def tick(self):
        port, target, route = self._pick_propagation()
        self._send_propagation_message(port, target, route)

    def _send_propagation_message(self, port_num: PortNumber, target: NodeId, route: Route):
        message = PropagationMessage(target, route)
        self.adapter.send(port_num, message)

    def _store_route(self, source: NodeId, target: NodeId, route: Route):
        if target == source:
            return
        if source not in self.edges:
            self.edges[source] = {}
        source_outgoing_edges = self.edges[source]

        # see if target lies on any existing edge
        successors = list(source_outgoing_edges.keys())
        for successor in successors:
            edge = source_outgoing_edges[successor]
            prefixed_edge_routes = [path for path in edge.routes if is_prefix(route, path)]
            non_prefixed_edge_routes = [path for path in edge.routes if not is_prefix(route, path)]
            if len(prefixed_edge_routes) != 0:
                self.edges[source][target] = _Edge()
                self.edges[source][target].routes = [
                    edge_route[len(route):]
                    for edge_route in prefixed_edge_routes
                ]
                edge.routes = non_prefixed_edge_routes
            if len(non_prefixed_edge_routes) == 0:
                del source_outgoing_edges[successor]

        # find known nodes on the route
        for successor, edge in source_outgoing_edges.items():
            for edge_route in edge.routes:
                if is_prefix(edge_route, route):
                    return self._store_route(
                        source=successor,
                        target=target,
                        route=route[len(edge_route):],
                    )

        if source not in self.edges:
            self.edges[source] = {}
        if target not in self.edges[source]:
            self.edges[source][target] = _Edge()
        self.edges[source][target].routes.append(route)

        if target not in self.path_finders:
            self.path_finders[target] = _PathFinder(self.node_id)
        path_finder = self.path_finders[target]
        if self.node_id not in path_finder.paths:
            path_finder.paths[self.node_id] = [route]

    def _pick_propagation(self) -> (PortNumber, NodeId, Route):
        ports = self.adapter.ports()
        port = ports[int(random.random() * len(ports))]
        node_ids = list(self.path_finders.keys())
        target = node_ids[int(random.random() * len(node_ids))]
        route = self.shortest_route(target)
        return port, target, route


class OptimisedRoutingStrategy(RoutingStrategy):
    def __init__(self, config):
        pass

    def build_router(self, adapter: net.Adapter, node_id: NodeId) -> Router:
        return OptimisedRouter(adapter, node_id)
