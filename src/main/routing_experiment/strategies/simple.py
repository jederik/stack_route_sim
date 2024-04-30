import random
from typing import Callable, Optional

import instrumentation
from routing_experiment import net
from routing_experiment.routing import Route, RouterFactory, Router
from routing_experiment.net import NodeId, PortNumber

_NodeRoutes = list[Route]
_RouteStore = dict[NodeId, _NodeRoutes]


class SimpleRouter(Router, net.Adapter.Handler):
    def __init__(
            self,
            adapter: net.Adapter,
            node_id: NodeId,
            propagation_route_picker: Callable[[_RouteStore], Route],
    ):
        self.workers: list[Worker] = []
        self.pick_propagation_route = propagation_route_picker
        self.routes: _RouteStore = {
            node_id: [[]]
        }
        self.adapter = adapter
        adapter.register_handler(self)

    def has_route(self, target: NodeId) -> bool:
        return target in self.routes and len(self.routes[target]) != 0

    def tick(self):
        for worker in self.workers:
            worker.execute()

    def handle(self, port_num: PortNumber, message):
        prop: RoutePropagationMessage = message
        node_routes = self._get_node_routes(prop.node_id)
        route = prop.route
        route.append(port_num)
        node_routes.append(route)

    def route(self, target: NodeId) -> Optional[Route]:
        return _shortest_route(self.routes, target)

    def _get_node_routes(self, node_id: NodeId):
        if node_id in self.routes:
            return self.routes[node_id]
        else:
            self.routes[node_id] = []
            return self.routes[node_id]


class RoutePropagationMessage:
    def __init__(self, node_id: int, route: list[int]):
        self.route = route
        self.node_id = node_id


class Worker:
    def execute(self):
        raise Exception("not implemented")


def _pick_propagation_route_random(routes: _RouteStore) -> (NodeId, Route):
    nodes = list(routes.keys())
    node_id = nodes[int(random.random() * len(nodes))]
    node_routes = routes[node_id]
    return node_id, node_routes[int(random.random() * len(node_routes))]


def _pick_propagation_route_shortest(routes: _RouteStore) -> (NodeId, Route):
    nodes = list(routes.keys())
    node_id = nodes[int(random.random() * len(nodes))]
    return node_id, _shortest_route(routes, node_id)


class RoutePropagator(Worker):
    def __init__(self, router: SimpleRouter, propagation_route_picker: Callable[[_RouteStore], Route]):
        self.router = router
        self.pick_propagation_route = propagation_route_picker

    def execute(self):
        ports = self.router.adapter.ports()
        port_num = ports[int(random.random() * len(ports))]
        target_id, route = self.pick_propagation_route(self.router.routes)
        prop_msg = RoutePropagationMessage(target_id, route)
        self.router.adapter.send(port_num, prop_msg)


class SimpleRouterFactory(RouterFactory):
    def __init__(self, config, rnd: random.Random):
        self.config = config

    def create_router(self, adapter: net.Adapter, node_id: NodeId, tracker: instrumentation.Tracker):
        router = SimpleRouter(
            adapter=adapter,
            node_id=node_id,
            propagation_route_picker=_pick_propagation_route_shortest if self.config[
                "propagate_shortest_route"] else _pick_propagation_route_random,
        )
        router.workers = [
            RoutePropagator(
                router=router,
                propagation_route_picker=_pick_propagation_route_shortest if self.config[
                    "propagate_shortest_route"] else _pick_propagation_route_random
            ),
        ]
        return router


def _shortest_route(routes, target):
    if target not in routes:
        return None
    target_routes = routes[target]
    if len(target_routes) == 0:
        return None
    shortest_route = min(target_routes, key=lambda route: len(route))
    return shortest_route
