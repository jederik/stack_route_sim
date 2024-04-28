import subprocess
import sys
import csv

_SCRIPT_TEMPLATE = """
set xlabel '{x_label}';
set ylabel '{y_label}';
plot {plots};
"""

_PLOT_TEMPLATE = """
'{data_file}' using {x_index}:{y_index} with lines title '{label}'
""".strip()


class Figure:
    def __init__(self, x_metric: str, y_metric: str, x_label: str, y_label: str):
        self.x_label = x_label
        self.y_label = y_label
        self.x_metric = x_metric
        self.y_metric = y_metric


def _create_figure(config) -> Figure:
    return Figure(
        x_metric=config["x"]["metric"],
        y_metric=config["y"]["metric"],
        x_label=config["x"]["label"] if "label" in config["x"] else config["x"]["metric"],
        y_label=config["y"]["label"] if "label" in config["y"] else config["y"]["metric"],
    )


def _gnuplot_escape(label: str) -> str:
    return label.replace("_", "\\_")


class FigureMaker:
    def __init__(self, config, candidates: list[str], data_file_location):
        self.figures = [
            _create_figure(figure_config)
            for figure_config in config
        ]
        self.candidates = candidates
        self.data_file_location = data_file_location
        self.samples = []

    def add_sample(self, sample):
        self.samples.append(sample)

    def make_figures(self):
        for figure in self.figures:
            self._write_data(figure)
            script = self._generate_script(figure)
            print(script, file=sys.stderr)
            try:
                subprocess.check_output(
                    ["gnuplot", "-p", "-e", script],
                )
            except subprocess.CalledProcessError as e:
                print(e.output, file=sys.stderr)
                raise Exception("error while running gnuplot")

    def _write_data(self, figure: Figure):
        with open(self.data_file_location, 'w') as data_file:
            writer = csv.writer(
                data_file,
                delimiter="\t",
            )
            for sample in self.samples:
                xy_pairs = [
                    [candidate_sample[figure.x_metric], candidate_sample[figure.y_metric]]
                    for candidate_sample in sample["candidates"].values()
                ]
                writer.writerow(sum(xy_pairs, []))

    def _generate_script(self, figure: Figure) -> str:
        plots = [
            _PLOT_TEMPLATE.format(
                data_file=self.data_file_location,
                x_index=index * 2 + 1,
                y_index=index * 2 + 2,
                label=candidate_name,
            )
            for index, candidate_name in enumerate(self.candidates)
        ]
        return _SCRIPT_TEMPLATE.format(
            plots=", ".join(plots),
            x_label=_gnuplot_escape(figure.x_label),
            y_label=_gnuplot_escape(figure.y_label),
        )

    def required_metrics(self) -> list[str]:
        metrics = set()
        for figure in self.figures:
            metrics.add(figure.x_metric)
            metrics.add(figure.y_metric)
        return list(metrics)
