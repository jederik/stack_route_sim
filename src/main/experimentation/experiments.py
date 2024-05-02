import copy
import random
import tempfile
from typing import Callable

import experimentation

from .metering import MetricName, MetricValue
from . import plotting


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
        self.figure_maker = plotting.FigureMaker(
            config=config["plotting"],
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


def apply_patch(original: dict, patch: dict) -> dict:
    result = copy.deepcopy(original)
    for key in patch.keys():
        if key in original and isinstance(original[key], dict):
            result[key] = apply_patch(original[key], patch[key])
        else:
            result[key] = patch[key]
    return result


def _create_experiment(
        candidate_creator_function: Callable[[dict, random.Random], Candidate],
        rnd: random.Random,
        candidate_configs: dict[str, dict],
) -> Experiment:
    return Experiment(
        candidates={
            candidate_name: candidate_creator_function(candidate_config, rnd)
            for candidate_name, candidate_config in candidate_configs.items()
        },
    )


def init_experiment_runner(
        config: dict[str],
        rnd: random.Random,
        figure_folder: str,
        candidate_creator_function: Callable[[dict, random.Random], Candidate],
):
    default_candidate_config = config["default_candidate_config"]
    candidate_configs = {
        candidate_name: apply_patch(default_candidate_config, candidate_config_patch)
        for candidate_name, candidate_config_patch in config["candidates"].items()
    }
    experiment_runner = experimentation.ExperimentRunner(
        config=config,
        experiment=_create_experiment(candidate_creator_function, rnd, candidate_configs),
        figure_folder=figure_folder,
    )
    return experiment_runner
