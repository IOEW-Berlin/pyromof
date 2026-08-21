from pyromof.preprocessing_functions.define_input_data_functions import (
    calculate_ep_costs_for_all_components,
    define_time_period,
    filter_input_data_by_scenario,
    read_raw_data,
    retrieve_scenario_from_input_data,
    slice_time_period_from_profiles,
)
from pyromof.preprocessing_functions.implement_policies import implement_policies


def preprocess(relative_file_path="input_data.xlsx"):

    data = read_raw_data(relative_file_path)
    time = define_time_period(data["general"])
    data["profiles"] = slice_time_period_from_profiles(data["profiles"], time)
    scenario = retrieve_scenario_from_input_data(data["general"])
    data = filter_input_data_by_scenario(data, scenario)
    data = implement_policies(data, scenario)
    epcs = calculate_ep_costs_for_all_components(data, time)
    return data, time, scenario, epcs


if __name__ == "__main__":
    data, time = preprocess("input_data.xlsx")
