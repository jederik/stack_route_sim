from typing import Optional

from overrides import override

from routing_experiment import routing, stacking, net, route_storage
from routing_experiment.net import NodeId
from routing_experiment.routing import Route


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

    class MessageHandler:
        def handle(self, datagram: stacking.Datagram):
            raise Exception("not implemented")

    class PortDisconnectedTask:
        def execute(self, port_num: net.PortNumber):
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
