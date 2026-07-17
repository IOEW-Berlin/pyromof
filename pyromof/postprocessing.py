import os
from pathlib import Path

import pandas as pd
from oemof.solph import (
    EnergySystem,
    processing,
)

from pyromof import helpers
from pyromof.paths import (
    scenario_dumping_space_path,
    scenario_path,
    scenario_results_path,
)
from pyromof.postprocessing_functions.log_policies import log_postprocessed_policies
from pyromof.preprocessing_functions.define_input_data_functions import read_raw_data


def add_sums_to_scalar_results(data, description, scalar_results):
    """
    Calculate sums of the data and append them to the scalar results if they are not 0.

    Args:
        data: DataFrame to sum (sequences or costs)
        description: Description of the data type for the results (e.g., "sum of flow [kWh]")
        scalar_results: Existing scalar results dataframe

    Returns:
        Updated scalar results dataframe
    """
    sums = data.sum(axis=0)
    dict = {index: value for index, value in sums.items()}
    scalar_results = helpers.add_items_to_scalar_results(dict, description, scalar_results)
    return scalar_results


def add_objective_to_scalar_results(results, scalar_results):
    scalar_results = helpers.add_items_to_scalar_results(
        {"objective": results["meta"]["objective"]},
        "objective [Euros]",
        scalar_results,
    )
    return scalar_results


def convert_result_sequences_to_df(results_data):
    """
    This function extracts all the sequences and all scalars from the flows
    from the results data and stores them in dataframes.
    Also captures additional columns like positive_gradient, biochar_status, etc.
    """
    results = processing.convert_keys_to_strings(results_data)
    flows = [x for x in results.keys() if x[1] != "None"]
    nodes = [x for x in results.keys() if x[1] == "None"]

    df_sequences = pd.DataFrame()
    df_additional_columns = pd.DataFrame()
    df_scalars = pd.DataFrame(columns=flows)
    df_storage_content = pd.DataFrame()

    for flow in flows:
        flow_name = " to ".join(flow)
        sequences_data = results[flow]["sequences"]

        # Add the flow column
        if "flow" in sequences_data.columns:
            df_sequences[flow_name] = sequences_data["flow"]

        # Capture all other columns (positive_gradient, biochar_status, etc.)
        additional_cols = [col for col in sequences_data.columns if col != "flow"]
        for col in additional_cols:
            col_name = f"{flow_name} ({col})"
            df_additional_columns[col_name] = sequences_data[col]

        df_scalars[flow_name] = results[flow]["scalars"]

    for node in nodes:
        node_name = " to ".join(node)
        df_scalars[node_name] = results[node]["scalars"]
        df_storage_content[node_name] = results[node]["sequences"]["storage_content"]

    return (
        df_sequences,
        df_scalars,
        df_storage_content,
        df_additional_columns,
    )


def gas_char_ratio(df_sequences, df_additional_columns, converters):
    """
    This function calculates the ratio of biochar to syngas output for the pyrolysis process.
    The ratio is then added as a column to the df_additional_columns dataframe.
    The ratio is calculated using the outputs from the sequences dataframe.
    Then, the ratio is multiplied with the normed ratio to get a ratio range close to 1.
    The normed ratio is based on the normed pyrolysis outputs from the input_data.xlsx file.
    """
    normed_biochar_output = converters.loc[converters["label"] == "pyrolysis", "eff_out_1"].iloc[0]
    normed_syngas_output = converters.loc[converters["label"] == "pyrolysis", "eff_out_2"].iloc[0]
    normed_ratio = normed_syngas_output / normed_biochar_output

    bio_char_output = df_sequences["pyrolysis to b_biochar"]
    syngas_output = df_sequences["pyrolysis to b_syngas_hot"]
    ratio = bio_char_output.div(syngas_output) * normed_ratio
    ratio = ratio.replace([float("inf"), -float("inf")], pd.NA)

    df_additional_columns["gas_char_ratio"] = ratio

    return df_additional_columns


def calculate_variable_costs_per_flow_per_timestep(sequences, path_varcosts):
    """
    This function takes the result sequences (flows per timestep) and the variable costs
    from csv files and multiplies them. The results are returned as a dataframe.
    """
    varcosts = pd.read_csv(path_varcosts, sep=";", index_col=0)
    varcosts = varcosts.set_index(
        sequences.index[:-1]
    )  # -1 because the index in sequences in one time step longer than the data

    # Create a new dataframe with the same structure as the sequences dataframe
    # to store the cost sequences
    effective_variable_costs = pd.DataFrame(index=sequences.index, columns=sequences.columns)
    # Calculate the effective variable costs by multiplying the sequences with the variable costs
    for col in effective_variable_costs.columns:
        effective_variable_costs[col] = sequences[col] * varcosts[col]

    return effective_variable_costs


