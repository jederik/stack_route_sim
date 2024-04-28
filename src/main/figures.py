import subprocess
import sys

_SCRIPT_TEMPLATE = """
plot {plots}
""".strip()

_PLOT_TEMPLATE = """
'{data_file}' using {x_index}:{y_index} with lines title '{label}'
""".strip()


class Figure:
    def __init__(self, x_metric: str, y_metric: str):
        self.x_metric = x_metric
        self.y_metric = y_metric

    pass


def _create_figure(config) -> Figure:
    return Figure(
        x_metric=config["x"]["metric"],
        y_metric=config["y"]["metric"],
    )


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
            script = self._generate_script()
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
            for sample in self.samples:
                formatted_sample = self._format_sample(sample, figure)
                data_file.write(f"{formatted_sample}")
        with open(self.data_file_location, 'r') as data_file:
            print(data_file.read())

    def _generate_script(self) -> str:
        plots = [
            _PLOT_TEMPLATE.format(
                data_file=self.data_file_location,
                x_index=index * 2 + 1,
                y_index=index * 2 + 2,
                label=candidate_name,
            )
            for index, candidate_name in enumerate(self.candidates)
        ]
        return _SCRIPT_TEMPLATE.format(plots=", ".join(plots))

    def _format_sample(self, sample, figure: Figure) -> str:
        line = "\t".join(
            [
                f"{candidate_sample[figure.x_metric]}\t{candidate_sample[figure.y_metric]}"
                for name, candidate_sample in sample["candidates"].items()
            ]
        )
        return f"{line}\n"

    def required_metrics(self) -> list[str]:
        metrics = set()
        for figure in self.figures:
            metrics.add(figure.x_metric)
            metrics.add(figure.y_metric)
        return list(metrics)
