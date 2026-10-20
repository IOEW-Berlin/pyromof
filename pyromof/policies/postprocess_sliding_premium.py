import os

import pandas as pd

from pyromof.helpers import add_items_to_scalar_results
from pyromof.paths import scenario_meta_info_path, scenario_results_path
from pyromof.policies.implement_policies import (
    feed_in_payment_sliding_premium,
    receive_and_refine_electricity_price_data,
    receive_higher_threshold_basis_and_lower_threshold_basis,
)
from pyromof.preprocessing_functions import preprocessing_input_data


def receive_data(scenario: str, data: dict) -> tuple[pd.Series, pd.Series, float, float]:

    policies = data["policies"]

    base_value, lower_threshold = receive_higher_threshold_basis_and_lower_threshold_basis(policies)

    pyrolysis_electricity_output = pd.read_csv(
        scenario_results_path(scenario) / "sequences.csv",
        sep=";",
        index_col=0,
        parse_dates=True,
    )["b_electricity to electricity_grid"]

    electricity_price = receive_and_refine_electricity_price_data(data["profiles"])

    return (
        electricity_price,
        pyrolysis_electricity_output,
        base_value,
        lower_threshold,
    )


def calculate_payment_sums(
    electricity_price,
    pyrolysis_electricity_output,
    base_value,
    lower_threshold,
    scenario,
):

    # calculate sliding premium and revenue per kwh
    feed_in_revenue_euro_per_kwh, sliding_premium, monthly_average_price = (
        feed_in_payment_sliding_premium(
            electricity_price,
            base_value,
            lower_threshold,
        )
    )

    # calculate payments
    feed_in_revenue = feed_in_revenue_euro_per_kwh * pyrolysis_electricity_output

    government_payment_share = sliding_premium * pyrolysis_electricity_output

    electricity_market_payment_euro = feed_in_revenue - government_payment_share

    # calculate payment sums
    sum_government_payment_share = government_payment_share.sum()
    sum_feed_in_revenue = feed_in_revenue.sum()
    sum_electricity_market_payment_euro = electricity_market_payment_euro.sum()

    # create csv file with payment sums
    results_dir = scenario_results_path(scenario)
    df2 = pd.DataFrame({})

    sum_dict = {
        "government_payment_share (euro)": sum_government_payment_share,
        "electricity_market_payment_share (euro)": sum_electricity_market_payment_euro,
        "revenue_fed_in_electricity (euro)": sum_feed_in_revenue,
    }
    revenue_sums = add_items_to_scalar_results(sum_dict, "sliding_premium", df2.copy())

    revenue_sums.to_csv(
        os.path.join(results_dir, "electricity_revenue_data.csv"), index=False, sep=";"
    )


def main(scenario: str) -> None:
    scenario_input_data_path = scenario_meta_info_path(scenario) / "input_data.xlsx"
    data, __, __, __ = preprocessing_input_data.preprocess(scenario_input_data_path)
    (
        electricity_price_euro_per_kwh,
        pyrolysis_electricity_output,
        base_value,
        lower_threshold,
    ) = receive_data(scenario, data)

    calculate_payment_sums(
        electricity_price_euro_per_kwh,
        pyrolysis_electricity_output,
        base_value,
        lower_threshold,
        scenario,
    )


if __name__ == "__main__":
    scenario = "Scenario_X"
    main(scenario)