def calculate_sum_of_variable_costs_per_timestep(effective_variable_costs):
    effective_variable_costs["sum of variable costs"] = effective_variable_costs.sum(axis=1)
    return effective_variable_costs


def add_investment_amount_to_scalar_results(scalars, scalar_results, epcs):
    """
    Extract non-NaN-values from the scalars df and append them to the scalar results.
    The scalars df should be composed of the scalars of all flows taken from the raw results
    data: results[flow]["scalars"]
    """
    scalars = scalars.dropna(axis=1, how="all")
    dict = {}
    for columnName, columnData in scalars.items():
        dict[columnName] = columnData["invest"]
        # The unit depends on the flow. Flows going to None are in kWh, flows between buses
        # are in kW.
    # Separate the dict into two dicts, one for flows to None and one for flows between buses,
    # to assign the correct unit in the scalar results.
    flows_kWh = {key: value for key, value in dict.items() if key.endswith(" to None")}
    flows_kW = {key: value for key, value in dict.items() if not key.endswith(" to None")}
    scalar_results = helpers.add_items_to_scalar_results(
        flows_kWh, "built capacity [kWh]", scalar_results
    )
    scalar_results = helpers.add_items_to_scalar_results(
        flows_kW, "built capacity [kW]", scalar_results
    )

    investmentcost_dict = {}
    for key, value in dict.items():
        investmentcost_dict[key] = (
            dict[key] * epcs.loc[epcs["object"].apply(lambda x: key.startswith(x)), "value"].item()
        )
    scalar_results = helpers.add_items_to_scalar_results(
        investmentcost_dict,
        "equivalent periodical costs of investment [Euros]",
        scalar_results,
    )

    return scalar_results


def calculate_objective_value_with_exogenous_investment_costs(scalar_results, RESULTS):
    objective_value = scalar_results.loc[scalar_results["variable"] == "objective", "value"].item()
    exogenous_investment_costs = pd.read_csv(
        RESULTS / "exogenous_investment_costs.csv", sep=";", index_col=0
    )["investment_cost"].sum()
    base_value = objective_value + exogenous_investment_costs
    scalar_results = helpers.add_items_to_scalar_results(
        {"objective with exogenous investment costs": base_value},
        "objective [Euros]",
        scalar_results,
    )
    return scalar_results


def check_scalar_costs_consistency(scalar_results):
    """
    Check whether the sum of the monetary scalar results is equal to the objective variable
    and print a warning if not
    """
    print("Checking the completeness of the cost scalars")
    scalar_costs = helpers.filter_cost_items_from_scalar_data(scalar_results)
    objective = scalar_results.loc[
        scalar_results["variable"] == "objective with exogenous investment costs",
        "value",
    ].item()
    sum = scalar_costs.value.sum().item()
    assert type(sum - objective) is type(0.1), (
        "The data types are not coherent, a consistency check is not possible."
    )
    if abs(objective - sum) > 0.1:
        print(
            "Some cost or revenue scalars must be missing in the scalar results. "
            "The sum of the cost and revenue data is ",
            scalar_costs.value.sum(),
            "whereas the objective is ",
            objective,
            ". The difference of ",
            objective - sum,
            " will be added as undefined costs to the scalar results.",
        )
        scalar_results = helpers.add_items_to_scalar_results(
            {"unallocated costs": objective - sum},
            "sum of unallocated costs [Euros]",
            scalar_results,
        )
    else:
        print(
            "The cost scalars are consistent. The sum of the cost and revenue data is ",
            scalar_costs.value.sum(),
            "and the objective is ",
            objective,
            ".",
        )
    return scalar_results


