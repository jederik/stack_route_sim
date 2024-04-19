import unittest

from strategies.optimised import RouteStore


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


if __name__ == '__main__':
    unittest.main()
