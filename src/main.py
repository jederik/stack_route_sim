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
                "steps": 100,
                "samples": 10,
            },
            "network": {
                "node_count": 100,
                "density": .1,
            }
        },
        emit_sample=dump_sample
    )
    experiment.run()


if __name__ == '__main__':
    run()
