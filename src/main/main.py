import os
import random
from datetime import datetime

import click
import yaml

import experiments
import routing_experiment


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
    run_experiment(main_config, target)


def run_experiment(config, target):
    rnd = random.Random()
    experiment = experiments.ExperimentRunner(
        config=config,
        experiment=routing_experiment.create_experiment(rnd, config),
        figure_folder=target,
    )
    experiment.run()


if __name__ == '__main__':
    run()
