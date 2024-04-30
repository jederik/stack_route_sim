import tempfile

from .metering import MetricName, MetricValue
from . import figures


class Candidate:
    def run_step(self):
        raise Exception("not implemented")

    def scrape_metrics(self, metrics: list[MetricName]) -> dict[MetricName, MetricValue]:
        raise Exception("not implemented")


class Experiment:
    def __init__(self, candidates: dict[str, Candidate]):
        self.candidates = candidates


class ExperimentRunner:
    def __init__(
            self,
            config,
            experiment: Experiment,
            figure_folder: str,
    ):
        self.experiment = experiment
        self.figure_maker = figures.FigureMaker(
            config=config["figures"],
            candidates=config["candidates"].keys(),
            data_file_location=tempfile.mktemp(),
            target_folder=figure_folder,
        )
        self.metrics = self.figure_maker.required_metrics()
        self.emit_sample = self.figure_maker.add_sample
        self.steps: int = config["measurement"]["steps"]
        samples = config["measurement"]["samples"]
        self.scrape_interval: int = self.steps // samples

    def run(self):
        for step in range(self.steps):
            if step % self.scrape_interval == 0:
                sample = self.scrape()
                self.emit_sample(sample)
            self.run_step()
        sample = self.scrape()
        self.emit_sample(sample)
        self.figure_maker.make_figures()

    def run_step(self):
        for _, candidate in self.experiment.candidates.items():
            candidate.run_step()

    def scrape(self):
        return {
            "candidates": {
                name: candidate.scrape_metrics(self.metrics)
                for name, candidate in self.experiment.candidates.items()
            },
        }
