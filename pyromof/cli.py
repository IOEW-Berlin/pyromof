import argparse

from pyromof.pipeline import PIPELINE_STEPS, run_pipeline


def main():
    parser = argparse.ArgumentParser(description="Energy model pipeline")

    parser.add_argument(
        "steps",
        nargs="+",
        choices=PIPELINE_STEPS.keys(),
        help="Steps to execute in order",
    )

    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Scenario name for steps that require it",
    )

    args = parser.parse_args()

    run_pipeline(args.steps, scenario=args.scenario)


if __name__ == "__main__":
    main()
