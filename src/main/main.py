import os
import tempfile

import click
import yaml

import experiments
import figures


def read_config(path):
    with open(path, 'r') as file:
        return yaml.safe_load(file)


@click.command()
@click.option(
    "--config",
    default=os.getenv("CONFIG", "./config.yaml"),
    help="location of the experiment config YAML",
)
def run(config: str):
    main_config = read_config(config)
    figure_maker = figures.FigureMaker(
        config=main_config["figures"],
        candidates=main_config["candidates"].keys(),
        data_file_location=tempfile.mktemp(),
    )
    required_metrics = figure_maker.required_metrics()
    experiment = experiments.Experiment(
        config=main_config,
        sample_emitter=figure_maker.add_sample,
        metrics=required_metrics,
    )
    experiment.run()
    figure_maker.make_figures()


if __name__ == '__main__':
    run()
