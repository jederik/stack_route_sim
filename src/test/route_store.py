import random
import typing
import unittest

from measure import generate_network
from net import Network
from routes import NodeId, Route, Cost
from strategies.optimised import RouteStore

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
        store = RouteStore(1)
        self.assertEqual([], store.shortest_route(1).path)  # add assertion here

    def test_insertion(self):
        store = RouteStore(1)
        route = [1, 2, 3, 4]
        store.insert(2, route, 4)
        self.assertEqual(route, store.shortest_route(2).path)

    def test_combined_routes(self):
        store = RouteStore(1)
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
            )
            source = int(rnd.random() * len(network.nodes))
            store = RouteStore(source, rnd)
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

    def test_random_route_retrieval(self):
        for i in range(100):
            rnd = random.Random(i)
            network = generate_network(
                config={
                    "node_count": 20,
                    "density": .5,
                },
                rnd=rnd,
            )
            source = int(rnd.random() * len(network.nodes))
            store = RouteStore(source, rnd)
            for _ in range(10):
                target, route, cost = _random_walk(network, source, rnd)
                store.insert(target, route, cost)
            target, route, cost = store.get_random_route()

            node = source
            expected_cost = 0
            for port_num in route:
                self.assertTrue(port_num in network.nodes[node].ports)
                port = network.nodes[node].ports[port_num]
                expected_cost += port.cost
                node = port.target_node
            self.assertEqual(node, target)
            self.assertEqual(expected_cost, cost)


if __name__ == '__main__':
    unittest.main()
