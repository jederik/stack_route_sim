import time


class Counter:
    def __init__(self):
        self.value: float = 0

    def increase(self, amount):
        self.value += amount


class Timer(Counter):
    def __enter__(self):
        self.start = time.time()

    def __exit__(self, exc_type, exc_val, exc_tb):
        end = time.time()
        self.increase(end - self.start)


class Tracker:
    def get_counter(self, name: str) -> Counter:
        raise Exception("not implemented")

    def get_timer(self, name) -> Timer:
        raise Exception("not implemented")


class MeasurementReader:
    def get_counter_value(self, name):
        raise Exception("not implemented")


class _Implementation(Tracker, MeasurementReader):
    def __init__(self):
        self.measurements: dict[str, Counter] = {}

    def get_counter(self, name: str) -> Counter:
        if name not in self.measurements:
            self.measurements[name] = Counter()
        return self.measurements[name]

    def get_counter_value(self, name):
        return self.measurements[name].value

    def get_timer(self, name) -> Timer:
        if name not in self.measurements:
            self.measurements[name] = Timer()
        counter = self.measurements[name]
        if isinstance(counter, Timer):
            timer: Timer = counter
            return timer
        raise Exception(f"there is already a non-timer counter registered under {name}")


def setup() -> tuple[Tracker, MeasurementReader]:
    instance = _Implementation()
    return instance, instance
