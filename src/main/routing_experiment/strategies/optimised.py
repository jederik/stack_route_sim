import random
from typing import Optional
from overrides import override

import instrumentation
import logging
from .. import net, route_storage
from ..net import NodeId, PortNumber, Cost
from ..propagation import Propagator, create_propagator
from ..route_storage import RouteStore
from ..routing import Router, Route, RouterFactory


class PropagationMessage:
    def __init__(self, target: NodeId, route: Route, cost: Cost):
        self.cost = cost
        self.route = route
        self.target = target


class OptimisedRouter(Router, net.Adapter.Handler):
    def __init__(
            self,
            adapter: net.Adapter,
            node_id: NodeId,
            propagation_strategy: Propagator,
            store: RouteStore,
            logger: logging.Logger,
            default_demand: float,
    ):
        self.default_demand = default_demand
        self.logger = logger
        self.node_id = node_id
        self.adapter = adapter
        self.store = store
        self._propagation_strategy = propagation_strategy

    @override
    def route(self, target: NodeId) -> Optional[Route]:
        priced_route = self.store.shortest_route(target)
        if not priced_route:
            return None
        return priced_route.path

    @override
    def has_route(self, target: NodeId) -> bool:
        return self.store.has_route(target)

    @override
    def handle(self, port_num: PortNumber, message) -> None:
        message: PropagationMessage = message
        self._handle_propagation_message(message, port_num)

    def _handle_propagation_message(self, message: PropagationMessage, port_num: PortNumber):
        self.store.insert(
            target=message.target,
            route=[port_num] + message.route,
            cost=message.cost + self.adapter.port_cost(port_num),
        )

    @override
    def tick(self) -> None:
        choice = self._propagation_strategy.pick(self.store, self.adapter)
        if choice is not None:
            (port, target, route, cost) = choice
            self._send_propagation_message(port, target, route, cost)

    def _send_propagation_message(self, port_num: PortNumber, target: NodeId, route: Route, cost: Cost):
        message = PropagationMessage(target, route, cost)
        self.adapter.send(port_num, message)

    @override
    def handler(self) -> net.Adapter.Handler:
        return self

    @override
    def demand(self, target) -> float:
        return self.default_demand


class OptimisedRouterFactory(RouterFactory):
    def __init__(self, routing_config, rnd: random.Random, node_count: int):
        self.store_factory = route_storage.Factory(config=routing_config["store"] if "store" in routing_config else {})
        self.rnd = rnd
        self.propagator = create_propagator(routing_config["propagation"], rnd)

    def create_router(self, adapter: net.Adapter, node_id: NodeId, tracker: instrumentation.Tracker) -> Router:
        logger = logging.getLogger(name=f"node {node_id}")
        store = self.store_factory.create_store(logger, node_id, tracker)
        return OptimisedRouter(
            adapter=adapter,
            node_id=node_id,
            propagation_strategy=self.propagator,
            store=store,
            logger=logger,
            default_demand=1,
        )
