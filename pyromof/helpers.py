import os
import re
from pathlib import Path

import pandas as pd
from typeguard import typechecked


@typechecked
def define_and_create_folders(ROOT_PATH: Path, scenario: str):
    RESULTS = Path(os.path.join(ROOT_PATH, "results"))
    # Create folder for the scenario within the results folder if it doesn't exist yet
    Path(os.path.join(RESULTS, scenario)).mkdir(exist_ok=True)
    SCENARIO_PATH = Path(os.path.join(RESULTS, scenario))
    # Create folders for meta_info and dumping_space
    Path(os.path.join(SCENARIO_PATH, "meta_info")).mkdir(exist_ok=True)
    META_INFO = Path(os.path.join(SCENARIO_PATH, "meta_info"))
    Path(os.path.join(SCENARIO_PATH, "dumping_space")).mkdir(exist_ok=True)
    DUMPING_SPACE = Path(os.path.join(SCENARIO_PATH, "dumping_space"))
    return SCENARIO_PATH, META_INFO, DUMPING_SPACE


def check_type(object, type_wanted):
    if not isinstance(object, type_wanted):
        raise TypeError("Expected {0}; got {1}".format(type_wanted, type(object).__name__))


def retreive_scenario_from_results(es):
    scenario = es.results["scenario"]
    return scenario


def convert_tuple_columnnames_to_strings(df):
    df.columns = [" to ".join(x) for x in df.columns]
    return df


def filter_cost_items_from_scalar_data(scalar_data):
    filtered = scalar_data[
        (~scalar_data["type"].str.contains("objective \\[Euros\\]", regex=True))
        & scalar_data["type"].str.contains("Euros", regex=False)
    ]
    return filtered


def prepare_cost_scalars_for_plotting(folder_name, file_name, scenario):
    """
    Reads in the scalars from a csv file, filters for cost components and multiplies by -1
    """
    scalar_data = pd.read_csv(os.path.join(folder_name, file_name), sep=";", index_col=0)
    scalcosts = filter_cost_items_from_scalar_data(scalar_data).copy()
    scalcosts.loc[:, scenario] = scalcosts.loc[:, "value"] * -1
    scalcosts.drop("value", axis=1, inplace=True)
    # TODO: Differentiate between annuity, epc and upfront investment costs and
    # clarify in the plot what is meant
    return scalcosts


def filter_bus_in_string(string):
    pattern = r"b_[^ ]+"  # Matches 'b_' followed by one or more non-space characters
    match = re.search(pattern, string)
    return match.group(0) if match else None


def add_items_to_scalar_results(dictionary: dict, type: str, scalar_results):
    """
    This functions adds given data to an existing dataframe with scalar results.
    The existing dataframe must have the columns "variable", "type" and "value".
    The input dict must contain the variable and value for each item. The type
    must be valid for all items in the dictionary.
    """
    new_df = pd.DataFrame(
        {
            "variable": list(dictionary.keys()),
            # Insert the given type for all new rows:
            "type": [type] * len(dictionary),
            "value": list(dictionary.values()),
        }
    )
    return pd.concat([scalar_results, new_df], ignore_index=True)
