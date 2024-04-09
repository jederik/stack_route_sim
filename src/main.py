import os
import click
import json
import yaml
import sys

from src import measure


def dump_sample(sample):
    json.dump(sample, fp=sys.stdout, indent=2)
    print()


def read_config(path):
    with open(path, 'r') as file:
        return yaml.safe_load(file)


@click.command()
@click.option(
    "--config",
    default=os.getenv("CONFIG", "~/config.yaml"),
    help="location of the experiment config YAML"
)
def run(config: str):
    experiment = measure.Experiment(
        config=read_config(config),
        sample_emitter=dump_sample,
    )
    experiment.run()


if __name__ == '__main__':
    run()
