from pathlib import Path

from pyromof import (
    analyse_sensitivity,
    compare_scenarios,
    load_demand_profiles,
    load_duration_curve,
    optimize,
    plotting,
    postprocessing,
)

pyromof = Path(__file__).parent

PIPELINE_STEPS = {
    "load_demand_profiles": load_demand_profiles.load_demand_profiles,
    "optimize": optimize.optimize,
    "postprocess": postprocessing.postprocess,
    "plot": [
        plotting.plot_sequences_and_scalars,
        load_duration_curve.plot_load_duration_curves,
    ],
    "compare_scenarios": compare_scenarios.compare_scenarios,
    "analyse_sensitivity": analyse_sensitivity.analyze_sensitivity,
}


def run_pipeline(steps, scenario=None):
    for step in steps:
        if step in PIPELINE_STEPS:
            print(f"Running {step}...")
            handler = PIPELINE_STEPS[step]
            if isinstance(handler, list):
                # Execute multiple functions
                for func in handler:
                    if scenario:
                        func(scenario)
                    else:
                        func()
            else:
                # Execute single function
                if scenario:
                    handler(scenario)
                else:
                    handler()
        else:
            print(f"Step {step} is not recognized. Skipping.")