def calculate_exogenous_investment_costs(sequences, storage_contents, scenario):
    # Calculates the investment costs for components with fixed investments,
    # assuming they have the size that would be necessary for peak production.
    results = []
    epcs = pd.read_csv(
        os.path.join(scenario_dumping_space_path(scenario), "epcs_from_optimization.csv"),
        sep=";",
    )
    storage = pd.read_excel(
        os.path.join(
            scenario_path(scenario),
            "meta_info",
            "input_preprocessed",
            "input_data_with_applied_policies.xlsx",
        ),
        sheet_name="storage",
    )
    converter = pd.read_excel(
        os.path.join(
            scenario_path(scenario),
            "meta_info",
            "input_preprocessed",
            "input_data_with_applied_policies.xlsx",
        ),
        sheet_name="converters",
    )

    for i, row in converter.iterrows():
        if not row.investment:
            matching_columns = [
                col
                for col in sequences.columns
                if row.label in col and col.endswith(f" to {row.bus_out_1}")
            ]
            if not matching_columns:
                raise ValueError(
                    f"No sequence column found for converter {row.label}ending with {row.bus_out_1}"
                )
            columnname_in_sequences = matching_columns[0]
            capacity = sequences[columnname_in_sequences].max()
            investment_cost = capacity * epcs.loc[epcs["object"] == row.label, "value"].item()
            results.append({"component": row.label, "investment_cost": investment_cost})
    for i, row in storage.iterrows():
        if not row.investment:
            columnname_in_storage_contents = row.label + " to None"
            capacity = storage_contents[columnname_in_storage_contents].max()
            investment_cost = capacity * epcs.loc[epcs["object"] == row.label, "value"].item()
            results.append({"component": row.label, "investment_cost": investment_cost})
    results = pd.DataFrame(results, columns=["component", "investment_cost"])
    scenario_results = scenario_results_path(scenario)
    results.to_csv(
        os.path.join(scenario_results, "exogenous_investment_costs.csv"),
        sep=";",
        index=False,
    )
    return results


def postprocess(dumping_space: Path | None = None, results: Path | None = None):

    # Read out the scenario from the input data
    input_data = read_raw_data("input_data.xlsx")
    scenario = (
        input_data["general"].loc[input_data["general"]["label"] == "scenario", "value"].item()
    )

    if dumping_space is None:
        dumping_space = scenario_dumping_space_path(scenario)
    if results is None:
        results = scenario_results_path(scenario)

    # Create a results folder if it doesn't exist yet
    results.mkdir(parents=True, exist_ok=True)

    es = EnergySystem()
    es.restore(dumping_space, "es_dump.oemof")

    epcs = pd.read_csv(
        os.path.join(dumping_space, "epcs_from_optimization.csv"), sep=";", index_col=0
    )

    # Create an empty dataframe for the scalar results:

    scalar_results = pd.DataFrame(columns=["variable", "type", "value"])

    # From the meta information, only the objective value is interesting for the results.
    # Store this value in the scalar results remove the meta part from the results:

    sequences, scalars, storage_contents, additional_columns = convert_result_sequences_to_df(
        results_data=es.results["main"]
    )
    additional_columns = gas_char_ratio(sequences, additional_columns, input_data["converters"])

    effective_variable_costs = calculate_variable_costs_per_flow_per_timestep(
        sequences,
        os.path.join(dumping_space, "variable_costs_from_model.csv"),
    )

    # Create scalar results
    scalar_results = add_objective_to_scalar_results(es.results, scalar_results)

    scalar_results = add_sums_to_scalar_results(sequences, "sum of flow", scalar_results)
    scalar_results = add_sums_to_scalar_results(
        effective_variable_costs,
        "sum of variable costs [Euros]",
        scalar_results,
    )

    scalar_results = add_investment_amount_to_scalar_results(scalars, scalar_results, epcs)

    exogeneous_investment_costs = calculate_exogenous_investment_costs(
        sequences, storage_contents, scenario
    )

    # Add exogenous investment costs to scalar results
    costs_dict = {}
    for _, row in exogeneous_investment_costs.iterrows():
        key = row["component"]
        costs_dict[key] = row["investment_cost"]
    scalar_results = helpers.add_items_to_scalar_results(
        costs_dict, "ep_costs for existing capacity [Euros]", scalar_results
    )

    scalar_results = calculate_objective_value_with_exogenous_investment_costs(
        scalar_results, results
    )

    result_dfs = {
        "sequences": sequences,
        "storage_contents": storage_contents,
        "effective_variable_costs": effective_variable_costs,
        "scalar_results": scalar_results,
        "additional_columns": additional_columns,
    }

    result_dfs["scalar_results"] = check_scalar_costs_consistency(result_dfs["scalar_results"])

    # Save all results
    for key, df in result_dfs.items():
        df.to_csv(os.path.join(results, f"{key}.csv"), sep=";")
    print("The postprocessing is finished and the results have been saved.")

    log_postprocessed_policies(input_data, scenario)

    return result_dfs


if __name__ == "__main__":
    postprocess()
