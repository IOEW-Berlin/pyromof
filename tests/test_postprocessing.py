import os
from pathlib import Path

import numpy as np
import pandas as pd

from pyromof.postprocessing_functions import postprocessing

TEST_PATH = Path(__file__).parent
ROOT_PATH = TEST_PATH.parent


def test_calculate_variable_costs_per_flow_per_timestep():
    path_sequences = os.path.join(TEST_PATH, "files", "sequences.csv")
    sequences = pd.read_csv(path_sequences, sep=";", index_col=0)
    path_varcosts = os.path.join(TEST_PATH, "files", "variable_costs_from_model.csv")
    effective_variable_costs = postprocessing.calculate_variable_costs_per_flow_per_timestep(
        sequences, path_varcosts
    )
    expected_result = pd.DataFrame(
        columns=[
            "('b_biochar to biochar_market')",
            "('b_electricity_2 to electricity_grid')",
            "('b_co2 to co2_market')",
        ],
        index=[
            "2023-01-02 00:00:00",
            "2023-01-02 01:00:00",
            "2023-01-02 02:00:00",
            "2023-01-02 03:00:00",
        ],
        data={
            "('b_biochar to biochar_market')": [0, 0, 0, np.nan],
            "('b_electricity_2 to electricity_grid')": [
                -0.2,
                -0.2,
                -0.2,
                np.nan,
            ],
            "('b_co2 to co2_market')": [0.02, 0.02, 0.02, np.nan],
        },
    )
    assert effective_variable_costs.equals(expected_result)


def test_add_sums_to_scalar_results_with_existing_data():
    """Test add_sums_to_scalar_results appends to existing scalar results"""
    # Create initial scalar results with some data
    scalar_results = pd.DataFrame(
        {
            "variable": ["objective"],
            "type": ["objective [Euros]"],
            "value": [1000.0],
        }
    )

    # Create sample data
    data = pd.DataFrame(
        {
            "cost_1": [10.0, 20.0],
            "cost_2": [5.0, 15.0],
        }
    )

    result = postprocessing.add_sums_to_scalar_results(
        data, "sum of variable costs [Euros]", scalar_results
    )

    # Should have original row plus 2 new rows
    assert len(result) == 3
    assert result.iloc[0]["variable"] == "objective"
    assert result.loc[result["variable"] == "cost_1", "value"].values[0] == 30.0
    assert result.loc[result["variable"] == "cost_2", "value"].values[0] == 20.0
