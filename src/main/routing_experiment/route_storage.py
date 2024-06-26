import bisect
import copy
import math
from typing import Optional

import instrumentation
from . import measurements
from .net import Cost, NodeId
from .routing import Route
import logging

_CostSummary = dict[NodeId, dict[NodeId, Cost]]


def is_real_prefix(short: Route, long: Route) -> bool:
    return len(short) < len(long) and is_prefix(short, long)


def is_prefix(short: Route, long: Route) -> bool:
    return short == long[:len(short)]


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
        bisect.insort_left(
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


class RouteStore:
    def __init__(
            self,
            source: NodeId,
            tracker: Optional[instrumentation.Tracker],
            logger: logging.Logger,
            eliminate_cycles: bool,
            eliminate_cycles_eagerly: bool,
    ):
        self.eliminate_cycles_eagerly = eliminate_cycles_eagerly
        self.eliminate_cycles = eliminate_cycles
        self.logger = logger
        self.measurements = _Measurements(tracker)
        self.source = source
        self.nodes: dict[NodeId, _Node] = {
            source: _Node(
                distance=0,
                predecessor=None,
            )
        }

    def shortest_route(self, target: NodeId) -> Optional[PricedRoute]:
        if target not in self.nodes:
            return None
        return copy.deepcopy(self._shortest_route_rec(target))

    def _shortest_route_rec(self, target: NodeId) -> PricedRoute:
        if target == self.source:
            return PricedRoute([], 0)
        pred = self.nodes[target].predecessor
        pred_route = self.shortest_route(pred)
        last_mile = self.nodes[pred].edges[target].priced_routes[0]
        return PricedRoute(
            path=pred_route.path + last_mile.path,
            cost=pred_route.cost + last_mile.cost,
        )

    def has_route(self, target: NodeId) -> bool:
        return target in self.nodes

    def _store_route(self, source: NodeId, target: NodeId, route: Route, cost: Cost,
                     modified_edges: list[tuple[NodeId, NodeId]]) -> None:
        if self.eliminate_cycles:
            if self.eliminate_cycles_eagerly:
                if target == source:
                    return
            else:
                if target == self.source:
                    return
        if target == source:
            return
        if len(route) == 0:
            if target != source:
                raise Exception("route target contradiction")
            # TODO back propagate new costs

        # find known node on the route
        for successor, edge in self.nodes[source].edges.items():
            for edge_route in edge.priced_routes:
                if is_prefix(edge_route.path, route):
                    self._store_route(
                        source=successor,
                        target=target,
                        route=route[len(edge_route.path):],
                        cost=cost - edge_route.cost,
                        modified_edges=modified_edges,
                    )
                    return

        # insert path between source and target
        if target not in self.nodes[source].edges:
            if target not in self.nodes:
                self.nodes[target] = _Node()
            self.nodes[source].edges[target] = _Edge()
        self.nodes[source].edges[target].insert_path(route, cost)
        modified_edges.append((source, target))

        # redirect prefixed routes via target
        successors = list(self.nodes[source].edges.keys())
        for successor in successors:
            self._redirect_prefixed_segments(source, successor, target, route, cost, modified_edges)

    def _redirect_prefixed_segments(
            self,
            source: NodeId,
            successor: NodeId,
            target: NodeId,
            route: Route,
            cost: Cost,
            modified_edges: list[tuple[NodeId, NodeId]]
    ):
        non_prefixed_edge_routes, prefixed_edge_routes = self._find_prefixed_segments(route, source, successor)

        if not any(prefixed_edge_routes):
            return False

        if target not in self.nodes:
            self.nodes[target] = _Node()

        # remove prefixed segments between source and successor
        self.nodes[source].edges[successor].update_paths(non_prefixed_edge_routes)
        if len(self.nodes[source].edges[successor].priced_routes) == 0:
            del self.nodes[source].edges[successor]
        modified_edges.append((source, successor))

        # add segments between target and successor
        for prefixed_edge_route in prefixed_edge_routes:
            remaining_route = prefixed_edge_route.path[len(route):]
            if len(remaining_route) == 0:
                raise Exception("empty remainder")
            remaining_cost = prefixed_edge_route.cost - cost
            if successor not in self.nodes[target].edges:
                self.nodes[target].edges[successor] = _Edge()
            self.nodes[target].edges[successor].insert_path(remaining_route, remaining_cost)
        modified_edges.append((target, successor))

        return True

    def _find_prefixed_segments(self, route, source, successor):
        edge = self.nodes[source].edges[successor]
        prefixed_edge_routes = [
            edge_route for edge_route in edge.priced_routes if is_real_prefix(route, edge_route.path)
        ]
        non_prefixed_edge_routes = [
            edge_route for edge_route in edge.priced_routes if not is_real_prefix(route, edge_route.path)
        ]
        return non_prefixed_edge_routes, prefixed_edge_routes

    def insert(self, target: NodeId, route: Route, cost: Cost):
        route = copy.deepcopy(route)
        self.measurements.received_route_length.increase(len(route))
        self.measurements.route_insertion_count.increase(1)
        modified_edges: list[tuple[NodeId, NodeId]] = []
        with self.measurements.route_update_seconds_sum:
            self._store_route(self.source, target, route, cost, modified_edges)
        with self.measurements.distance_update_seconds_sum:
            self._update_distances(modified_edges)

    def _update_distances(self, modified_edges: Optional[list[tuple[NodeId, NodeId]]] = None):
        if modified_edges is not None and len(modified_edges) == 0:
            return

        # Dijkstra:
        for i in self.nodes.keys():
            self.nodes[i].predecessor = None
            self.nodes[i].distance = math.inf
        self.nodes[self.source].distance = 0
        queue: list[NodeId] = list(self.nodes.keys())
        explored: set[NodeId] = set()
        while len(queue) != 0:
            u = min(queue, key=lambda nid: self.nodes[nid].distance)
            queue.remove(u)
            explored.add(u)
            for v in self.nodes[u].edges.keys():
                if v not in explored:
                    alt = self.nodes[u].distance + self.nodes[u].edges[v].cost()
                    if alt < self.nodes[v].distance:
                        self.nodes[v].predecessor = u
                        self.nodes[v].distance = alt
        self.nodes = {
            node_id: node
            for node_id, node in self.nodes.items()
            if node.distance != math.inf
        }

    def _route_exists(self, source: NodeId, route: Route) -> bool:
        for successor, edge in self.nodes[source].edges.items():
            for priced_route in edge.priced_routes:
                if priced_route.path == route:
                    return True
        return False

    def remove_routes_starting_with(self, route: Route):
        self._remove_routes_starting_with_rec(
            source=self.source,
            route=route,
        )
        self._update_distances()

    def _remove_routes_starting_with_rec(self, source: NodeId, route: Route):
        for successor, edge in self.nodes[source].edges.items():
            edge.priced_routes = [
                priced_route
                for priced_route in edge.priced_routes
                if not is_prefix(route, priced_route.path)
            ]
        self.nodes[source].edges = {
            successor: edge
            for successor, edge in self.nodes[source].edges.items()
            if any(edge.priced_routes)
        }

        # find known node on the route
        for successor, edge in self.nodes[source].edges.items():
            for edge_route in edge.priced_routes:
                if is_prefix(edge_route.path, route):
                    self._remove_routes_starting_with_rec(
                        source=successor,
                        route=route[len(edge_route.path):],
                    )
                    return

    def has_routes_starting_with(self, route: Route) -> bool:
        return self._has_routes_starting_with_rec(self.source, route)

    def _has_routes_starting_with_rec(self, source: NodeId, route: Route):
        for successor, edge in self.nodes[source].edges.items():
            for priced_route in edge.priced_routes:
                if is_prefix(route, priced_route.path):
                    return True
                if is_prefix(priced_route.path, route):
                    return self._has_routes_starting_with_rec(successor, route[len(priced_route.path):])


class _Measurements:
    def __init__(self, tracker: instrumentation.Tracker):
        self.route_insertion_count = tracker.get_counter(measurements.ROUTE_INSERTION_COUNT)
        self.route_update_seconds_sum = tracker.get_timer(measurements.ROUTE_UPDATE_SECONDS_SUM)
        self.distance_update_seconds_sum = tracker.get_timer(measurements.DISTANCE_UPDATE_SECONDS_SUM)
        self.received_route_length = tracker.get_counter(measurements.RECEIVED_ROUTE_LENGTH)


class Factory:
    def __init__(self, config: dict[str]):
        self.eliminate_cycles_eagerly = False if "eliminate_cycles_eagerly" not in config else config[
            "eliminate_cycles_eagerly"]
        self.eliminate_cycles = False if "eliminate_cycles" not in config else config["eliminate_cycles"]

    def create_store(self, logger: logging.Logger, source: NodeId, tracker: instrumentation.Tracker):
        return RouteStore(source, tracker, logger, self.eliminate_cycles, self.eliminate_cycles_eagerly)
