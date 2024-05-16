from routing_experiment import stacking, route_storage
from routing_experiment.extendable_router import ExtendableRouter
from routing_experiment.net import NodeId, Cost
from routing_experiment.propagation import Propagator
from routing_experiment.routing import Route


class RouteAdvertisement:
    def __init__(self, target: NodeId, cost: Cost):
        self.cost = cost
        self.target = target


class SelfAdvertiser(ExtendableRouter.Task):
    def __init__(self, stack_engine: stacking.StackEngine, address: NodeId):
        self.address = address
        self.stack_engine = stack_engine

    def execute(self):
        self.stack_engine.send_datagram(
            stacking.Datagram(
                payload=RouteAdvertisement(
                    target=self.address,
                    cost=0,
                ),
                origin=[],
            )
        )


class RouteAdvertiser(ExtendableRouter.Task):
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
                payload=RouteAdvertisement(
                    target=target,
                    cost=cost,
                ),
            )
        )


class AdvertisementHandler(ExtendableRouter.MessageHandler):
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
            advertisement: RouteAdvertisement = datagram.payload
            advertisement.cost += port_cost
            self.store.insert(
                target=datagram.payload.target,
                route=datagram.origin,
                cost=datagram.payload.cost,
            )
        if self.auto_forward_propagations:
            self.stack_engine.send_datagram(datagram)
