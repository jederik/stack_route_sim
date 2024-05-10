import unittest
from unittest.mock import Mock

from routing_experiment import route_storage, stacking
from routing_experiment.strategies import stacked


# noinspection PyMethodMayBeStatic
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
            auto_forward_propagations=False,
            message_handlers={},
        ).tick()
        tick_task_1.execute.assert_called()
        tick_task_2.execute.assert_called()

    def test_broadcast_handling(self):
        handler = Mock()
        handler.handle = Mock()
        stacked.ExtendableRouter(
            stack_engine=Mock(),
            scheduled_tasks=[],
            demand_map={},
            store=Mock(),
            auto_forward_propagations=False,
            message_handlers={
                str: handler,
            },
        ).receive_broadcast(
            datagram=stacking.Datagram(
                payload="blabla",
                origin=[1, 2, 3],
            ),
        )
        handler.handle.assert_called()
        self.assertEqual("blabla", handler.handle.call_args[0][0].payload)
        self.assertEqual([1, 2, 3], handler.handle.call_args[0][0].origin)
        self.assertIsNone(handler.handle.call_args[0][0].destination)

    def test_unicast_handling(self):
        handler = Mock()
        handler.handle = Mock()
        stacked.ExtendableRouter(
            stack_engine=Mock(),
            scheduled_tasks=[],
            demand_map={},
            store=Mock(),
            auto_forward_propagations=False,
            message_handlers={
                str: handler,
            },
        ).receive_broadcast(
            datagram=stacking.Datagram(
                payload="blabla",
                origin=[1, 2, 3],
                destination=[4, 5, 6]
            ),
        )
        handler.handle.assert_called()
        self.assertEqual("blabla", handler.handle.call_args[0][0].payload)
        self.assertEqual([1, 2, 3], handler.handle.call_args[0][0].origin)
        self.assertEqual([4, 5, 6], handler.handle.call_args[0][0].destination)


if __name__ == '__main__':
    unittest.main()
