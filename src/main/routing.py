from typing import Optional

from net import NodeId, PortNumber

Route = list[PortNumber]


class Router:
    def tick(self) -> None:
        raise Exception("not implemented")

    def has_route(self, target: NodeId) -> bool:
        raise Exception("not implemented")

    def route(self, target: NodeId) -> Optional[Route]:
        raise Exception("not implemented")
