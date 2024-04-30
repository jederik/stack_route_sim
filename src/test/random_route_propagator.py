import unittest
from unittest.mock import Mock

import instrumentation
from strategies.optimised import RandomRoutePropagator, RouteStore, _Node, _Edge, PricedRoute


class MyTestCase(unittest.TestCase):
    def test_pick(self):
        # case
        case = {
            "given": {
                "my_id": 0,
                "nodes": {
                    0: {
                        "edges": {
                            1: {
                                "segments": [
                                    {
                                        "path": [1, 2, 3, 4],
                                        "cost": 3,
                                    },
                                ],
                            }
                        },
                    },
                },
                "cutoff_rate": .1,
                "rnd": [0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0],
            },
            "then": {
                "target": 1,
                "route": [1, 2, 3, 4],
                "cost": 3,
            }
        }
        rnd = Mock()
        rnd.random = Mock(side_effect=case["given"]["rnd"])

        # mock
        propagator = RandomRoutePropagator(
            cutoff_rate=case["given"]["cutoff_rate"],
            rnd=rnd,
        )
        store = RouteStore(case["given"]["my_id"], rnd, Mock())
        for node_id, given_node in case["given"]["nodes"].items():
            store.nodes[node_id] = _Node()
            for edge_target, given_edge in given_node["edges"].items():
                store.nodes[node_id].edges[edge_target] = _Edge()
                for given_segment in given_edge["segments"]:
                    store.nodes[node_id].edges[edge_target].priced_routes.append(
                        PricedRoute(path=given_segment["path"], cost=given_segment["cost"]),
                    )
        store.nodes[1] = _Node()
        router = Mock()
        router.adapter.ports.side_effect = [
            [1],
        ]
        router.store = store

        # call
        _, target, route, cost = propagator.pick(router)

        # assert
        self.assertEqual(case["then"]["route"], route)
        self.assertEqual(case["then"]["target"], target)
        self.assertEqual(case["then"]["cost"], cost)


if __name__ == '__main__':
    unittest.main()
