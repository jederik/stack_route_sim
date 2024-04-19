import net
from routes import NodeId
from routing import Router


class RoutingStrategy:
    def build_router(self, adapter: net.Adapter, node_id: NodeId) -> Router:
        raise Exception("not implemented")
