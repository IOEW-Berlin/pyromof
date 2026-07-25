from pathlib import Path

import pandas as pd

from pyromof.preprocessing_functions.define_input_data_functions import (
    read_raw_data,
    retrieve_scenario_from_input_data,
)
from pyromof.preprocessing_functions.define_storage_subsidies import (
    implement_storage_subsidies,
)


def flexinility_bonus(converters, policies, wacc):
    flex_bonus_per_kw_and_year = policies.loc[
        policies["policy"] == "Flexibility bonus", "value 1"
    ].values[0]
    flex_bonus_duration = policies.loc[policies["policy"] == "Flexibility bonus", "value 2"].values[
        0
    ]

    # lump_sum_calc_factor: Converts the annual bonus to a lump sum capex reduction
    # based on the duration of the bonus and the wacc.
    lump_sum_calc_factor = (1 - (1 + wacc) ** -flex_bonus_duration) / wacc
    subsidy_capex_reduction = flex_bonus_per_kw_and_year * lump_sum_calc_factor
    converters.loc[(converters["label"] == "chp"), "capex"] -= subsidy_capex_reduction

    return converters


def receive_and_refine_electricity_price_data(profiles):

    timestamps = pd.to_datetime(profiles.index)

    raw_data = profiles["profile_electricity_remuneration"]

    data_float = raw_data.astype(float)

    data_float.index = timestamps

    return data_float


def feed_in_tariff_policy(data) -> pd.DataFrame:

    feed_in_premium = (
        -1
        / 100
        * data["policies"].loc[data["policies"]["policy"] == "feed in tariff", "value 1"].values[0]
    )

    data["profiles"]["profile_electricity_premium"] = feed_in_premium

    return data


