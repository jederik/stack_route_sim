import random
import typing
import unittest
from unittest.mock import Mock, MagicMock

from routing_experiment.net import Network, NodeId, Cost
from routing_experiment.routing import Route
from routing_experiment.strategies.optimised import RouteStore, _Node, _Edge, PricedRoute

from routing_experiment.setup import generate_network

T = typing.TypeVar('T')


def _pick_random(items: list[T], rnd: random.Random) -> T:
    return items[int(rnd.random() * len(items))]


def _random_walk(network: Network, source: NodeId, rnd: random.Random) -> tuple[NodeId, Route, Cost]:
    node = source
    route = []
    cost = 0
    while rnd.random() < .9:
        port_num = _pick_random(list(network.nodes[node].ports.keys()), rnd)
        route += [port_num]
        port = network.nodes[node].ports[port_num]
        cost += port.cost
        node = port.target_node
    return node, route, cost


class MyTestCase(unittest.TestCase):
    def test_self_route(self):
        store = RouteStore(1, Mock(), Mock())
        self.assertEqual([], store.shortest_route(1).path)  # add assertion here

    def test_insertion(self):
        store = RouteStore(1, Mock(), MagicMock())
        route = [1, 2, 3, 4]
        store.insert(2, route, 4)
        self.assertEqual(route, store.shortest_route(2).path)

    def test_combined_routes(self):
        store = RouteStore(1, Mock(), MagicMock())
        store.insert(3, [1, 2, 4], 3)
        store.insert(2, [1, 2], 2)
        store.insert(2, [3], 1)
        self.assertEqual([3, 4], store.shortest_route(3).path)

    def test_random_route(self):
        for i in range(100):
            rnd = random.Random(i)
            network = generate_network(
                config={
                    "node_count": 20,
                    "density": .5,
                },
                rnd=rnd,
                tracker=Mock(),
            )
            source = int(rnd.random() * len(network.nodes))
            store = RouteStore(source, rnd, MagicMock())
            for _ in range(10):
                target, route, cost = _random_walk(network, source, rnd)
                store.insert(target, route, cost)
            target = int(rnd.random() * len(network.nodes))
            priced_route = store.shortest_route(target)
            if priced_route is not None:
                route = priced_route.path
                cost = priced_route.cost

                node = source
                expected_cost = 0
                for port_num in route:
                    self.assertTrue(port_num in network.nodes[node].ports)
                    port = network.nodes[node].ports[port_num]
                    expected_cost += port.cost
                    node = port.target_node
                self.assertEqual(node, target)
                self.assertEqual(expected_cost, cost)

    def test_finding_shorter_path(self):
        store = RouteStore(0, Mock(), MagicMock())
        store.nodes[0] = _Node()
        store.nodes[0].edges[1] = _Edge()
        store.nodes[0].edges[1].insert_path([1, 2], 10)
        store.nodes[1] = _Node()

        store.insert(
            target=1,
            route=[1],
            cost=3,
        )

        self.assertTrue(1 in store.nodes[0].edges)
        self.assertTrue(len(store.nodes[0].edges[1].priced_routes) != 0)
        self.assertIsNotNone(store.nodes[1].predecessor)


if __name__ == '__main__':
    unittest.main()
