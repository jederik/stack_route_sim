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
    def receive_datagram(self, datagram: Datagram):
        raise Exception("not implemented")

    def on_port_disconnected(self, port_num: net.PortNumber):
        pass


class StackEngine(net.Adapter.Handler):
    def __init__(
            self,
            adapter: net.Adapter,
            broadcasting_forwarding_rate: float,
            rnd: random.Random,
            random_walk_broadcasting: bool,
    ):
        self.random_walk_broadcasting = random_walk_broadcasting
        self.rnd = rnd
        self.adapter = adapter
        self.endpoint: Optional[Endpoint] = None
        self.broadcasting_forwarding_rate = broadcasting_forwarding_rate

    @override
    def handle(self, port_num: PortNumber, message) -> None:
        datagram: Datagram = message
        if datagram.origin is not None:
            datagram.origin = [port_num] + datagram.origin
        if datagram.destination is not None:
            # unicast
            if len(datagram.destination) == 0:
                self.endpoint.receive_datagram(datagram)
            else:
                self.send_datagram(datagram)
        else:
            # broadcast
            self.endpoint.receive_datagram(datagram)

    def on_disconnected(self, port_num: PortNumber) -> None:
        if self.endpoint:
            self.endpoint.on_port_disconnected(port_num)

    def send_datagram(self, datagram: Datagram):
        if datagram.destination is not None:
            # unicast
            port_num = datagram.destination[0]
            self.adapter.send(
                port_num=port_num,
                message=Datagram(
                    payload=datagram.payload,
                    origin=datagram.origin,
                    destination=datagram.destination[1:],
                ),
            )
        else:
            # broadcast
            if self.random_walk_broadcasting:
                if self.broadcasting_forwarding_rate > self.rnd.random():
                    port_num = self.rnd.choice(self.adapter.ports())
                    self.adapter.send(port_num, datagram)
            else:
                ports = self.adapter.ports()
                if any(ports):
                    prob = self.broadcasting_forwarding_rate / len(ports)
                    for port in ports:
                        if prob > self.rnd.random():
                            self.adapter.send(port, datagram)

    def send_full_broadcast(self, datagram: Datagram):
        for port in self.adapter.ports():
            self.adapter.send(port, datagram)
