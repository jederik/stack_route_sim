from routes import Route, NodeId


class Router:
    def tick(self):
        raise Exception("not implemented")

    def has_route(self, target: NodeId) -> bool:
        raise Exception("not implemented")

    def shortest_route(self, target: NodeId) -> Route:
        raise Exception("not implemented")
