import instrumentation
import net
from net import NodeId
from routing import Router


class RouterFactory:
    def create_router(self, adapter: net.Adapter, node_id: NodeId, tracker: instrumentation.Tracker) -> Router:
        raise Exception("not implemented")
