import pandas as pd
from typeguard import typechecked


def read_raw_data(relative_file_path):
    return {
        "profiles": pd.read_excel(relative_file_path, sheet_name="profiles"),
        "sinks": pd.read_excel(relative_file_path, sheet_name="sink"),
        "sources": pd.read_excel(relative_file_path, sheet_name="source"),
        "converters": pd.read_excel(relative_file_path, sheet_name="converter"),
        "storage": pd.read_excel(relative_file_path, sheet_name="storage"),
        "general": pd.read_excel(relative_file_path, sheet_name="general"),
        "policies": pd.read_excel(relative_file_path, sheet_name="policies"),
    }


@typechecked
def define_time_period(general: pd.DataFrame) -> pd.DatetimeIndex:
    # Definition of the time period
    start_time = general.loc[general["label"] == "start_time", "value"].item()
    end_time = general.loc[general["label"] == "end_time", "value"].item()
    time = pd.date_range(start=start_time, end=end_time, freq="h", inclusive="both")
    return time


def slice_time_period_from_profiles(profiles: pd.DataFrame, time: pd.DatetimeIndex) -> pd.DataFrame:
    # Slice the time period from profiles
    profiles["timeindex"] = pd.to_datetime(profiles["timeindex"])
    profiles = profiles[profiles["timeindex"].isin(time)]
    profiles = profiles.set_index("timeindex")
    return profiles


@typechecked
def retrieve_scenario_from_input_data(general_df: pd.DataFrame) -> str:
    scenario = general_df.loc[general_df["label"] == "scenario", "value"].item()
    return scenario


@typechecked
def matches_scenario(scenario_to_check: str, scenario_wanted: str) -> bool:
    """
    Checks wether the string "scenario to check" is either "all" or
    includes the "scenario_wanted".
    "scenario_wanted" should be the scenario to be optimized,
    and "scenario_to_check" a scenario field
    from the input data.
    """
    return scenario_to_check == "all" or scenario_wanted in scenario_to_check


@typechecked
def filter_input_data_by_scenario(
    data: dict[str, pd.DataFrame],
    scenario_wanted: str,
):
    dfs = ["sinks", "sources", "converters", "storage"]
    # Filter sheets listed in dfs by scenario and leave the others unchanged
    data = {
        name: df[df["scenario"].apply(matches_scenario, args=(scenario_wanted,))]
        if name in dfs
        else df
        for name, df in data.items()
    }
    return data


