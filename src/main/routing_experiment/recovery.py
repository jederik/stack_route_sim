from routing_experiment import stacking, net, route_storage
from routing_experiment.extendable_router import ExtendableRouter


class LinkFailureAdvertisement:
    pass


class LinkFailureAdvertiser(ExtendableRouter.PortDisconnectedTask):
    def __init__(self, stack_engine: stacking.StackEngine):
        self.stack_engine = stack_engine

    def execute(self, port_num: net.PortNumber):
        advertisement = stacking.Datagram(
            payload=LinkFailureAdvertisement(
            ),
            origin=[port_num],
        )
        self.stack_engine.send_datagram(advertisement)


class LinkFailureAdvertisementHandler(ExtendableRouter.MessageHandler):
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
