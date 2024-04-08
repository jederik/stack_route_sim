class Router:
    def tick(self):
        raise Exception("not implemented")

    def has_route(self, target) -> bool:
        raise Exception("not implemented")

    def shortest_route(self, target) -> list[int]:
        raise Exception("not implemented")
