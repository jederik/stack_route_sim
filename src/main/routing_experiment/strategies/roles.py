import logging
import random
import typing
from typing import Optional
from overrides import override

import instrumentation
from .. import routing, net, route_storage, propagation
from ..net import NodeId, PortNumber, Cost
from ..propagation import Propagator
from ..routing import Route


class RoutePropagation:
    def __init__(self, target: NodeId, cost: Cost):
        self.cost = cost
        self.target = target


class Datagram:
    def __init__(self, payload, origin: Optional[Route] = None, destination: Optional[Route] = None):
        self.payload = payload
        self.origin = origin
        self.destination = destination


class Endpoint:
    def receive_unicast(self):
        raise Exception("not implemented")

    def receive_broadcast(self, datagram: Datagram):
        raise Exception("not implemented")


T = typing.TypeVar('T')


def _pick_random(rnd: random.Random, items: list[T]) -> T:
    return items[int(rnd.random() * len(items))]


class StackEngine(net.Adapter.Handler):
    def __init__(self, adapter: net.Adapter, broadcast_forwarding_rate: float, rnd: random.Random):
        self.rnd = rnd
        self.broadcast_forwarding_rate = broadcast_forwarding_rate
        self.adapter = adapter
        self.endpoint: Optional[Endpoint] = None

    @override
    def handle(self, port_num: PortNumber, message) -> None:
        datagram: Datagram = message
        if datagram.origin is not None:
            datagram.origin = [port_num] + datagram.origin
        if datagram.destination is not None:
            if len(datagram.destination) != 0:
                self.endpoint.receive_unicast()
            else:
                self.send_datagram(datagram)
        else:
            self.endpoint.receive_broadcast(datagram)

    def send_datagram(self, datagram: Datagram):
        if datagram.destination is not None:
            # unicast
            port_num = datagram.destination.pop(0)
            self.adapter.send(port_num, datagram)
        else:
            # broadcast
            if self.broadcast_forwarding_rate > self.rnd.random():
                port_num = _pick_random(self.rnd, self.adapter.ports())
                self.adapter.send(port_num, datagram)


class StackEngineRouter(routing.Router, Endpoint):
    def __init__(self, stack_engine: StackEngine):
        self.stack_engine = stack_engine

    @override
    def handler(self) -> net.Adapter.Handler:
        return self.stack_engine


class RouteCollector(StackEngineRouter):
    def __init__(self, store: route_storage.RouteStore, stack_engine: StackEngine):
        super().__init__(stack_engine)
        self.store = store

    @override
    def receive_broadcast(self, datagram: Datagram):
        route_propagation: RoutePropagation = datagram.payload
        self.store.insert(
            target=route_propagation.target,
            route=datagram.origin,
            cost=route_propagation.cost,
        )


class Forwarder(StackEngineRouter):

    def tick(self) -> None:
        pass

    def route(self, target: NodeId) -> Optional[Route]:
        return None

    def has_route(self, target: NodeId) -> bool:
        return False

    @override
    def receive_broadcast(self, datagram: Datagram):
        self.stack_engine.send_datagram(datagram)


class Server(StackEngineRouter):
    def __init__(self, stack_engine: StackEngine, address: NodeId):
        super().__init__(stack_engine)
        self.address = address

    @override
    def tick(self) -> None:
        self._self_promote()

    def _self_promote(self):
        self.stack_engine.send_datagram(
            Datagram(
                payload=RoutePropagation(
                    target=self.address,
                    cost=0,
                ),
                origin=[],
            )
        )

    @override
    def route(self, target: NodeId) -> Optional[Route]:
        return None

    @override
    def has_route(self, target: NodeId) -> bool:
        return False

    @override
    def receive_broadcast(self, datagram: Datagram):
        pass


class Client(RouteCollector):
    @override
    def tick(self) -> None:
        pass

    @override
    def route(self, target: NodeId) -> Optional[Route]:
        priced_route = self.store.shortest_route(target)
        if not priced_route:
            return None
        return priced_route.path

    @override
    def has_route(self, target: NodeId) -> bool:
        return self.store.has_route(target)

    @classmethod
    def create(cls, node_id: NodeId, store_factory: route_storage.Factory, stack_engine: StackEngine):
        tracker = instrumentation.Tracker(
            counters={},
        )
        logger = logging.Logger(f"node {node_id}")
        store = store_factory.create_store(logger, node_id, tracker)
        return Client(
            store=store,
            stack_engine=stack_engine,
        )


class Helper(RouteCollector):
    def __init__(self, store: route_storage.RouteStore, stack_engine: StackEngine, propagator: Propagator):
        super().__init__(store, stack_engine)
        self._propagator = propagator

    @override
    def tick(self) -> None:
        self._promote_route()

    def _promote_route(self):
        _, target, route, cost = self._propagator.pick(self.store, self.stack_engine.adapter)
        self._send_route_propagation(target, route, cost)

    @override
    def route(self, target: NodeId) -> Optional[Route]:
        return None

    @override
    def has_route(self, target: NodeId) -> bool:
        return False

    @classmethod
    def create(cls, node_id, store_factory: route_storage.Factory, stack_engine: StackEngine, config: dict[str],
               rnd: random.Random):
        logger, tracker = cls._init_telemetry(node_id)
        return Helper(
            store=store_factory.create_store(logger, node_id, tracker),
            stack_engine=stack_engine,
            propagator=propagation.create_propagator(config, rnd)
        )

    @classmethod
    def _init_telemetry(cls, node_id):
        tracker = instrumentation.Tracker(
            counters={},
        )
        logger = logging.Logger(f"node {node_id}")
        return logger, tracker

    def _send_route_propagation(self, target: NodeId, route: Route, cost: Cost):
        self.stack_engine.send_datagram(
            datagram=Datagram(
                origin=route,
                payload=RoutePropagation(
                    target=target,
                    cost=cost,
                ),
            )
        )


ROLES = ["server", "client", "helper", "forwarder"]


def _extract_accumulated_distributions(shares: dict[str, float]):
    total = sum([share for share in shares.values()])
    acc_probs: dict[str, float] = {}
    acc_prob: float = 0
    for role in ROLES:
        acc_prob += shares[role] / total
        acc_probs[role] = acc_prob
    return acc_probs


class RolesRouterFactory(routing.RouterFactory):
    def __init__(self, config: dict[str], rnd: random.Random):
        self.propagation_config = config["propagation"]
        self.store_factory = route_storage.Factory(config["store"] if "store" in config else {})
        self.rnd = rnd
        self.accumulated_role_probabilities = _extract_accumulated_distributions(config["role_distribution"])
        self.store_factory = route_storage.Factory(config=config["store"] if "store" in config else {})

    def create_router(self, adapter: net.Adapter, node_id: NodeId, tracker: instrumentation.Tracker) -> routing.Router:
        stack_engine = StackEngine(adapter, 0.9, self.rnd)
        choice = self.rnd.random()
        router: StackEngineRouter
        if self.accumulated_role_probabilities["server"] > choice:
            router = Server(stack_engine, node_id)
        elif self.accumulated_role_probabilities["client"] > choice:
            router = Client.create(node_id, self.store_factory, stack_engine)
        elif self.accumulated_role_probabilities["helper"] > choice:
            router = Helper.create(node_id, self.store_factory, stack_engine, self.propagation_config, self.rnd)
        else:
            router = Forwarder(stack_engine)
        stack_engine.endpoint = router
        return router
