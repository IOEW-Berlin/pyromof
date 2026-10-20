import os
import shutil
from functools import reduce

import pandas as pd

from pyromof import optimize, postprocessing, preprocessing_functions
from pyromof.paths import (
    scenario_results_path,
)
from pyromof.preprocessing_functions.preprocessing_input_data import (
    calculate_ep_costs_for_all_components,
)


def run_sensitivity_step(
    parameter_value,
    parameters,
    data,
    time,
    epcs,
    META_INFO,
    DUMPING_SPACE,
    scenario,
    THIS_SENSITIVITY,
):
    df_name = parameters["component_type"]
    data[df_name].loc[
        data[df_name]["label"] == parameters["component"],
        parameters["variable"],
    ] = parameter_value

    # Recalculate EPCs after changing the parameter
    epcs = calculate_ep_costs_for_all_components(data, time)

    # OPTIMIZATION
    es, om = optimize.create_energysystem(
        META_INFO=META_INFO, data=data, time=time, epcs=epcs
    )
    optimize.save_results(
        es,
        om,
        META_INFO,
        DUMPING_SPACE,
        scenario,
        time,
        epcs=epcs,
    )

    # POSTPROCESSING
    result_dfs = postprocessing.postprocess(
        dumping_space=DUMPING_SPACE, results=THIS_SENSITIVITY
    )

    postprocessing.check_scalar_costs_consistency(result_dfs["scalar_results"])

    result_dfs["scalar_results"].rename(
        columns={"value": parameter_value}, inplace=True
    )
    return result_dfs["scalar_results"]


def analyze_sensitivity():
    # Insert here the parameters. Only two decimal places are possible!
    parameters = {
        "component_type": "storage",  # must be plural
        "component": "syngas_storage",
        "variable": "capex",
        "min": 160,
        "max": 250,
        "step": 10,
    }

    # Select the scenario here:
    scenario = "Scenario_X"

    # Definition of the time period
    data, time, scenario, epcs = (
        preprocessing_functions.preprocessing_input_data.preprocess("input_data.xlsx")
    )

    RESULTS = scenario_results_path(scenario)
    parameter_name = parameters["component"] + "_" + parameters["variable"]
    print(parameter_name)
    (RESULTS / "sensitivity").mkdir(exist_ok=True)
    (RESULTS / "sensitivity" / parameter_name).mkdir(exist_ok=True)
    THIS_SENSITIVITY = RESULTS / "sensitivity" / parameter_name

    # These folders will be deleted again in the end
    # Create folders for meta_info and dumping_space
    (THIS_SENSITIVITY / "meta_info").mkdir(exist_ok=True)
    META_INFO = THIS_SENSITIVITY / "meta_info"
    (THIS_SENSITIVITY / "dumping_space").mkdir(exist_ok=True)
    DUMPING_SPACE = THIS_SENSITIVITY / "dumping_space"

    # Copy scenario-level exogenous investment costs into sensitivity results
    shutil.copy(
        os.path.join(RESULTS, "exogenous_investment_costs.csv"),
        os.path.join(THIS_SENSITIVITY, "exogenous_investment_costs.csv"),
    )

    # Loop over the steps below, changing the sensitivity parameter in the raw data each time
    all_dfs = []
    value_range = [
        x / 100
        for x in range(
            int(parameters["min"] * 100),
            int(parameters["max"] * 100) + int(parameters["step"] * 100),
            int(parameters["step"] * 100),
        )
    ]
    # Somewhat complicated workaround because "range" only accepts integers
    for parameter_value in value_range:
        print(parameter_value)
        scalar_results = run_sensitivity_step(
            parameter_value,
            parameters,
            data,
            time,
            epcs,
            META_INFO,
            DUMPING_SPACE,
            scenario,
            THIS_SENSITIVITY,
        )
        print(scalar_results)
        all_dfs.append(scalar_results)

    merged_df = reduce(
        lambda left, right: pd.merge(left, right, on=["variable", "type"], how="outer"),
        all_dfs,
    )
    # Save scalar results when all are collected
    merged_df.to_csv(
        os.path.join(THIS_SENSITIVITY, "scalar_results_" + parameter_name + ".csv"),
        sep=";",
    )

    # Delete all other CSV files in the sensitivity results folder, keeping only the
    # merged scalar results
    merged_file = "scalar_results_" + parameter_name + ".csv"
    for file in THIS_SENSITIVITY.glob("*.csv"):
        if file.name != merged_file:
            file.unlink()

    # Delete folders dumping space and meta info
    shutil.rmtree(DUMPING_SPACE)
    shutil.rmtree(META_INFO)
