import os

import pandas as pd

from pyromof.paths import RESULTS_DIR, scenario_path, scenario_results_path


def calculate_electricity_fed_in_at_negative_price_timesteps(sequences, profiles):
    """
    This function identifies the timesteps where electricity is fed into the grid
    at a negative price and sums up the amount of electricity fed in at these timesteps.
    """
    # Align indices: keep only timestamps that exist in both dataframes
    common_index = sequences.index.intersection(profiles.index)
    sequences_aligned = sequences.loc[common_index]
    profiles_aligned = profiles.loc[common_index]

    # Identify the timesteps with negative electricity prices
    negative_price_timesteps = profiles_aligned[
        profiles_aligned["profile_electricity_remuneration"] > 0
    ].index

    # Sum up the electricity fed into the grid at these timestepsSS
    fed_in_at_negative_price = (
        sequences_aligned.loc[
            negative_price_timesteps,
            sequences_aligned.columns.str.contains("b_electricity to electricity_grid"),
        ]
        .sum()
        .sum()
    )

    share_of_total_electricity_fed_in = (
        fed_in_at_negative_price
        / sequences_aligned["b_electricity to electricity_grid"].sum().sum()
    )
    return fed_in_at_negative_price, share_of_total_electricity_fed_in * 100


def calculate_pyrolysis_full_load_hours(sequences):
    """
    This function calculates the full load hours of the pyrolysis
    process based on the amount of biochar produced.
    """
    total_biochar_produced = sequences["b_biochar to biochar_market"].sum()
    pyrolysis_capacity = sequences["b_biochar to biochar_market"].max()
    full_load_hours = total_biochar_produced / pyrolysis_capacity
    return full_load_hours


def calculate_storage_charging_cycles(scalars, sequences, storage):
    """
    This function calculates the number of charging cycles for each storage component
    based on the storage inflow over time.
    """
    charging_cycles = {}
    inflow_columns = [s for s in sequences.columns if "storage" in s.split(" to ")[1]]
    for column in sequences[inflow_columns]:
        storage_name = column.split(" to ")[1]
        total_inflow = sequences[column].sum()
        # Check if the storage name exists as a substring in the scalars variable column:
        if storage.loc[storage_name, "investment"].item() is True:
            storage_capacity = scalars.loc[
                scalars["variable"].str.contains(storage_name)
                & scalars["type"].str.contains("built capacity"),
                "value",
            ].item()
        else:
            storage_capacity = storage.loc[
                storage.index == storage_name, "nominal_storage_capacity"
            ].item()
        if storage_capacity > 0:
            charging_cycles[storage_name] = total_inflow / storage_capacity
        else:
            charging_cycles[storage_name] = 0
    return charging_cycles


def measure_flexibility(scenarios: list):
    # Create a table with scenarios as column names and the elec fed in at negative price,
    # the share of total electricity fed in at negative price and the pyrolysis full load
    # hours as rows

    results = pd.DataFrame(columns=scenarios)

    for scenario in scenarios:
        SCENARIO_RESULTS = scenario_results_path(scenario)
        SCENARIO_META_INFO = scenario_path(scenario) / "meta_info"

        sequences = pd.read_csv(
            os.path.join(SCENARIO_RESULTS, "sequences.csv"), sep=";", index_col=0
        )
        scalars = pd.read_csv(
            os.path.join(SCENARIO_RESULTS, "scalar_results.csv"), sep=";", index_col=0
        )
        profiles = pd.read_excel(
            os.path.join(SCENARIO_META_INFO, "input_data.xlsx"),
            sheet_name="profiles",
            index_col=0,
        )
        storage = pd.read_excel(
            os.path.join(SCENARIO_META_INFO, "input_data.xlsx"),
            sheet_name="storage",
            index_col=0,
        )
        fed_in_at_negative_price, share_of_total_electricity_fed_in = (
            calculate_electricity_fed_in_at_negative_price_timesteps(
                sequences, profiles
            )
        )
        pyrolysis_full_load_hours = calculate_pyrolysis_full_load_hours(sequences)

        charging_cycles = calculate_storage_charging_cycles(scalars, sequences, storage)

        results.loc["fed_in_at_negative_price", scenario] = fed_in_at_negative_price
        results.loc["share_of_total_electricity_fed_in", scenario] = (
            share_of_total_electricity_fed_in
        )
        results.loc["pyrolysis_full_load_hours", scenario] = pyrolysis_full_load_hours

        # Append charging_cycles to results DataFrame
        for storage_name, cycles in charging_cycles.items():
            rowname = f"charging_cycles_{storage_name}"
            results.loc[rowname, scenario] = cycles

    results.to_csv(RESULTS_DIR / "flexibility_results.csv", sep=";")


if __name__ == "__main__":
    scenarios = [
        "scenario_1",
        "scenario_2",
    ]
    measure_flexibility(scenarios)
