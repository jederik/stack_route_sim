import copy
from typing import Optional

import instrumentation
from . import measurements

NodeId = int
PortNumber = int
Cost = float


class Adapter:
    class Handler:
        def handle(self, port_num: PortNumber, message) -> None:
            raise Exception("not implemented")

        def on_disconnected(self, port_num: PortNumber) -> None:
            pass

    def send(self, port_num: PortNumber, message) -> None:
        raise Exception("not implemented")

    def ports(self) -> list[PortNumber]:
        raise Exception("not implemented")

    def register_handler(self, handler: Handler) -> None:
        raise Exception("not implemented")

    def port_cost(self, port_num) -> Cost:
        raise Exception("not implemented")


class Transmission:
    def __init__(self, recipient_node_id: int, port_num: int, message):
        self.port_num = port_num
        self.message = message
        self.recipient_node_id = recipient_node_id


class Measurements:
    def __init__(self, tracker: instrumentation.Tracker):
        self.transmission_count = tracker.get_counter(measurements.TRANSMISSION_COUNT)


class Network:
    class Node:
        class Port:
            def __init__(self, target_node: int, target_port_num: int, cost: Cost):
                self.target_port_num: int = target_port_num
                self.target_node: int = target_node
                self.cost = cost

        def __init__(self):
            self.handler = None
            self.next_port_num: int = 0
            self.ports: dict[PortNumber, Network.Node.Port] = {}

    class AdapterImpl(Adapter):
        def __init__(self, network: 'Network', node_id: NodeId):
            self.handler: Optional[Adapter.Handler] = None
            self.network = network
            self.node_id = node_id

        def send(self, port_num: int, message):
            self.network._send(self.node_id, port_num, message)

        def ports(self) -> list[int]:
            return list(self.network.nodes[self.node_id].ports.keys())

        def register_handler(self, handler: Adapter.Handler):
            self.handler = handler

        def port_cost(self, port_num) -> Cost:
            return self.network.nodes[self.node_id].ports[port_num].cost

    def __init__(self, node_count: int, tracker: instrumentation.Tracker):
        self.measurements = Measurements(tracker)
        self._transmission_queue: list[Transmission] = []
        self.nodes = [
            Network.Node()
            for _ in range(node_count)
        ]
        self.adapters = [
            self.AdapterImpl(self, node)
            for node in range(node_count)
        ]

    def connect(self, node1: int, node2: int, forward_cost: Cost, backward_cost: Cost):
        n1 = self.nodes[node1]
        n2 = self.nodes[node2]
        pn1 = n1.next_port_num
        pn2 = n2.next_port_num
        n1.ports[pn1] = Network.Node.Port(node2, pn2, forward_cost)
        n2.ports[pn2] = Network.Node.Port(node1, pn1, backward_cost)
        n1.next_port_num += 1
        n2.next_port_num += 1

    def disconnect(self, node_id: NodeId, port_num: PortNumber) -> None:
        other_node_id = self.nodes[node_id].ports[port_num].target_node
        reverse_port_num = self.nodes[node_id].ports[port_num].target_port_num
        del self.nodes[other_node_id].ports[reverse_port_num]
        del self.nodes[node_id].ports[port_num]
        self.adapters[node_id].handler.on_disconnected(port_num)
        self.adapters[other_node_id].handler.on_disconnected(reverse_port_num)

    def _send(self, sender_node_id: int, sender_port_num: int, message):
        node = self.nodes[sender_node_id]
        port = node.ports[sender_port_num]
        transmission = Transmission(
            recipient_node_id=port.target_node,
            port_num=port.target_port_num,
            message=copy.deepcopy(message),
        )
        self._transmission_queue.append(transmission)
        self._process_queue()

    def _process_queue(self):
        while len(self._transmission_queue) != 0:
            transmission = self._transmission_queue.pop(0)
            adapter = self.adapters[transmission.recipient_node_id]
            if adapter.handler is None:
                raise Exception("no handler registered")
            else:
                self.measurements.transmission_count.increase(1)
                adapter.handler.handle(transmission.port_num, transmission.message)
