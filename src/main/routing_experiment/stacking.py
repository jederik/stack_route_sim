import random
from typing import Optional

from overrides import override

from routing_experiment import net
from routing_experiment.net import PortNumber

from routing_experiment.routing import Route


class Datagram:
    def __init__(self, payload, origin: Optional[Route] = None, destination: Optional[Route] = None):
        self.payload = payload
        self.origin = origin
        self.destination = destination


class Endpoint:
    def receive_unicast(self, datagram: Datagram):
        raise Exception("not implemented")

    def receive_broadcast(self, datagram: Datagram):
        raise Exception("not implemented")


class StackEngine(net.Adapter.Handler):
    def __init__(self, adapter: net.Adapter, broadcasting_forwarding_rate: float, rnd: random.Random, broadcasting_auto_forward: bool):
        self.rnd = rnd
        self.adapter = adapter
        self.endpoint: Optional[Endpoint] = None
        self.broadcasting_forwarding_rate = broadcasting_forwarding_rate
        self.broadcasting_auto_forward = broadcasting_auto_forward

    @override
    def handle(self, port_num: PortNumber, message) -> None:
        datagram: Datagram = message
        if datagram.origin is not None:
            datagram.origin = [port_num] + datagram.origin
        if datagram.destination is not None:
            # unicast
            if len(datagram.destination) == 0:
                self.endpoint.receive_unicast(datagram)
            else:
                self.send_datagram(datagram)
        else:
            # broadcast
            self.endpoint.receive_broadcast(datagram)
            if self.broadcasting_auto_forward:
                self.send_datagram(datagram)

    def send_datagram(self, datagram: Datagram):
        if datagram.destination is not None:
            # unicast
            port_num = datagram.destination.pop(0)
            self.adapter.send(port_num, datagram)
        else:
            # broadcast
            if self.broadcasting_forwarding_rate > self.rnd.random():
                port_num = self.rnd.choice(self.adapter.ports())
                self.adapter.send(port_num, datagram)
