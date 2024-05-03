import csv
import pathlib
import subprocess
import sys
from typing import Optional

_SCRIPT_TEMPLATE = """
set xlabel '{x_label}';
set ylabel '{y_label}';
plot {plots};
"""

_FILE_OUTPUT_TEMPLATE = """
set terminal png;
set output '{output_file}';
replot;
"""

_PLOT_TEMPLATE = """
'{data_file}' using {x_index}:{y_index} with lines title '{label}'
""".strip()


class Figure:
    def __init__(self, y_metric: str, y_label: str, title: str):
        self.title = title
        self.y_label = y_label
        self.y_metric = y_metric


def _create_figure(config) -> Figure:
    y_metric = config["metric"]
    y_label = config["label"] if "label" in config else y_metric
    title = config["title"] if "title" in config else y_label
    return Figure(
        y_metric=y_metric,
        y_label=y_label,
        title=title,
    )


def _gnuplot_escape(label: str) -> str:
    return label.replace("_", "\\_")


class Group:
    def __init__(self, figures: list[Figure], x_label: str, x_metric: str):
        self.x_label = x_label
        self.x_metric = x_metric
        self.figures = figures


def _create_group(config) -> Group:
    x_metric = config["x_metric"]
    x_label = config["x_label"] if "x_label" in config else x_metric
    figures = [
        _create_figure(figure_config)
        for figure_config in config["figures"]
    ]
    return Group(
        x_metric=x_metric,
        x_label=x_label,
        figures=figures,
    )


class FigureMaker:
    def __init__(self, config, candidates: list[str], data_file_location, target_folder: Optional[str]):
        self.target_folder = target_folder
        self.groups = [
            _create_group(group_config)
            for group_config in config["groups"]
        ]
        self.candidates = candidates
        self.data_file_location = data_file_location
        self.samples = []

    def add_sample(self, sample):
        self.samples.append(sample)

    def make_figures(self):
        if self.target_folder is not None:
            pathlib.Path(self.target_folder).mkdir(parents=True, exist_ok=True)
        for group in self.groups:
            for figure in group.figures:
                self._write_data(group, figure)
                script = self._generate_script(group, figure)
                print(script, file=sys.stderr)
                try:
                    subprocess.check_output(
                        ["gnuplot", "-p", "-e", script],
                    )
                except subprocess.CalledProcessError as e:
                    print(e.output, file=sys.stderr)
                    raise Exception("error while running gnuplot")

    def _write_data(self, group: Group, figure: Figure):
        with open(self.data_file_location, 'w') as data_file:
            writer = csv.writer(
                data_file,
                delimiter="\t",
            )
            for sample in self.samples:
                xy_pairs = [
                    [candidate_sample[group.x_metric], candidate_sample[figure.y_metric]]
                    for candidate_sample in sample["candidates"].values()
                ]
                writer.writerow(sum(xy_pairs, []))

    def _generate_script(self, group: Group, figure: Figure) -> str:
        plots = [
            _PLOT_TEMPLATE.format(
                data_file=self.data_file_location,
                x_index=index * 2 + 1,
                y_index=index * 2 + 2,
                label=_gnuplot_escape(candidate_name),
            )
            for index, candidate_name in enumerate(self.candidates)
        ]
        script = _SCRIPT_TEMPLATE.format(
            plots=", ".join(plots),
            x_label=_gnuplot_escape(group.x_label),
            y_label=_gnuplot_escape(figure.y_label),
        )
        if self.target_folder:
            script += _FILE_OUTPUT_TEMPLATE.format(
                output_file=f"{self.target_folder}/{figure.title}.png"
            )
        return script

    def required_metrics(self) -> list[str]:
        metrics = set()
        for group in self.groups:
            metrics.add(group.x_metric)
            for figure in group.figures:
                metrics.add(figure.y_metric)
        return list(metrics)
