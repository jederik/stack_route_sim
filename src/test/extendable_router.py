import unittest
from unittest.mock import Mock

from routing_experiment import route_storage, stacking
from routing_experiment.strategies import stacked


class MyTestCase(unittest.TestCase):
    def test_scheduled_tasks(self):
        tick_task_1 = Mock()
        tick_task_2 = Mock()
        stacked.ExtendableRouter(
            stack_engine=Mock(),
            scheduled_tasks=[
                tick_task_1,
                tick_task_2,
            ],
            demand_map={},
            store=Mock(),
        ).tick()
        tick_task_1.execute.assert_called()
        tick_task_2.execute.assert_called()

    def test_route_retrieval(self):
        store = Mock()
        store.shortest_route = Mock(
            return_value=route_storage.PricedRoute(
                path=[1, 2, 3],
                cost=13,
            ),
        )
        route = stacked.ExtendableRouter(
            stack_engine=Mock(),
            scheduled_tasks=[],
            demand_map={},
            store=store,
        ).route(1)
        self.assertEqual([1, 2, 3], route)

    def test_receive_route_propagation_message(self):
        store = Mock()
        store.insert = Mock()
        stacked.ExtendableRouter(
            stack_engine=Mock(),
            scheduled_tasks=[],
            demand_map={},
            store=store,
        ).receive_broadcast(
            datagram=stacking.Datagram(
                payload=stacked.RoutePropagationMessage(
                    target=1,
                    cost=3,
                ),
                origin=[1, 2, 3],
            ),
        )
        store.insert.assert_called_with(
            target=1,
            route=[1, 2, 3],
            cost=3,
        )


if __name__ == '__main__':
    unittest.main()
