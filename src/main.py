import json
import sys

from src import measure


def dump_sample(sample):
    json.dump(sample, fp=sys.stdout, indent=2)
    print()


def run():
    experiment = measure.Experiment(
        config={
            "measurement": {
                "steps": 3000,
                "samples": 100,
            },
            "candidates": {
                "random": {
                    "network": {
                        "node_count": 100,
                        "density": .1,
                    },
                    "strategy": {
                        "propagate_shortest_route": False,
                    },
                },
                "shortest": {
                    "network": {
                        "node_count": 100,
                        "density": .1,
                    },
                    "strategy": {
                        "propagate_shortest_route": True,
                    },
                },
            }
        },
        sample_emitter=dump_sample,
    )
    experiment.run()


if __name__ == '__main__':
    run()
