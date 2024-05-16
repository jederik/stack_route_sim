import bisect
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


class MessageHandler:
    def handle(self, datagram: stacking.Datagram):
        raise Exception("not implemented")


class PortDisconnectedTask:
    def execute(self, port_num: net.PortNumber):
        raise Exception("not implemented")


class ExtendableRouter(StackEngineRouter):
    class Task:
        def execute(self):
            raise Exception("not implemented")

    def __init__(
            self,
            stack_engine: stacking.StackEngine,
            scheduled_tasks: list[Task],
            message_handlers: dict[type, MessageHandler],
            demand_map: dict[NodeId, float],
            auto_forward_propagations: bool,
            port_disconnected_tasks: list[PortDisconnectedTask],
            store: Optional[route_storage.RouteStore] = None,
    ):
        super().__init__(stack_engine)
        self.port_disconnected_tasks = port_disconnected_tasks
        self.message_handlers = message_handlers
        self.auto_forward_propagations = auto_forward_propagations
        self.demand_map = demand_map
        self.scheduled_tasks = scheduled_tasks
        self.store = store
        
    def on_port_disconnected(self, port_num: net.PortNumber):
        for task in self.port_disconnected_tasks:
            task.execute(port_num)

    def tick(self) -> None:
        for task in self.scheduled_tasks:
            task.execute()

    def receive_datagram(self, datagram: stacking.Datagram):
        self.message_handlers[type(datagram.payload)].handle(datagram)

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
        choice = self.propagator.pick(self.store, self.stack_engine.adapter)
        if choice is not None:
            (_, target, route, cost) = choice
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


class PropagationHandler(MessageHandler):
    def __init__(
            self,
            auto_forward_propagations: bool,
            store: route_storage.RouteStore,
            stack_engine: stacking.StackEngine,
    ):
        self.stack_engine = stack_engine
        self.store = store
        self.auto_forward_propagations = auto_forward_propagations

    def handle(self, datagram: stacking.Datagram):
        if self.store is not None:
            incoming_port = datagram.origin[0]
            port_cost = self.stack_engine.adapter.port_cost(incoming_port)
            datagram.payload.cost += port_cost
            self.store.insert(
                target=datagram.payload.target,
                route=datagram.origin,
                cost=datagram.payload.cost,
            )
        if self.auto_forward_propagations:
            self.stack_engine.send_datagram(datagram)


class RouteSearchMessage:
    def __init__(self, target: NodeId):
        self.target = target


class Searcher(MessageHandler, ExtendableRouter.Task):
    def __init__(
            self,
            store: route_storage.RouteStore,
            stacking_engine: stacking.StackEngine,
            rnd: random.Random,
            demand_map: dict[NodeId, float],
    ):
        self.demand_pairs, self.total_demand = self._prepare_demand_pairs(demand_map)
        self.rnd = rnd
        self.stacking_engine = stacking_engine
        self.store = store

    def execute(self):
        target = self._pick_demanded_node()
        self._send_request(target)

    def handle(self, datagram: stacking.Datagram):
        search: RouteSearchMessage = datagram.payload
        if self.store.has_route(search.target):
            priced_route = self.store.shortest_route(search.target)
            self._send_answer(
                return_route=datagram.origin,
                target=search.target,
                route=priced_route.path,
                cost=priced_route.cost,
            )
        self._send_request(search.target, origin=datagram.origin)

    def _send_answer(self, return_route: Route, target: NodeId, route: Route, cost: Cost):
        answer = stacking.Datagram(
            payload=RoutePropagationMessage(target, cost),
            origin=route,
            destination=return_route,
        )
        self.stacking_engine.send_datagram(answer)

    def _pick_demanded_node(self) -> NodeId:
        pos = self.rnd.random() * self.total_demand
        index = bisect.bisect_right(self.demand_pairs, (pos, 0))
        return self.demand_pairs[index][1]

    def _send_request(self, target: NodeId, origin: Route = None):
        if origin is None:
            origin = []
        request = stacking.Datagram(
            payload=RouteSearchMessage(target),
            origin=origin,
        )
        self.stacking_engine.send_datagram(request)

    @staticmethod
    def _prepare_demand_pairs(demand_map: dict[NodeId, float]) -> tuple[list[tuple[float, NodeId]], float]:
        pairs = []
        accumulated_demand: float = 0
        for node_id, demand in demand_map.items():
            accumulated_demand += demand
            pairs.append((accumulated_demand, node_id))
        return pairs, accumulated_demand


