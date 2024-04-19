import random
from typing import Optional, TypeVar

import net
from routes import NodeId, Route, Cost, PortNumber
from routing import Router
from strategies.optimised import PropagationMessage
from strategy import RoutingStrategy


class _Segment:
    def __init__(self, route: Route, cost: Cost):
        self.cost = cost
        self.route = route

    def __add__(self, other: '_Segment'):
        return _Segment(
            route=self.route + other.route,
            cost=self.cost + other.cost,
        )


class _Node:
    def __init__(self, pred: NodeId):
        self.pred = pred
        self.out_segments: list[_Segment] = []


T = TypeVar('T')


def _pick_random(items: list[T]) -> T:
    return items[int(random.random() * len(items))]


class RouteCombinerStore:
    def __init__(self, node_id: NodeId):
        self.node_id = node_id
        self.nodes: dict[NodeId, _Node] = {}

    def cheapest_route(self, target: NodeId) -> Optional[Route]:
        if target not in self.nodes:
            return None
        cheapest_segment = self._cheapest_segment(target)
        if cheapest_segment:
            return cheapest_segment.route
        else:
            return None

    def _cheapest_segment(self, target) -> Optional[_Segment]:
        if target == self.node_id:
            return _Segment(
                route=[],
                cost=0,
            )
        else:
            pred = self.nodes[target].pred
            segment = self.nodes[pred].out_segments[0]
            return self._cheapest_segment(pred) + segment

    def pick_propagation_segment(self) -> (NodeId, Route, Cost):
        nodes = list(self.nodes.keys())
        target = _pick_random(nodes)
        segment = self._cheapest_segment(target)
        if segment is None:
            raise Exception(f"no route to node {target}")
        return target, segment.route, segment.cost

    def insert(self):
        self._walk()

    def _walk(self):
        successor = self._node_on_route()
        if successor:
            return self._walk()
        else:
            self._interject()

    def _node_on_route(self) -> Optional[NodeId]:
        raise Exception("not implemented")

    def _interject(self):
        nodes_behind, nodes_not_behind = self._whats_behind()
        if nodes_behind:
            pass


    def _whats_behind(self) -> ():
        pass


class CombiningRouter(Router, net.Adapter.Handler):
    def __init__(self, node_id: NodeId, adapter: net.Adapter):
        self.adapter = adapter
        self.store = RouteCombinerStore(node_id)

    def route(self, target: NodeId) -> Optional[Route]:
        return self.store.cheapest_route(target)

    def tick(self):
        self._send_propagation_message()

    def handle(self, port_num: PortNumber, message):
        message: PropagationMessage = message
        self.store.insert()

    def _send_propagation_message(self):
        port_num = self._pick_propagation_port()
        target, route, cost = self.store.pick_propagation_segment()
        message = PropagationMessage(
            target=target,
            route=route,
            cost=cost,
        )
        self.adapter.send(port_num, message)

    def _pick_propagation_port(self):
        port_nums = self.adapter.ports()
        return port_nums[int(random.random() * len(port_nums))]


class CombiningRoutingStrategy(RoutingStrategy):
    def build_router(self, adapter: net.Adapter, node_id: NodeId) -> Router:
        return CombiningRouter(node_id, adapter)
