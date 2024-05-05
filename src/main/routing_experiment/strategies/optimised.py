import random
from typing import Optional, TypeVar

import instrumentation
from .. import net
from ..net import NodeId, PortNumber, Cost
from ..route_storage import RouteStore
from ..routing import Router, Route, RouterFactory


class PropagationMessage:
    def __init__(self, target: NodeId, route: Route, cost: Cost):
        self.cost = cost
        self.route = route
        self.target = target


T = TypeVar('T')


def _pick_random(items: list[T], rnd: random.Random) -> T:
    return items[int(rnd.random() * len(items))]


class Propagator:
    def pick(self, router: 'OptimisedRouter'):
        raise Exception("not implemented")


class OptimisedRouter(Router, net.Adapter.Handler):
    def __init__(
            self,
            adapter: net.Adapter,
            node_id: NodeId,
            propagation_strategy: Propagator,
            tracker: instrumentation.Tracker,
            eliminate_cycles: bool,
    ):
        self.eliminate_cycles = eliminate_cycles
        self.node_id = node_id
        self.adapter = adapter
        self.store = RouteStore(node_id, tracker)
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
        self._handle_propagation_message(message, port_num)

    def _handle_propagation_message(self, message: PropagationMessage, port_num: PortNumber):
        if self.eliminate_cycles and message.target == self.node_id:
            return
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


class RandomRoutePropagator(Propagator):
    def __init__(self, cutoff_rate: float, rnd: random.Random):
        self.cutoff_rate = cutoff_rate
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
        if self.cutoff_rate > self.rnd.random():
            return source, [], 0
        successor = _pick_random(list(store.nodes[source].edges.keys()), self.rnd)
        target, route_tail, tail_cost = self._get_random_route(store, successor)
        edged_route = _pick_random(store.nodes[source].edges[successor].priced_routes, self.rnd)
        return target, edged_route.path + route_tail, edged_route.cost + tail_cost

    @classmethod
    def create(cls, config, rnd: random.Random):
        return RandomRoutePropagator(config["cutoff_rate"], rnd)


class ShortestRoutePropagator(Propagator):
    def __init__(self, rnd: random.Random):
        self.rnd = rnd

    def pick(self, router: OptimisedRouter) -> tuple[PortNumber, NodeId, Route, Cost]:
        port = _pick_random(router.adapter.ports(), self.rnd)
        target = _pick_random(list(router.store.nodes.keys()), self.rnd)
        priced_route = router.store.shortest_route(target)
        return port, target, priced_route.path, priced_route.cost

    @classmethod
    def create(cls, config, rnd: random.Random):
        return ShortestRoutePropagator(
            rnd=rnd,
        )


class AlternativeRoutePropagator(Propagator):
    def __init__(self, rnd: random.Random, random_propagator: RandomRoutePropagator, random_ratio: float,
                 shortest_propagator: ShortestRoutePropagator):
        self.shortest_propagator = shortest_propagator
        self.random_propagator = random_propagator
        self.rnd = rnd
        self.random_ratio = random_ratio

    def pick(self, router: 'OptimisedRouter') -> tuple[PortNumber, NodeId, Route, Cost]:
        if self.random_ratio > self.rnd.random():
            return self.random_propagator.pick(router)
        else:
            return self.shortest_propagator.pick(router)

    @classmethod
    def create(cls, config, rnd: random.Random):
        return AlternativeRoutePropagator(
            random_propagator=RandomRoutePropagator.create(config["random"], rnd),
            rnd=rnd,
            random_ratio=config["random_ratio"],
            shortest_propagator=ShortestRoutePropagator.create(config["shortest"], rnd)
        )


def _create_propagator(config, rnd: random.Random) -> Propagator:
    strategy = config["strategy"]
    if strategy == "random_route":
        return RandomRoutePropagator.create(config, rnd)
    if strategy == "shortest_route":
        return ShortestRoutePropagator.create(config, rnd)
    if strategy == "alternate":
        return AlternativeRoutePropagator.create(config, rnd)
    raise Exception(f"unknown propagation strategy: {strategy}")


class OptimisedRouterFactory(RouterFactory):
    def __init__(self, routing_config, rnd: random.Random):
        self.eliminate_cycles = False if "eliminate_cycles" not in routing_config else routing_config["eliminate_cycles"]
        self.rnd = rnd
        self.propagator = _create_propagator(routing_config["propagation"], rnd)

    def create_router(self, adapter: net.Adapter, node_id: NodeId, tracker: instrumentation.Tracker) -> Router:
        return OptimisedRouter(
            adapter=adapter,
            node_id=node_id,
            propagation_strategy=self.propagator,
            tracker=tracker,
            eliminate_cycles=self.eliminate_cycles,
        )