class LinkFailureAdvertisement:
    pass


class LinkFailureAdvertiser(PortDisconnectedTask):
    def __init__(self, stack_engine: stacking.StackEngine):
        self.stack_engine = stack_engine

    def execute(self, port_num: net.PortNumber):
        advertisement = stacking.Datagram(
            payload=LinkFailureAdvertisement(
            ),
            origin=[port_num],
        )
        self.stack_engine.send_datagram(advertisement)


class LinkFailureAdvertisementHandler(MessageHandler):
    def __init__(self, stack_engine: stacking.StackEngine, store: route_storage.RouteStore):
        self.store = store
        self.stack_engine = stack_engine

    def handle(self, datagram: stacking.Datagram):
        advertisement: LinkFailureAdvertisement = datagram.payload
        route = datagram.origin
        if self.store.has_routes_starting_with(route):
            self.store.remove_routes_starting_with(route)
            self.stack_engine.send_full_broadcast(
                datagram=stacking.Datagram(
                    payload=datagram.payload,
                    origin=datagram.origin,
                ),
            )


class StackedRouterFactory(routing.RouterFactory):
    def __init__(self, config: dict, rnd: random.Random, node_count: int):
        self.advertise_link_failures = config["advertise_link_failures"]
        self.searching_enabled = config["searching"]
        self.auto_forward_propagations = config["auto_forward_propagations"]
        self.random_walk_broadcasting = (
            config["random_walk_broadcasting"]
            if self.auto_forward_propagations
            else False
        )
        self.route_propagation: bool = config["route_propagation"]
        self.self_propagation: bool = config["self_propagation"]
        self.broadcast_forwarding_rate: float = config["broadcast_forwarding_rate"]
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
            random_walk_broadcasting=self.random_walk_broadcasting
        )
        demand_map = self.generate_demand_map()
        propagator = propagation.create_propagator(self.config["propagation"], self.rnd)
        logger, tracker = _init_telemetry(node_id)
        store = self.store_factory.create_store(logger, node_id, tracker)
        scheduled_tasks = []
        if self.route_propagation:
            scheduled_tasks.append(
                RoutePropagator(
                    propagator=propagator,
                    store=store,
                    stack_engine=stack_engine,
                ),
            )
        if self.self_propagation:
            scheduled_tasks.append(
                SelfPropagator(
                    stack_engine=stack_engine,
                    address=node_id,
                ),
            )
        message_handlers = {
            RoutePropagationMessage: PropagationHandler(
                auto_forward_propagations=self.auto_forward_propagations,
                store=store,
                stack_engine=stack_engine,
            ),
        }
        if self.searching_enabled:
            searcher = Searcher(store, stack_engine, self.rnd, demand_map)
            message_handlers[RouteSearchMessage] = searcher
            scheduled_tasks.append(searcher)
        port_disconnected_tasks = []
        if self.advertise_link_failures:
            message_handlers[LinkFailureAdvertisement] = LinkFailureAdvertisementHandler(stack_engine, store)
            port_disconnected_tasks.append(LinkFailureAdvertiser(stack_engine))
        router = ExtendableRouter(
            stack_engine=stack_engine,
            scheduled_tasks=scheduled_tasks,
            demand_map=demand_map,
            auto_forward_propagations=self.auto_forward_propagations,
            store=store,
            message_handlers=message_handlers,
            port_disconnected_tasks=port_disconnected_tasks,
        )
        stack_engine.endpoint = router
        return router

    def generate_demand_map(self) -> dict[NodeId, float]:
        return {
            node_id: self.rnd.random()
            for node_id in range(self.node_count)
        }
