import pandas as pd

from pyromof.preprocessing_functions import implement_input_data_functions
from pyromof.preprocessing_functions.define_input_data_functions import (
    retrieve_scenario_from_input_data,
)
from pyromof.preprocessing_functions.implement_policies import (
    feed_in_payment_sliding_premium,
    receive_and_refine_electricity_price_data,
)


def receive_data(data: dict) -> tuple[pd.Series, pd.Series, pd.Series]:
    scenario = retrieve_scenario_from_input_data(data["general"])

    sequences = pd.read_csv(
        f"./results/{scenario}/results/sequences.csv", sep=";", index_col=0, parse_dates=True
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
        / 100
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


if __name__ == "__main__":
    data, time, scenario = implement_input_data_functions.preprocess("input_data.xlsx")
    postprocess_sliding_premium(data)
    postprocess_feed_in_tariff(data)
