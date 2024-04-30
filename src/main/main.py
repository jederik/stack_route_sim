import os
import tempfile
from datetime import datetime

import click
import yaml

import experiments
import figures
import instrumentation


def read_config(path):
    with open(path, 'r') as file:
        return yaml.safe_load(file)


@click.command()
@click.option(
    "--config",
    default=os.getenv("CONFIG", "./config.yaml"),
    help="location of the experiment config YAML",
)
@click.option(
    "--target",
    default=os.getenv("TARGET", f"./results/{datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}"),
    help="directory in which figures should be stored",
)
def run(config: str, target: str):
    main_config = read_config(config)
    figure_maker = figures.FigureMaker(
        config=main_config["figures"],
        candidates=main_config["candidates"].keys(),
        data_file_location=tempfile.mktemp(),
        target_folder=target,
    )
    required_metrics = figure_maker.required_metrics()
    experiment = experiments.Experiment(
        config=main_config,
        sample_emitter=figure_maker.add_sample,
        metrics=required_metrics,
        tracker_factory_method=instrumentation.Tracker,
    )
    experiment.run()
    figure_maker.make_figures()


if __name__ == '__main__':
    run()
