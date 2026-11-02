"""
Calculates the payments of the activated policies after the optimization (capex subsidies,
feed in tariff and sliding premium) and saves them in
results/<scenario>/results/policies_subsidies.csv.
"""

import pandas as pd

from pyromof.paths import scenario_results_path
from pyromof.preprocessing_functions.implement_policies import (
    check_policy_choice_compatibility,
    feed_in_payment_sliding_premium,
    receive_and_refine_electricity_price_data,
)
from pyromof.preprocessing_functions.preprocess import (
    filter_input_data_by_scenario,
    read_raw_data,
    retrieve_scenario_from_input_data,
)


# Capex policies: investment subsidies and flexibility bonus
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


def receive_capacity(data, label):
    investment = (
        data["converters"].loc[data["converters"]["label"] == label, "investment"].values[0]
    )

    if not investment:
        capacity = float(
            data["converters"]
            .loc[data["converters"]["label"] == label, "nominal_capacity"]
            .values[0]
        )
    else:
        capacity = receive_investment(data, f"{label} to b_electricity", "built capacity")
    return capacity


def flexibility_bonus_subsidy(data):
    policy_row = data["policies"].loc[data["policies"]["policy"] == "flexibility bonus"]
    flex_bonus_per_kw_and_year = float(policy_row["value 1"].values[0])
    flex_bonus_duration = float(policy_row["value 2"].values[0])
    labels = [label for label in ["chp", "orc"] if label in data["converters"]["label"].values]
    capacity = sum(receive_capacity(data, label) for label in labels)

    general = data["general"]
    start_time = pd.Timestamp(general.loc[general["label"] == "start_time", "value"].item())
    end_time = pd.Timestamp(general.loc[general["label"] == "end_time", "value"].item())
    optimization_horizon_years = ((end_time - start_time).total_seconds() / 3600 + 1) / 8760

    relevant_period_years = min(optimization_horizon_years, flex_bonus_duration)
    total_bonus = round(flex_bonus_per_kw_and_year * capacity * relevant_period_years, 1)

    return {"flexibility_bonus_remuneration": total_bonus}


def receive_pyrolysis_investment(data, scalar_objective):
    investment = (
        data["converters"].loc[data["converters"]["label"] == "pyrolysis", "investment"].values[0]
    )
    if not investment:
        pyrolysis_investment = (
            data["converters"]
            .loc[data["converters"]["label"] == "pyrolysis", "nominal_capacity"]
            .values[0]
        )

    else:
        pyrolysis_investment = receive_investment(data, scalar_objective, "built capacity")
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


def receive_storage_capacity(data, subsidized_investment, scalar_objective):
    row = data["storage"].loc[data["storage"]["label"] == subsidized_investment]
    if not row["investment"].values[0]:
        return float(row["nominal_storage_capacity"].values[0])
    return receive_investment(data, scalar_objective, "built capacity")


def lump_sum_storage_subsidy(data, subsidy_value, subsidized_investment, scalar_objective):

    subsidy = data["policies"].loc[data["policies"]["policy"] == subsidy_value, "value 1"].values[0]
    storage_investment = receive_storage_capacity(data, subsidized_investment, scalar_objective)
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
    storage_investment = receive_storage_capacity(data, subsidized_investment, scalar_objective)
    subsidy_per_installed_capacity = percentage_subsidy * storage_capex
    total_subsidy = subsidy_per_installed_capacity * storage_investment
    total_subsidy = round(total_subsidy, 1)
    return {subsidized_investment: total_subsidy}


# Opex policies: feed in tariff and sliding premium
def receive_data(data: dict) -> tuple[pd.Series, pd.Series, pd.Series]:
    scenario = retrieve_scenario_from_input_data(data["general"])

    sequences = pd.read_csv(
        scenario_results_path(scenario) / "sequences.csv", sep=";", index_col=0, parse_dates=True
    )
    subsidized_electricity_output = sequences["b_electricity to electricity_grid_subsidy"]
    unsubsidized_electricity_output = sequences["b_electricity to electricity_grid"]

    electricity_price = receive_and_refine_electricity_price_data(data["profiles"])

    return (electricity_price, subsidized_electricity_output, unsubsidized_electricity_output)


def postprocess_feed_in_tariff(data):

    electricity_price, subsidized_electricity_output, unsubsidized_electricity_output = (
        receive_data(data)
    )

    feed_in_tariff = (
        -1
        * data["policies"].loc[data["policies"]["policy"] == "feed in tariff", "value 1"].values[0]
    )
    government_payment_share = feed_in_tariff - electricity_price

    total_electricity_output = subsidized_electricity_output + unsubsidized_electricity_output
    market_payment = electricity_price * total_electricity_output
    government_payment = government_payment_share * subsidized_electricity_output
    feed_in_revenue = market_payment + government_payment

    sum_market_payment = market_payment.sum().round(1)
    sum_government_payment = government_payment.sum().round(1)
    sum_feed_in_revenue = feed_in_revenue.sum().round(1)

    return {
        "feed_in_revenue": sum_feed_in_revenue,
        "government_payment": sum_government_payment,
        "market_payment": sum_market_payment,
    }