def validate_input_data_column_types(input_file):
    """
    Checks whether the columns of the input data sheets contain the expected data types.
    The expected data type of a column is determined by the rules below in this order:
    1. prefix_rules: columns starting with a certain prefix (e.g. bus_in_1, eff_out_2)
    2. common_rules: columns that have the same name and meaning in all sheets
    3. sheet_rules: all other columns, listed explicitly for each sheet
    Columns that are not covered by any rule (e.g. unit, comment) and columns that are
    completely empty are not checked. The sheet "profiles" has its own rule (profiles_rule).
    All errors are printed grouped by sheet and column, then a ValueError is raised.
    """

    prefix_rules = {"bus_": "str", "eff_": "numeric"}

    common_rules = {"scenario": "str|list[str]", "label": "str"}

    # The sheet "general" consists of the columns label and value and is checked row-wise.
    sheet_rules = {
        "general": {
            "wacc": "numeric",
            "scenario": "str",
            "start_time": "datetime",
            "end_time": "datetime",
        },
        "sink": {
            "nominal_capacity": "numeric",
            "min": "numeric|str",
            "max": "numeric|str",
            "variable_costs": "numeric|str",
        },
        "source": {
            "nominal_capacity": "numeric",
            "total_availability": "numeric",
            "min": "numeric|str",
            "max": "numeric|str",
            "capex": "numeric",
            "lifetime": "numeric",
            "variable_costs": "numeric",
        },
        "converter": {
            "nominal_capacity": "numeric",
            "min_load_share": "numeric",
            "minimum_downtime": "numeric",
            "maximum_startups": "numeric",
            "initial_status": "numeric",
            "startup_costs": "numeric",
            "positive_gradient_limit": "numeric",
            "capex": "numeric|str",
            "offset": "numeric",
            "lifetime": "numeric",
            "minimum": "numeric",
            "maximum": "numeric|str",
            "investment": "bool",
        },
        "storage": {
            "loss_rate": "numeric|str",
            "inflow_conversion_factor": "numeric",
            "outflow_conversion_factor": "numeric",
            "nominal_storage_capacity": "numeric",
            "charge_rate": "numeric",
            "initial_storage_level": "numeric",
            "capex": "numeric",
            "lifetime": "numeric",
            "maximum": "numeric",
            "investment": "bool",
        },
    }

    # The column names in the sheet "profiles" are profile names that can be chosen freely
    # so they cannot be listed. All columns except the excluded ones must be numeric.
    profiles_rule = {"exclude": ["timeindex"], "dtype": "numeric"}

    # Descriptions of the data types and hints on how to fix a wrong entry for the error messages
    type_descriptions = {
        "str": "text",
        "numeric": "a number",
        "bool": "TRUE or FALSE",
        "datetime": "a date with time",
        "numeric|str": "a number or a profile name",
        "str|list[str]": "text or a comma-separated list of texts",
    }
    type_hints = {
        "str": (
            "Enter text. If a name consists only of digits (e.g. a scenario called 2030), "
            "add letters (e.g. S2030) or format the cell as text in Excel."
        ),
        "numeric": (
            "Enter a number without units or placeholders like '-'. "
            "Leave the cell empty if there is no value."
        ),
        "bool": "Enter TRUE or FALSE",
        "datetime": (
            "Enter a date with time in the format YYYY-MM-DD hh:mm, e.g. 2025-01-01 00:00."
        ),
        "numeric|str": (
            "Enter a number or the name of a column in the sheet 'profiles'. "
            "Several profile names can be separated by commas."
        ),
        "str|list[str]": "Enter text or a comma-separated list of texts, e.g. PyGas_CHP, Py_ORC.",
    }

    # Errors are collected per sheet and column so that the hint is printed only once
    errors = {}

    # Only the first errors per column are printed to keep the output readable
    max_errors_per_column = 5

    # Helper functions for the validation

    def infer_dtype(sheet, col):
        """
        Returns the expected data type of a column according to the rules above
        or None if the column is not checked.
        """
        if sheet == "profiles":
            return None if col in profiles_rule["exclude"] else profiles_rule["dtype"]
        for prefix, dtype in prefix_rules.items():
            if str(col).startswith(prefix):
                return dtype
        if col in common_rules:
            return common_rules[col]
        return sheet_rules.get(sheet, {}).get(col)

    def check_value(value, dtype, profile_names):
        """
        Checks a single value against the expected data type. Returns None if the value
        is valid, otherwise a short description of the problem.
        """
        if dtype in ("str", "str|list[str]"):
            valid = isinstance(value, str)
        elif dtype == "numeric":
            valid = isinstance(value, (int, float))
        elif dtype == "bool":
            valid = isinstance(value, bool)
        elif dtype == "datetime":
            valid = not pd.isna(pd.to_datetime(value, errors="coerce"))
        elif dtype == "numeric|str":
            if isinstance(value, str):
                missing = [p.strip() for p in value.split(",") if p.strip() not in profile_names]
                if missing:
                    return f"profile {', '.join(missing)} not found in the sheet 'profiles'"
                return None
            valid = isinstance(value, (int, float))
        else:
            raise ValueError(f"Unknown data type '{dtype}' in validate_input_data_column_types")
        if valid:
            return None
        return f"found {value!r}, expected {type_descriptions[dtype]}"

    def add_error(sheet, heading, dtype, idx, label, problem):
        # Adds an error message for cells with a wrong type, grouped by sheet and column.
        # The row number is increased by 2 to account for the header and 0-based indexing.
        row = f"row {idx + 2}" if label is None else f"row {idx + 2} (label '{label}')"
        errors.setdefault((sheet, heading, dtype), []).append(f"{row}: {problem}")

    try:
        profiles_df = pd.read_excel(input_file, sheet_name="profiles")
        profile_names = [str(c) for c in profiles_df.columns if c not in profiles_rule["exclude"]]
    except ValueError:
        profile_names = []

    # initiate loop for column type validation
    for sheet in [*sheet_rules, "profiles"]:
        try:
            df = pd.read_excel(input_file, sheet_name=sheet)
        except ValueError:
            errors[(sheet, None, None)] = [f"The sheet '{sheet}' could not be found."]
            continue

        # row-wise validation for "general" sheet
        if sheet == "general":
            for idx, row in df.iterrows():
                dtype = sheet_rules["general"].get(row["label"])
                if dtype is None or pd.isna(row["value"]):
                    continue
                problem = check_value(row["value"], dtype, profile_names)
                if problem:
                    add_error(sheet, f"value of '{row['label']}'", dtype, idx, None, problem)
            continue

        # skip empty columns and columns without rule, create error messages
        for col in df.columns:
            dtype = infer_dtype(sheet, col)
            if dtype is None or df[col].isna().all():
                continue
            for idx, value in df[col].dropna().items():
                problem = check_value(value, dtype, profile_names)
                if problem:
                    has_label = "label" in df.columns and col != "label"
                    label = df.at[idx, "label"] if has_label else None
                    add_error(sheet, f"column '{col}'", dtype, idx, label, problem)

    if errors:
        print(f"\nThe input data in '{input_file}' contains the following errors:")
        for (sheet, heading, dtype), messages in errors.items():
            print(f"\nSheet '{sheet}'" + (f", {heading}:" if heading else ":"))
            for message in messages[:max_errors_per_column]:
                print(f"  - {message}")
            if len(messages) > max_errors_per_column:
                print(f"  ... and {len(messages) - max_errors_per_column} more rows")
            if dtype:
                print(f"  How to fix: {type_hints[dtype]}")
                if dtype == "numeric|str":
                    print(f"  Available profiles: {', '.join(profile_names)}")
        print(
            "\nThe expected data types are defined in the function "
            "validate_input_data_column_types in "
            "pyromof/preprocessing_functions/preprocessing_input_data.py."
        )
        raise ValueError("The input data validation failed. See the list of errors above.")
    else:
        print("All types valid.")


def preprocess(relative_file_path):
    data = read_raw_data(relative_file_path)
    time = define_time_period(data["general"])
    data["profiles"] = slice_time_period_from_profiles(data["profiles"], time)
    scenario = retrieve_scenario_from_input_data(data["general"])
    data = filter_input_data_by_scenario(data, scenario)
    validate_input_data_column_types(relative_file_path)
    return data, time, scenario


if __name__ == "__main__":
    data, time = preprocess("input_data.xlsx")
