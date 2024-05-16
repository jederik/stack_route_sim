import unittest
from unittest.mock import Mock

from routing_experiment import stacking


class MyTestCase(unittest.TestCase):
    def test_receive_broadcast(self):
        endpoint = Mock()
        endpoint.receive_broadcast = Mock()
        engine = stacking.StackEngine(
            adapter=Mock(),
            rnd=Mock(),
            broadcasting_forwarding_rate=1.0,
            random_walk_broadcasting=True,
        )
        engine.endpoint = endpoint
        engine.handle(
            port_num=1,
            message=stacking.Datagram(
                payload="blabla",
                origin=[2, 3],
            ),
        )
        endpoint.receive_datagram.assert_called()
        self.assertEqual("blabla", endpoint.receive_datagram.call_args[0][0].payload)
        self.assertEqual([1, 2, 3], endpoint.receive_datagram.call_args[0][0].origin)
        self.assertIsNone(endpoint.receive_datagram.call_args[0][0].destination)

    def test_send_broadcast(self):
        adapter = Mock()
        adapter.ports = Mock(
            return_value=[1, 2, 3],
        )
        adapter.send = Mock()
        rnd = Mock()
        rnd.random = Mock(return_value=0.5)
        rnd.choice = Mock(
            return_value=3,
        )
        engine = stacking.StackEngine(
            adapter=adapter,
            rnd=rnd,
            broadcasting_forwarding_rate=1.0,
            random_walk_broadcasting=True,
        )
        engine.send_datagram(
            datagram=stacking.Datagram(
                payload="blabla",
                origin=[],
            ),
        )
        adapter.send.assert_called()
        self.assertEqual(3, adapter.send.call_args[0][0])
        self.assertEqual("blabla", adapter.send.call_args[0][1].payload)
        self.assertEqual([], adapter.send.call_args[0][1].origin)
        self.assertIsNone(adapter.send.call_args[0][1].destination)

    def test_receive_unicast(self):
        endpoint = Mock()
        endpoint.receive_unicast = Mock()
        adapter = Mock()
        adapter.send_datagram = Mock()
        engine = stacking.StackEngine(
            adapter=adapter,
            rnd=Mock(),
            broadcasting_forwarding_rate=1.0,
            random_walk_broadcasting=True,
        )
        engine.endpoint = endpoint
        engine.handle(
            port_num=1,
            message=stacking.Datagram(
                payload="blabla",
                origin=[2, 3],
                destination=[],
            ),
        )
        endpoint.receive_datagram.assert_called()
        self.assertEqual("blabla", endpoint.receive_datagram.call_args[0][0].payload)
        self.assertEqual([1, 2, 3], endpoint.receive_datagram.call_args[0][0].origin)
        self.assertEqual([], endpoint.receive_datagram.call_args[0][0].destination)

    def test_forward_unicast(self):
        adapter = Mock()
        adapter.send = Mock()
        engine = stacking.StackEngine(
            adapter=adapter,
            rnd=Mock(),
            broadcasting_forwarding_rate=1.0,
            random_walk_broadcasting=True,
        )
        engine.endpoint = Mock()
        engine.handle(
            port_num=1,
            message=stacking.Datagram(
                payload="blabla",
                origin=[2, 3],
                destination=[5, 6, 7],
            ),
        )
        adapter.send.assert_called()
        send_call_args = adapter.send.call_args_list[0][1]
        self.assertEqual(5, send_call_args["port_num"])
        self.assertEqual("blabla", send_call_args["message"].payload)
        self.assertEqual([1, 2, 3], send_call_args["message"].origin)
        self.assertEqual([6, 7], send_call_args["message"].destination)

    def test_send_unicast(self):
        adapter = Mock()
        adapter.ports = Mock(
            return_value=[1, 2, 3],
        )
        adapter.send = Mock()
        rnd = Mock()
        engine = stacking.StackEngine(
            adapter=adapter,
            rnd=rnd,
            broadcasting_forwarding_rate=1.0,
            random_walk_broadcasting=True,
        )
        engine.send_datagram(
            datagram=stacking.Datagram(
                payload="blabla",
                origin=[],
                destination=[1, 2, 3],
            ),
        )
        adapter.send.assert_called()
        send_call_args = adapter.send.call_args_list[0][1]
        self.assertEqual(1, send_call_args["port_num"])
        self.assertEqual("blabla", send_call_args["message"].payload)
        self.assertEqual([], send_call_args["message"].origin)
        self.assertEqual([2, 3], send_call_args["message"].destination)


if __name__ == '__main__':
    unittest.main()
