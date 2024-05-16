import random
import typing
import unittest
from unittest.mock import Mock, MagicMock

from routing_experiment import setup
from routing_experiment.net import Network, NodeId, Cost
from routing_experiment.route_storage import _Edge, _Node, RouteStore, PricedRoute
from routing_experiment.routing import Route
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
        store = RouteStore(1, MagicMock(), Mock(), True, True)
        self.assertEqual([], store.shortest_route(1).path)  # add assertion here

    def test_insertion(self):
        store = RouteStore(1, MagicMock(), Mock(), True, True)
        route = [1, 2, 3, 4]
        store.insert(2, route, 4)
        self.assertEqual(route, store.shortest_route(2).path)

    def test_combined_routes(self):
        store = RouteStore(1, MagicMock(), Mock(), True, True)
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
                cost_generator=setup.cost_generator_uniform,
            )
            source = int(rnd.random() * len(network.nodes))
            store = RouteStore(source, MagicMock(), Mock(), True, True)
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
        # This test reproduces a bug that occurred when inserting a route r to target x when the store already
        # contains a route r2 to target x that is prefixed by r.

        store = RouteStore(0, MagicMock(), Mock(), True, True)
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

    def test_insert_existing_route(self):
        store = RouteStore(0, MagicMock(), Mock(), True, True)
        store.insert(1, [1], 1)
        store.insert(1, [1], 1)

        self.assertEqual(2, len(store.nodes))
        self.assertEqual(1, len(store.nodes[0].edges))
        self.assertEqual(1, len(store.nodes[0].edges[1].priced_routes))
        self.assertEqual([1], store.nodes[0].edges[1].priced_routes[0].path)
        self.assertEqual(1, store.nodes[0].edges[1].priced_routes[0].cost)
        self.assertEqual(0, len(store.nodes[1].edges))

    def test_insert_existing_two_hop_route(self):
        store = RouteStore(0, MagicMock(), Mock(), True, True)
        store.insert(1, [1], 1)
        store.insert(2, [1, 2], 3)
        store.insert(2, [1, 2], 3)

        self.assertEqual(3, len(store.nodes))
        self.assertEqual(1, len(store.nodes[0].edges))
        self.assertEqual(1, len(store.nodes[0].edges[1].priced_routes))
        self.assertEqual([1], store.nodes[0].edges[1].priced_routes[0].path)
        self.assertEqual(1, store.nodes[0].edges[1].priced_routes[0].cost)
        self.assertEqual(1, len(store.nodes[1].edges))
        self.assertEqual(1, len(store.nodes[1].edges[2].priced_routes))
        self.assertEqual([2], store.nodes[1].edges[2].priced_routes[0].path)
        self.assertEqual(2, store.nodes[1].edges[2].priced_routes[0].cost)
        self.assertEqual(0, len(store.nodes[2].edges))

    def test_insert_redirect(self):
        store = RouteStore(0, MagicMock(), Mock(), True, True)
        store.nodes[0].edges[2] = _Edge()
        store.nodes[0].edges[2].priced_routes = [
            PricedRoute(path=[1, 2], cost=3),
            PricedRoute(path=[1, 3], cost=4),
        ]
        store.nodes[2] = _Node()

        store.insert(target=1, route=[1], cost=1)

        self.assertEqual(3, len(store.nodes))
        self.assertEqual(1, len(store.nodes[0].edges))
        self.assertEqual(1, len(store.nodes[0].edges[1].priced_routes))
        self.assertEqual([1], store.nodes[0].edges[1].priced_routes[0].path)
        self.assertEqual(1, store.nodes[0].edges[1].priced_routes[0].cost)
        self.assertEqual(1, len(store.nodes[1].edges))
        self.assertEqual(2, len(store.nodes[1].edges[2].priced_routes))
        self.assertEqual([2], store.nodes[1].edges[2].priced_routes[0].path)
        self.assertEqual(2, store.nodes[1].edges[2].priced_routes[0].cost)
        self.assertEqual([3], store.nodes[1].edges[2].priced_routes[1].path)
        self.assertEqual(3, store.nodes[1].edges[2].priced_routes[1].cost)
        self.assertEqual(0, len(store.nodes[2].edges))


if __name__ == '__main__':
    unittest.main()
