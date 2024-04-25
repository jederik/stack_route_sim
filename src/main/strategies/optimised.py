import bisect
import math
import random
import sys
from typing import Optional, TypeVar

import net
from routes import NodeId, Route, PortNumber, Cost
from routing import Router
from strategy import RoutingStrategy


class PropagationMessage:
    def __init__(self, target: NodeId, route: Route, cost: Cost):
        self.cost = cost
        self.route = route
        self.target = target


def is_real_prefix(short: Route, long: Route) -> bool:
    return len(short) != len(long) and short == long[:len(short)]


class PricedRoute:
    def __init__(self, path: Route, cost: Cost):
        self.path = path
        self.cost = cost


class _Edge:
    def __init__(self):
        self.priced_routes: list[PricedRoute] = []

    def __repr__(self):
        return str({"routes": [pr.path for pr in self.priced_routes]})

    def insert_path(self, route: Route, cost: Cost):
        bisect.insort(
            self.priced_routes,
            PricedRoute(route, cost),
            key=lambda pr: pr.cost,
        )

    def update_paths(self, priced_routes: list[PricedRoute]):
        self.priced_routes = priced_routes

    def cost(self) -> Cost:
        if len(self.priced_routes) == 0:
            return math.inf
        return self.priced_routes[0].cost


class _Node:
    def __init__(self, distance: Cost = math.inf, predecessor: Optional[NodeId] = None):
        self.distance: Cost = distance
        self.predecessor: Optional[NodeId] = predecessor
        self.edges: dict[NodeId, _Edge] = {}

    def __repr__(self):
        return str({"edges": self.edges})

    def get_edge(self, target):
        if target not in self.edges:
            self.edges[target] = _Edge()
        return self.edges[target]


T = TypeVar('T')


def _pick_random(items: list[T], rnd: random.Random) -> T:
    return items[int(rnd.random() * len(items))]


class RouteStore:
    def __init__(self, node_id: NodeId, rnd: random.Random = random.Random()):
        self.rnd = rnd
        self.node_id = node_id
        self.nodes: dict[NodeId, _Node] = {
            node_id: _Node(
                distance=0,
                predecessor=None,
            )
        }

    def shortest_route(self, target: NodeId) -> Optional[PricedRoute]:
        if target == self.node_id:
            return PricedRoute([], 0)
        if target not in self.nodes:
            return None
        pred = self.nodes[target].predecessor
        if pred not in self.nodes:
            raise Exception(f"node {self.node_id}: {pred} is best predecessor of {target} but has no outgoing edges")
        if target not in self.nodes[pred].edges:
            raise Exception(f"node {self.node_id}: {pred} is best predecessor of {target} but has no edge to it")
        pred_route = self.shortest_route(pred)
        if pred_route is None:
            return None
        last_mile = self.nodes[pred].edges[target].priced_routes[0]
        return PricedRoute(
            path=pred_route.path + last_mile.path,
            cost=pred_route.cost + last_mile.cost
        )

    def has_route(self, target: NodeId) -> bool:
        return target in self.nodes

    def _store_route(self, source: NodeId, target: NodeId, route: Route, cost: Cost) -> list[NodeId]:
        if target == source:
            return []
        if len(route) == 0:
            raise Exception(f"empty route. self: {self.node_id}, target: {target}")

        if len(self.nodes) != 0:

            # see if exact route is already present
            for successor, edge in self.nodes[source].edges.items():
                for priced_route in edge.priced_routes:
                    if priced_route.path == route:
                        # TODO potentially update cost
                        return []

            # see if target lies on any existing edge
            distance_modified_nodes: list[NodeId] = []
            successors = list(self.nodes[source].edges.keys())
            for successor in successors:
                edge = self.nodes[source].edges[successor]
                prefixed_edge_routes = [
                    edge_route for edge_route in edge.priced_routes if is_real_prefix(route, edge_route.path)
                ]
                non_prefixed_edge_routes = [
                    edge_route for edge_route in edge.priced_routes if not is_real_prefix(route, edge_route.path)
                ]
                if len(prefixed_edge_routes) != 0:

                    if target not in self.nodes:
                        self.nodes[target] = _Node()

                    # insert path between source and target
                    if target not in self.nodes[source].edges:
                        self.nodes[source].edges[target] = _Edge()
                    self.nodes[source].edges[target].insert_path(route, cost)

                    # add paths between target and successor
                    for prefixed_edge_route in prefixed_edge_routes:
                        remaining_route = prefixed_edge_route.path[len(route):]
                        if len(remaining_route) == 0:
                            raise Exception("empty remainder")
                        remaining_cost = prefixed_edge_route.cost - cost
                        if successor not in self.nodes[target].edges:
                            self.nodes[target].edges[successor] = _Edge()
                        self.nodes[target].edges[successor].insert_path(remaining_route, remaining_cost)

                    # remove replaced paths
                    self.nodes[source].edges[successor].update_paths(non_prefixed_edge_routes)
                    if len(self.nodes[source].edges[successor].priced_routes) == 0:
                        del self.nodes[source].edges[successor]

                    distance_modified_nodes.append(successor)
            if distance_modified_nodes:
                return [target]

            # find known node on the route
            for successor, edge in self.nodes[source].edges.items():
                for edge_route in edge.priced_routes:
                    if len(edge_route.path) == 0:
                        raise Exception("empty segment")
                    if is_real_prefix(edge_route.path, route):
                        distance_modified_nodes = self._store_route(
                            source=successor,
                            target=target,
                            route=route[len(edge_route.path):],
                            cost=cost - edge_route.cost,
                        )
                        return [successor] + distance_modified_nodes

        if target not in self.nodes[source].edges:
            if target not in self.nodes:
                self.nodes[target] = _Node()
            self.nodes[source].edges[target] = _Edge()
        self.nodes[source].edges[target].insert_path(route, cost)
        return [target]

    def insert(self, target: NodeId, route: Route, cost: Cost):
        distance_modified_nodes = self._store_route(self.node_id, target, route, cost)
        self._update_distances(distance_modified_nodes)

    def _get_node(self, node_id: NodeId):
        if node_id not in self.nodes:
            self.nodes[node_id] = _Node()
        return self.nodes[node_id]

    def _update_distances(self, distance_modified_nodes: list[NodeId]):
        # Dijkstra:
        for i in self.nodes.keys():
            self.nodes[i].predecessor = None
            self.nodes[i].distance = math.inf
        self.nodes[self.node_id].distance = 0
        queue: list[NodeId] = list(self.nodes.keys())
        explored: set[NodeId] = set()
        while len(queue) != 0:
            u = min(queue, key=lambda i: self.nodes[i].distance)
            queue.remove(u)
            explored.add(u)
            for v in self.nodes[u].edges.keys():
                if v not in explored:
                    alt = self.nodes[u].distance + self.nodes[u].edges[v].cost()
                    if alt < self.nodes[v].distance:
                        self.nodes[v].predecessor = u
                        self.nodes[v].distance = alt

    def _log(self, msg):
        print(f"{self.node_id}: {str(msg)}", file=sys.stderr)

    def _pick_random(self, items: list[T]) -> T:
        return _pick_random(items, self.rnd)


