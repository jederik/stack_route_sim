from typing import Optional

import instrumentation
from . import net

from .net import NodeId, PortNumber

Route = list[PortNumber]


class Router:
    def tick(self) -> None:
        raise Exception("not implemented")

    def has_route(self, target: NodeId) -> bool:
        raise Exception("not implemented")

    def route(self, target: NodeId) -> Optional[Route]:
        raise Exception("not implemented")

    def handler(self) -> net.Adapter.Handler:
        raise Exception("not implemented")

    def demand(self, target) -> float:
        raise Exception("not implemented")


class RouterFactory:
    def create_router(
            self,
            adapter: net.Adapter,
            node_id: NodeId,
            tracker: instrumentation.Tracker,
    ) -> Router:
        raise Exception("not implemented")
