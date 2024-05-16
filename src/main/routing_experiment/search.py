import bisect
import random

from routing_experiment import route_storage, stacking
from routing_experiment.advertising import RouteAdvertisement
from routing_experiment.extendable_router import ExtendableRouter
from routing_experiment.net import NodeId, Cost
from routing_experiment.routing import Route


class RouteSearchMessage:
    def __init__(self, target: NodeId):
        self.target = target


class Searcher(ExtendableRouter.MessageHandler, ExtendableRouter.Task):
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
            payload=RouteAdvertisement(target, cost),
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
