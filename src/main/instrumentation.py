import copy
import time
from collections import defaultdict


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
    def __init__(self, counters: dict[str, Counter]):
        self.counters = counters

    def get_counter(self, name: str) -> Counter:
        if name not in self.counters:
            self.counters[name] = Counter()
        return self.counters[name]

    def get_timer(self, name) -> Timer:
        if name not in self.counters:
            self.counters[name] = Timer()
        counter = self.counters[name]
        if isinstance(counter, Timer):
            timer: Timer = counter
            return timer
        raise Exception(f"there is already a non-timer counter registered under {name}")


class Session:
    def __init__(self, before: dict[str, float], after: dict[str, float]):
        self.before = before
        self.after = after

    def get_counter_value(self, name):
        raise Exception("not implemented")

    def get(self, name) -> float:
        return self.after[name]

    def rate(self, sum_metric: str, count_metric: str) -> float:
        sum_delta = self._get_measurement_delta(sum_metric)
        count_delta = self._get_measurement_delta(count_metric)
        if count_delta == 0:
            return 0
        return sum_delta / count_delta

    def _get_measurement_delta(self, name: str) -> float:
        try:
            return self.after[name] - self.before[name]
        except KeyError as e:
            raise Exception(f"metric {name} not available")


class MeasurementReader:
    def __init__(self, counters: dict[str, Counter]):
        self.counters = counters
        self.before: dict[str, float] = defaultdict(lambda: float(0))

    def session(self) -> Session:
        current = {
            name: counter.value
            for name, counter in self.counters.items()
        }
        before = copy.copy(self.before)
        self.before = current
        return Session(before, current)


def setup() -> tuple[Tracker, MeasurementReader]:
    counters: dict[str, Counter] = {}
    return Tracker(counters), MeasurementReader(counters)
