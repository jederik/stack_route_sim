import random
from typing import TypeVar

from routing_experiment import net
from routing_experiment.net import PortNumber, NodeId, Cost
from routing_experiment.route_storage import RouteStore
from routing_experiment.routing import Route


class Propagator:
    def pick(self, store: RouteStore, adapter: net.Adapter) -> tuple[PortNumber, NodeId, Route, Cost]:
        raise Exception("not implemented")


class PortPicker:
    def pick(self, adapter: net.Adapter) -> PortNumber:
        raise Exception("not implemented")


class RoutePicker:
    def pick(self, store: RouteStore) -> tuple[NodeId, Route, Cost]:
        raise Exception("not implemented")


class CompositePropagator(Propagator):
    def __init__(self, port_picker: PortPicker, route_picker: RoutePicker):
        self.port_picker = port_picker
        self.route_picker = route_picker

    def pick(self, store: RouteStore, adapter: net.Adapter) -> tuple[PortNumber, NodeId, Route, Cost]:
        port = self.port_picker.pick(adapter)
        target, route, cost = self.route_picker.pick(store)
        return port, target, route, cost


class RandomPortPicker(PortPicker):
    def __init__(self, rnd: random.Random):
        self.rnd = rnd

    def pick(self, adapter: net.Adapter) -> PortNumber:
        ports = adapter.ports()
        if len(ports) == 0:
            raise Exception("no ports available")
        return _pick_random(ports, self.rnd)


class RandomRoutePicker(RoutePicker):
    def __init__(self, cutoff_rate: float, rnd: random.Random):
        self.rnd = rnd
        self.cutoff_rate = cutoff_rate

    def pick(self, store: RouteStore) -> tuple[NodeId, Route, Cost]:
        return self._get_random_route(store)

    def _get_random_route(self, store: RouteStore, source: NodeId = None) -> tuple[NodeId, Route, Cost]:
        if source is None:
            source = store.source
        if len(store.nodes[source].edges) == 0:
            return source, [], 0
        if self.cutoff_rate > self.rnd.random():
            return source, [], 0
        successor = _pick_random(list(store.nodes[source].edges.keys()), self.rnd)
        target, route_tail, tail_cost = self._get_random_route(store, successor)
        edged_route = _pick_random(store.nodes[source].edges[successor].priced_routes, self.rnd)
        return target, edged_route.path + route_tail, edged_route.cost + tail_cost


class RandomRoutePropagator:
    @classmethod
    def create(cls, config, rnd: random.Random):
        return CompositePropagator(
            port_picker=RandomPortPicker(rnd),
            route_picker=RandomRoutePicker(config["cutoff_rate"], rnd)
        )


class ShortestRoutePicker(RoutePicker):
    def __init__(self, rnd: random.Random):
        self.rnd = rnd

    def pick(self, store: RouteStore) -> tuple[NodeId, Route, Cost]:
        target = _pick_random(list(store.nodes.keys()), self.rnd)
        priced_route = store.shortest_route(target)
        return target, priced_route.path, priced_route.cost


class ShortestRoutePropagator:
    @classmethod
    def create(cls, config, rnd: random.Random):
        return CompositePropagator(
            port_picker=RandomPortPicker(rnd),
            route_picker=ShortestRoutePicker(rnd),
        )


class AlternativeRoutePropagator(Propagator):
    def __init__(
            self,
            first_propagator: Propagator,
            second_propagator: Propagator,
            ratio: float,
            rnd: random.Random,
    ):
        self.first_propagator = first_propagator
        self.second_propagator = second_propagator
        self.ratio = ratio
        self.rnd = rnd

    def pick(self, store: RouteStore, adapter: net.Adapter) -> tuple[PortNumber, NodeId, Route, Cost]:
        if self.ratio > self.rnd.random():
            return self.first_propagator.pick(store, adapter)
        else:
            return self.second_propagator.pick(store, adapter)

    @classmethod
    def create(cls, config, rnd: random.Random):
        return AlternativeRoutePropagator(
            first_propagator=RandomRoutePropagator.create(config["random"], rnd),
            second_propagator=ShortestRoutePropagator.create(config["shortest"], rnd),
            ratio=config["ratio"],
            rnd=rnd,
        )


def create_propagator(config, rnd: random.Random) -> Propagator:
    strategy = config["strategy"]
    if strategy == "random_route":
        return RandomRoutePropagator.create(config, rnd)
    if strategy == "shortest_route":
        return ShortestRoutePropagator.create(config, rnd)
    if strategy == "alternate":
        return AlternativeRoutePropagator.create(config, rnd)
    raise Exception(f"unknown propagation strategy: {strategy}")


T = TypeVar('T')


def _pick_random(items: list[T], rnd: random.Random) -> T:
    return items[int(rnd.random() * len(items))]