def postprocess_sliding_premium(data):
    # receive input data
    electricity_price, subsidized_electricity_output, unsubsidized_electricity_output = (
        receive_data(data)
    )
    _, sliding_premium, _ = feed_in_payment_sliding_premium(data)
    total_electricity_output = subsidized_electricity_output + unsubsidized_electricity_output
    # calculate payments
    market_payment = electricity_price * total_electricity_output
    government_payment = sliding_premium * subsidized_electricity_output
    feed_in_revenue = market_payment + government_payment

    # calculate payment sums
    sum_government_payment = government_payment.sum().round(1)
    sum_feed_in_revenue = feed_in_revenue.sum().round(1)
    sum_market_payment = market_payment.sum().round(1)
    return {
        "feed_in_revenue": sum_feed_in_revenue,
        "government_payment": sum_government_payment,
        "market_payment": sum_market_payment,
    }


# Collection of the results of all activated policies
def log_postprocessed_policies(data, scenario):

    activated_policies = (
        data["policies"].loc[data["policies"]["activate"] == "x", "policy"].dropna().tolist()
    )

    active_opex = (
        data["policies"]
        .loc[
            (data["policies"]["activate"] == "x") & (data["policies"]["policy category"] == "opex"),
            "policy",
        ]
        .dropna()
        .tolist()
    )
    opex_label = " + ".join(active_opex)

    check_policy_choice_compatibility(activated_policies, data["converters"])
    print("active policies:", activated_policies)

    policy_functions = {
        "feed in tariff": {
            "function": postprocess_feed_in_tariff,
            "type": "opex",
        },
        "sliding premium": {
            "function": postprocess_sliding_premium,
            "type": "opex",
        },
        "flexibility bonus": {
            "function": flexibility_bonus_subsidy,
            "type": "capex",
        },
        "subsidy for pyrolysis investment costs: capex share": {
            "function": capex_share_pyrolysis_subsidy,
            "type": "capex",
            "subsidized_investment": "pyrolysis",
            "scalar_objective": "pyrolysis to b_biochar_pre_shift",
        },
        "subsidy for pyrolysis investment costs: lump sum": {
            "function": lump_sum_pyrolysis_subsidy,
            "type": "capex",
            "subsidized_investment": "pyrolysis",
            "scalar_objective": "pyrolysis to b_biochar_pre_shift",
        },
        "subsidy for electricity storage: lump sum": {
            "function": lump_sum_storage_subsidy,
            "type": "capex",
            "subsidized_investment": "electricity_storage",
            "scalar_objective": "electricity_storage to None",
        },
        "subsidy for electricity storage: capex share": {
            "function": capex_share_storage_subsidy,
            "type": "capex",
            "subsidized_investment": "electricity_storage",
            "scalar_objective": "electricity_storage to None",
        },
        "subsidy for heat storage: lump sum": {
            "function": lump_sum_storage_subsidy,
            "type": "capex",
            "subsidized_investment": "heat_storage",
            "scalar_objective": "heat_storage to None",
        },
        "subsidy for heat storage: capex share": {
            "function": capex_share_storage_subsidy,
            "type": "capex",
            "subsidized_investment": "heat_storage",
            "scalar_objective": "heat_storage to None",
        },
        "subsidy for hydrogen storage: lump sum": {
            "function": lump_sum_storage_subsidy,
            "type": "capex",
            "subsidized_investment": "h2_storage",
            "scalar_objective": "h2_storage to None",
        },
        "subsidy for hydrogen storage: capex share": {
            "function": capex_share_storage_subsidy,
            "type": "capex",
            "subsidized_investment": "h2_storage",
            "scalar_objective": "h2_storage to None",
        },
        "subsidy for syngas storage: lump sum": {
            "function": lump_sum_storage_subsidy,
            "type": "capex",
            "subsidized_investment": "syngas_storage",
            "scalar_objective": "syngas_storage to None",
        },
        "subsidy for syngas storage: capex share": {
            "function": capex_share_storage_subsidy,
            "type": "capex",
            "subsidized_investment": "syngas_storage",
            "scalar_objective": "syngas_storage to None",
        },
    }
    rows = []

    for policy in activated_policies:
        entry = policy_functions.get(policy)
        if entry is None:
            continue

        function = entry["function"]
        policy_type = entry["type"]

        kwargs = {}
        if "subsidized_investment" in entry:
            kwargs = {
                "subsidy_value": policy,
                "subsidized_investment": entry["subsidized_investment"],
                "scalar_objective": entry["scalar_objective"],
            }
        result = function(data, **kwargs)

        if policy_type == "opex":
            label = opex_label
        else:
            label = policy

        for name, value in result.items():
            rows.append(
                {
                    "name": name,
                    "policy category": policy_type,
                    "relevant activated policies": label,
                    "value (euro)": value,
                }
            )
    df = pd.DataFrame(rows)

    results_dir = scenario_results_path(scenario)

    df.to_csv(results_dir / "policies_subsidies.csv", index=False, sep=";")


if __name__ == "__main__":
    data = read_raw_data("input_data.xlsx")
    data["profiles"] = data["profiles"].set_index("timeindex")
    data["profiles"].index = pd.to_datetime(data["profiles"].index)
    scenario = retrieve_scenario_from_input_data(data["general"])
    data = filter_input_data_by_scenario(data, scenario)
    log_postprocessed_policies(data, scenario)
