import logging
import random
from typing import Optional

from overrides import override

import instrumentation
from .. import routing, net, route_storage, propagation, stacking
from ..net import NodeId, Cost
from ..propagation import Propagator
from ..routing import Route


class RoutePropagationMessage:
    def __init__(self, target: NodeId, cost: Cost):
        self.cost = cost
        self.target = target


class StackEngineRouter(routing.Router, stacking.Endpoint):
    def __init__(self, stack_engine: stacking.StackEngine):
        self.stack_engine = stack_engine

    @override
    def handler(self) -> net.Adapter.Handler:
        return self.stack_engine


class ExtendableRouter(StackEngineRouter):
    class Task:
        def execute(self):
            raise Exception("not implemented")

    def __init__(
            self,
            stack_engine: stacking.StackEngine,
            scheduled_tasks: list[Task],
            demand_map: dict[NodeId, float],
            store: Optional[route_storage.RouteStore] = None,
    ):
        super().__init__(stack_engine)
        self.demand_map = demand_map
        self.scheduled_tasks = scheduled_tasks
        self.store = store

    def tick(self) -> None:
        for task in self.scheduled_tasks:
            task.execute()

    def receive_broadcast(self, datagram: stacking.Datagram):
        if self.store is not None:
            if isinstance(datagram.payload, RoutePropagationMessage):
                self.store.insert(
                    target=datagram.payload.target,
                    route=datagram.origin,
                    cost=datagram.payload.cost,
                )

    def route(self, target: NodeId) -> Optional[Route]:
        if self.store is not None:
            priced_route = self.store.shortest_route(target)
            if priced_route is not None:
                return priced_route.path
        return None

    def has_route(self, target: NodeId) -> bool:
        if self.store is not None:
            return self.store.has_route(target)
        return False

    def demand(self, target) -> float:
        return self.demand_map[target]


class SelfPropagator(ExtendableRouter.Task):
    def __init__(self, stack_engine: stacking.StackEngine, address: NodeId):
        self.address = address
        self.stack_engine = stack_engine

    def execute(self):
        self.stack_engine.send_datagram(
            stacking.Datagram(
                payload=RoutePropagationMessage(
                    target=self.address,
                    cost=0,
                ),
                origin=[],
            )
        )


class RoutePropagator(ExtendableRouter.Task):
    def __init__(
            self,
            propagator: Propagator,
            store: route_storage.RouteStore,
            stack_engine: stacking.StackEngine,
    ):
        self.stack_engine = stack_engine
        self.store = store
        self.propagator = propagator

    def execute(self):
        _, target, route, cost = self.propagator.pick(self.store, self.stack_engine.adapter)
        self._send_route_propagation(target, route, cost)

    def _send_route_propagation(self, target: NodeId, route: Route, cost: Cost):
        self.stack_engine.send_datagram(
            datagram=stacking.Datagram(
                origin=route,
                payload=RoutePropagationMessage(
                    target=target,
                    cost=cost,
                ),
            )
        )


def _init_telemetry(node_id) -> tuple[logging.Logger, instrumentation.Tracker]:
    tracker = instrumentation.Tracker(
        counters={},
    )
    logger = logging.Logger(f"node {node_id}")
    return logger, tracker


class StackedRouterFactory(routing.RouterFactory):
    def __init__(self, config: dict, rnd: random.Random, node_count: int):
        self.broadcasting_auto_forward = config["broadcasting_auto_forward"]
        self.broadcast_forwarding_rate = config["broadcast_forwarding_rate"]
        self.node_count = node_count
        self.config = config
        self.store_factory = route_storage.Factory(config["store"] if "store" in config else {})
        self.rnd = rnd
        self.store_factory = route_storage.Factory(config=config["store"] if "store" in config else {})

    def create_router(
            self,
            adapter: net.Adapter,
            node_id: NodeId,
            tracker: instrumentation.Tracker,
    ) -> routing.Router:
        stack_engine = stacking.StackEngine(
            adapter=adapter,
            rnd=self.rnd,
            broadcasting_forwarding_rate=self.broadcast_forwarding_rate,
            broadcasting_auto_forward=self.broadcasting_auto_forward
        )
        demand_map = self.generate_demand_map()
        propagator = propagation.create_propagator(self.config["propagation"], self.rnd)
        logger, tracker = _init_telemetry(node_id)
        store = self.store_factory.create_store(logger, node_id, tracker)
        router = ExtendableRouter(
            stack_engine=stack_engine,
            scheduled_tasks=[
                # SelfPropagator(
                #     stack_engine=stack_engine,
                #     address=node_id,
                # ),
                RoutePropagator(
                    propagator=propagator,
                    store=store,
                    stack_engine=stack_engine,
                ),
            ],
            demand_map=demand_map,
            store=store,
        )
        stack_engine.endpoint = router
        return router

    def generate_demand_map(self) -> dict[NodeId, float]:
        return {
            node_id: self.rnd.random()
            for node_id in range(self.node_count)
        }
