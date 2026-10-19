"""
Calculates the payments of capex subsidies (flexibility bonus, pyrolysis and storage
subsidies) after the optimization.
"""

import pandas as pd

from pyromof.paths import scenario_results_path
from pyromof.preprocessing_functions import implement_input_data_functions
from pyromof.preprocessing_functions.define_input_data_functions import (
    retrieve_scenario_from_input_data,
)


def receive_investment(data, variable_name, type_name):
    scenario = retrieve_scenario_from_input_data(data["general"])
    file_path = scenario_results_path(scenario) / "scalar_results.csv"
    scalar_results = pd.read_csv(file_path, sep=";")

    result = scalar_results.loc[
        (scalar_results["variable"] == variable_name) & (scalar_results["type"] == type_name),
        "value",
    ].values[0]
    if isinstance(result, str):
        result = result.replace(".", "")
    return float(result)


def receive_chp_capacity(data, scalar_objective):
    investment = (
        data["converters"].loc[data["converters"]["label"] == "chp", "investment"].values[0]
    )

    if not investment:
        chp_capacity = float(
            data["converters"]
            .loc[data["converters"]["label"] == "chp", "nominal_capacity"]
            .values[0]
        )
    else:
        chp_capacity = receive_investment(data, scalar_objective, "built capacity")
    return chp_capacity


def flexibility_bonus_subsidy(data):
    policy_row = data["policies"].loc[data["policies"]["policy"] == "Flexibility bonus"]
    flex_bonus_per_kw_and_year = float(policy_row["value 1"].values[0])
    flex_bonus_duration = float(policy_row["value 2"].values[0])
    chp_capacity = receive_chp_capacity(data, "chp to b_electricity")

    general = data["general"]
    start_time = pd.Timestamp(general.loc[general["label"] == "start_time", "value"].item())
    end_time = pd.Timestamp(general.loc[general["label"] == "end_time", "value"].item())
    optimization_horizon_years = ((end_time - start_time).total_seconds() / 3600 + 1) / 8760

    relevant_period_years = min(optimization_horizon_years, flex_bonus_duration)
    total_bonus = round(flex_bonus_per_kw_and_year * chp_capacity * relevant_period_years, 1)

    return {"flexibility_bonus_remuneration": total_bonus}


def receive_pyrolysis_investment(data, scalar_objective):
    investment = (
        data["converters"].loc[data["converters"]["label"] == "pyrolysis", "investment"].values[0]
    )
    # *8.76 converts the biochar capacity from kg/h to t/year (8760 h/year / 1000 kg/t)
    if not investment:
        pyrolysis_investment = (
            8.76
            * data["converters"]
            .loc[data["converters"]["label"] == "pyrolysis", "nominal_capacity"]
            .values[0]
        )

    else:
        pyrolysis_investment = 8.76 * receive_investment(data, scalar_objective, "built capacity")
    return pyrolysis_investment


def lump_sum_pyrolysis_subsidy(data, subsidy_value, subsidized_investment, scalar_objective):
    _ = subsidized_investment
    pyrolysis_investment = receive_pyrolysis_investment(data, scalar_objective)

    subsidy_per_biochar_ton = (
        data["policies"].loc[data["policies"]["policy"] == subsidy_value, "value 1"].values[0]
    )
    total_subsidy = subsidy_per_biochar_ton * pyrolysis_investment
    total_subsidy = round(total_subsidy, 1)
    return {"pyrolysis_capex_subsidy": total_subsidy}


def capex_share_pyrolysis_subsidy(data, subsidy_value, subsidized_investment, scalar_objective):
    pyrolysis_investment = receive_pyrolysis_investment(data, scalar_objective)
    percentage_subsidy = (
        1
        / 100
        * data["policies"]
        .loc[
            data["policies"]["policy"] == subsidy_value,
            "value 1",
        ]
        .values[0]
    )
    pyrolysis_capex = (
        data["converters"]
        .loc[data["converters"]["label"] == subsidized_investment, "capex"]
        .values[0]
    )
    subsidy_per_biochar_ton = percentage_subsidy * pyrolysis_capex
    total_subsidy = subsidy_per_biochar_ton * pyrolysis_investment
    total_subsidy = round(total_subsidy, 1)
    return {"pyrolysis_capex_subsidy": total_subsidy}


def lump_sum_storage_subsidy(data, subsidy_value, subsidized_investment, scalar_objective):

    subsidy = data["policies"].loc[data["policies"]["policy"] == subsidy_value, "value 1"].values[0]
    storage_investment = receive_investment(data, scalar_objective, "built capacity")
    total_subsidy = subsidy * storage_investment
    total_subsidy = round(total_subsidy, 1)

    return {subsidized_investment: total_subsidy}


def capex_share_storage_subsidy(data, subsidy_value, subsidized_investment, scalar_objective):
    storage_capex = (
        data["storage"].loc[data["storage"]["label"] == subsidized_investment, "capex"].values[0]
    )
    percentage_subsidy = (
        1
        / 100
        * data["policies"].loc[data["policies"]["policy"] == subsidy_value, "value 1"].values[0]
    )
    storage_investment = receive_investment(data, scalar_objective, "built capacity")
    subsidy_per_installed_capacity = percentage_subsidy * storage_capex
    total_subsidy = subsidy_per_installed_capacity * storage_investment
    total_subsidy = round(total_subsidy, 1)
    return {subsidized_investment: total_subsidy}


if __name__ == "__main__":
    data, time, scenario = implement_input_data_functions.preprocess("input_data.xlsx")
    lump_sum_pyrolysis_subsidy(data)
    capex_share_pyrolysis_subsidy(data)
    lump_sum_storage_subsidy(
        data,
        "Subsidy for electricity storage: lump sum",
        "electricity_storage",
        "electricity_storage_invest to None",
    )
    capex_share_storage_subsidy(
        data,
        "Subsidy for electricity storage: capex share",
        "electricity_storage",
        "electricity_storage_invest to None",
    )
