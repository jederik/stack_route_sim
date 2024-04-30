class Counter:
    def __init__(self):
        self.value: float = 0

    def increase(self, amount):
        self.value += amount


class Tracker:
    def __init__(self):
        self.counters: dict[str, Counter] = {}

    def get_counter(self, name: str) -> Counter:
        if name not in self.counters:
            self.counters[name] = Counter()
        return self.counters[name]

    def get_counter_value(self, name):
        return self.counters[name].value