class PropagationStrategy:
    def pick(self, router: 'OptimisedRouter'):
        raise Exception("not implemented")


class OptimisedRouter(Router, net.Adapter.Handler):
    def __init__(
            self,
            adapter: net.Adapter,
            node_id: NodeId,
            propagation_strategy: PropagationStrategy,
            rnd: random.Random
    ):
        self.adapter = adapter
        self.store = RouteStore(node_id, rnd)
        self._propagation_strategy = propagation_strategy
        adapter.register_handler(self)

    def route(self, target: NodeId) -> Optional[Route]:
        priced_route = self.store.shortest_route(target)
        if not priced_route:
            return None
        return priced_route.path

    def has_route(self, target: NodeId) -> bool:
        return self.store.has_route(target)

    def handle(self, port_num: PortNumber, message) -> None:
        message: PropagationMessage = message
        self.store.insert(
            target=message.target,
            route=[port_num] + message.route,
            cost=message.cost + self.adapter.port_cost(port_num),
        )

    def tick(self) -> None:
        port, target, route, cost = self._propagation_strategy.pick(self)
        self._send_propagation_message(port, target, route, cost)

    def _send_propagation_message(self, port_num: PortNumber, target: NodeId, route: Route, cost: Cost):
        message = PropagationMessage(target, route, cost)
        self.adapter.send(port_num, message)


class RandomRoutePropagationStrategy(PropagationStrategy):
    def __init__(self, rnd: random.Random):
        self.rnd = rnd

    def pick(self, router: OptimisedRouter) -> tuple[PortNumber, NodeId, Route, Cost]:
        ports = router.adapter.ports()
        if len(ports) == 0:
            raise Exception("no ports available")
        port = _pick_random(ports, self.rnd)
        target, route, cost = self._get_random_route(router.store)
        return port, target, route, cost

    def _get_random_route(self, store: RouteStore, source: NodeId = None) -> tuple[NodeId, Route, Cost]:
        if source is None:
            source = store.node_id
        if len(store.nodes[source].edges) == 0:
            return source, [], 0
        if self.rnd.random() < .9:
            return source, [], 0
        successor = _pick_random(list(store.nodes[source].edges.keys()), self.rnd)
        target, route_tail, tail_cost = self._get_random_route(store, successor)
        edged_route = _pick_random(store.nodes[source].edges[successor].priced_routes, self.rnd)
        return target, edged_route.path + route_tail, edged_route.cost + tail_cost


class ShortestRoutePropagationStrategy(PropagationStrategy):
    def __init__(self, rnd: random.Random):
        self.rnd = rnd

    def pick(self, router: OptimisedRouter) -> tuple[PortNumber, NodeId, Route, Cost]:
        port = _pick_random(router.adapter.ports(), self.rnd)
        target = _pick_random(list(router.store.nodes.keys()), self.rnd)
        priced_route = router.store.shortest_route(target)
        return port, target, priced_route.path, priced_route.cost


def _create_propagation_strategy(propagation_config, rnd: random.Random) -> PropagationStrategy:
    name = propagation_config["name"]
    if name == "random_route":
        return RandomRoutePropagationStrategy(rnd)
    if name == "shortest_route":
        return ShortestRoutePropagationStrategy(rnd)
    raise Exception(f"unknown propagation strategy: {name}")


class OptimisedRoutingStrategy(RoutingStrategy):
    def __init__(self, routing_config, rnd: random.Random):
        self.rnd = rnd
        self.propagation_strategy = _create_propagation_strategy(routing_config["propagation"], rnd)

    def build_router(self, adapter: net.Adapter, node_id: NodeId) -> Router:
        return OptimisedRouter(
            adapter,
            node_id,
            propagation_strategy=self.propagation_strategy,
            rnd=self.rnd,
        )
