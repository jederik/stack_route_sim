import instrumentation


class MetricsCalculator:
    def __init__(self, tracker: instrumentation.Tracker):
        self.scraped_measurements: set[str] = set()
        self.tracker = tracker
        self._last_measurement: dict[str, float] = {}

    def calculate_metric(self, metric_name: str):
        raise Exception("not implemented")

    def reset(self) -> None:
        for measurement in self.scraped_measurements:
            self._reset_measurement(measurement)
        self.scraped_measurements = set()

    def _reset_measurement(self, name):
        self._last_measurement[name] = self.tracker.get_counter_value(name)

    def scrape(self, metrics) -> dict[str, float]:
        result = {
            metric_name: self.calculate_metric(metric_name)
            for metric_name in metrics
        }
        self.reset()
        return result

    def rate(self, sum_metric: str, count_metric: str) -> float:
        sum_delta = self._get_measurement_delta(sum_metric)
        count_delta = self._get_measurement_delta(count_metric)
        if count_delta == 0:
            return 0
        return sum_delta / count_delta

    def _get_measurement_delta(self, name) -> float:
        old_value = float(0)
        if name in self._last_measurement:
            old_value = self._last_measurement[name]
        new_value = self._get_measurement(name)
        return new_value - old_value

    def _get_measurement(self, name):
        self.scraped_measurements.add(name)
        return self.tracker.get_counter_value(name)