def feed_in_payment_sliding_premium(data) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    This function calculates the feed-in payment for each hour in euro per kwh.
    Based on the electricity price data, base value, and lower threshold from policies.
    The monthly sliding premium is calculated from the difference between base value
    and monthly average electricity price.
    The premium is only added if the current electricity price is above the lower threshold.
    Otherwise the feed-in payment is the electricity price.
    """

    electricity_price = receive_and_refine_electricity_price_data(data["profiles"])

    base_value = (
        -1
        / 100
        * data["policies"].loc[data["policies"]["policy"] == "Sliding premium", "value 1"].values[0]
    )

    lower_threshold = (
        -1
        / 100
        * data["policies"].loc[data["policies"]["policy"] == "Sliding premium", "value 2"].values[0]
    )

    monthly_average_price = electricity_price.groupby(
        electricity_price.index.to_period("M")
    ).transform("mean")

    sliding_premium = (base_value - monthly_average_price).where(
        electricity_price < lower_threshold, -0
    )

    feed_in_revenue = electricity_price + sliding_premium

    return feed_in_revenue, sliding_premium, monthly_average_price


def sliding_premium_policy(data) -> tuple[pd.DataFrame, pd.DataFrame]:

    feed_in_revenue, _, _ = feed_in_payment_sliding_premium(data)

    data["profiles"]["profile_electricity_premium"] = feed_in_revenue

    return data["sinks"], data["profiles"]


def lump_sum_investment_subsidy_policy(
    converters: pd.DataFrame, policies: pd.DataFrame
) -> pd.DataFrame:

    fix_subsidy = policies.loc[
        policies["policy"] == "Subsidy for pyrolysis investment costs: lump sum", "value 1"
    ].values[0]

    converters.loc[(converters["label"] == "pyrolysis"), "capex"] = (
        converters.loc[(converters["label"] == "pyrolysis"), "capex"] - fix_subsidy
    )

    return converters


def percentage_investment_subsidy_policy(
    converters: pd.DataFrame, policies: pd.DataFrame
) -> pd.DataFrame:

    percentage_subsidy = policies.loc[
        policies["policy"] == "Subsidy for pyrolysis investment costs: capex share", "value 1"
    ].values[0]

    converters.loc[(converters["label"] == "pyrolysis"), "capex"] = converters.loc[
        (converters["label"] == "pyrolysis"), "capex"
    ] * (1 - (1 / 100 * percentage_subsidy))

    return converters


def check_policy_choice_compatibility(activated_policies, converters):

    if (
        ("feed in tariff" in activated_policies and "Sliding premium" in activated_policies)
        or (
            "Subsidy for pyrolysis investment costs: lump sum" in activated_policies
            and "Subsidy for pyrolysis investment costs: capex share" in activated_policies
        )
        or (
            "Subsidy for electricity storage: lump sum" in activated_policies
            and "Subsidy for electricity storage: capex share" in activated_policies
        )
        or (
            "Subsidy for heat storage: lump sum" in activated_policies
            and "Subsidy for heat storage: capex share" in activated_policies
        )
        or (
            "Subsidy for hydrogen storage: lump sum" in activated_policies
            and "Subsidy for hydrogen storage: capex share" in activated_policies
        )
        or (
            "Subsidy for co2 storage: lump sum" in activated_policies
            and "Subsidy for co2 storage: capex share" in activated_policies
        )
        or (
            "limitation of subsidized full load hours" in activated_policies
            and "limitation of subsidized operation time" in activated_policies
        )
    ):
        raise ValueError(
            "Only one of the policies in each policy type can be activated at the same time. \n"
            "Please check your input in the policies sheet."
        )

    if "Flexibility bonus" in activated_policies and not (
        "limitation of subsidized full load hours" in activated_policies
        or "limitation of subsidized operation time" in activated_policies
    ):
        print(
            "Warning: Flexibility bonus is activated without "
            "limitation of full load hours or operation time. "
            "Please check wheter this is intended. "
            "In Germany, these instruments are used in combination."
        )

    if (
        "High load time for chp" in activated_policies
        and "Flexibility bonus" not in activated_policies
    ):
        print(
            "Warning: High load time for chp is activated without "
            "Flexibility bonus. Please check wheter this is intended. "
            "Usually, the high load time is a restriction for the Flexibility bonus."
        )

    chp_row = converters.loc[converters["label"] == "chp"]
    if (
        "High load time for chp" in activated_policies
        and not chp_row.empty
        and chp_row["investment"].item() is True
    ):
        print(
            "Warning: High load time for chp is activated, in chp investment mode. "
            "The instrument does only effect the optimization in dispatch mode."
        )
    else:
        return print("policies confirmed")


def redefine_input_data_for_policies(data, activated_policies):

    if "feed in tariff" in activated_policies:
        data["sinks"] = feed_in_tariff_policy(
            data["sinks"],
            data["policies"],
        )
    if "Sliding premium" in activated_policies:
        data["sinks"], data["profiles"] = sliding_premium_policy(data)

    if "Subsidy for pyrolysis investment costs: lump sum" in activated_policies:
        data["converters"] = lump_sum_investment_subsidy_policy(
            data["converters"],
            data["policies"],
        )

    if "Subsidy for pyrolysis investment costs: capex share" in activated_policies:
        data["converters"] = percentage_investment_subsidy_policy(
            data["converters"],
            data["policies"],
        )

    if "Flexibility bonus" in activated_policies:
        wacc = data["general"].loc[data["general"]["label"] == "wacc", "value"].values[0]
        data["converters"] = flexinility_bonus(
            data["converters"],
            data["policies"],
            wacc,
        )
    return data


def implement_policies(data, scenario) -> None:

    active_policies = (
        data["policies"]
        .loc[data["policies"]["activate"] == "x", ["policy", "value 1"]]
        .set_index("policy")["value 1"]
        .to_dict()
    )

    check_policy_choice_compatibility(active_policies, data["converters"])

    # drop column "scenario" from all tables where it exists
    for key in data:
        if "scenario" in data[key].columns:
            data[key].drop(columns=["scenario"], inplace=True)
    data = redefine_input_data_for_policies(data, active_policies)
    data["storage"] = implement_storage_subsidies(data, active_policies)
    output_file = (
        Path("results")
        / scenario
        / "meta_info"
        / "input_preprocessed"
        / "input_data_with_applied_policies.xlsx"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_file) as writer:
        for table_name, table_data in data.items():
            table_data = table_data.replace({True: "True", False: "False"})

            if isinstance(table_data, pd.DataFrame):
                export_df = table_data.copy()

                if isinstance(export_df.index, pd.DatetimeIndex):
                    if export_df.index.name is None:
                        export_df.index.name = "timeindex"

                    export_df = export_df.reset_index()

                export_df.to_excel(
                    writer,
                    sheet_name=table_name,
                    index=False,
                )
    return data


if __name__ == "__main__":
    data = read_raw_data("input_data.xlsx")
    scenario = retrieve_scenario_from_input_data(data["general"])
    implement_policies(data, scenario)
