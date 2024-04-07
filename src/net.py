from collections import defaultdict
from typing import Optional


class Adapter:
    class Handler:
        def handle(self):
            raise Exception("not implemented")

    def send(self, port_num: int):
        raise Exception("not implemented")

    def ports(self) -> list[int]:
        raise Exception("not implemented")

    def register_handler(self, handler: Handler):
        raise Exception("not implemented")


class Transmission:
    def __init__(self, recipient_node_id: int):
        self.recipient_node_id = recipient_node_id


class Network:
    class Node:
        class Port:
            def __init__(self, target_node: int):
                self.target_node = target_node

        def __init__(self):
            self.handler = None
            self.next_port_num: int = 0
            self.ports: dict[int, Network.Node.Port] = {}

    class AdapterImpl(Adapter):
        def __init__(self, network: 'Network', node_id: int):
            self.handler: Optional[Adapter.Handler] = None
            self.network = network
            self.node_id = node_id

        def send(self, port_num: int):
            self.network._send(self.node_id, port_num)

        def ports(self) -> list[int]:
            return list(self.network.nodes[self.node_id].ports.keys())

        def register_handler(self, handler: Adapter.Handler):
            self.handler = handler

    def __init__(self, node_count: int):
        self._transmission_queue: list[Transmission] = []
        self.counters: dict[str, int] = defaultdict(lambda: 0)
        self.nodes = [
            Network.Node()
            for _ in range(node_count)
        ]
        self.adapters = [
            self.AdapterImpl(self, node)
            for node in range(node_count)
        ]

    def connect(self, node1: int, node2: int):
        n1 = self.nodes[node1]
        n2 = self.nodes[node2]
        pn1 = n1.next_port_num
        pn2 = n2.next_port_num
        n1.ports[pn1] = Network.Node.Port(node2)
        n2.ports[pn2] = Network.Node.Port(node1)
        n1.next_port_num += 1
        n2.next_port_num += 1

    def _send(self, sender_node_id: int, sender_port_num: int):
        node = self.nodes[sender_node_id]
        transmission = Transmission(
            recipient_node_id=node.ports[sender_port_num].target_node
        )
        self._transmission_queue.append(transmission)
        self._process_queue()

    def _process_queue(self):
        while len(self._transmission_queue) != 0:
            transmission = self._transmission_queue.pop()
            adapter = self.adapters[transmission.recipient_node_id]
            if adapter.handler is None:
                self._increase_counter({"name": "transmission_count", "success": "false"})
                raise Exception("no handler registered")
            else:
                adapter.handler.handle()
                self._increase_counter({"name": "transmission_count", "success": "true"})

    def _increase_counter(self, labels: dict[str, str]):
        self.counters[str(labels)] += 1

    def get_counter(self, labels: dict[str, str]):
        return self.counters[str(labels)]
