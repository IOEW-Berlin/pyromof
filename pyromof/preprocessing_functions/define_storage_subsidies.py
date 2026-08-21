from pyromof.preprocessing_functions.define_input_data_functions import read_raw_data


def implement_storage_subsidies(data, active_policies):

    subsidy_configs = {
        "lump_sum": {
            "electricity_storage": "Subsidy for electricity storage: lump sum",
            "heat_storage": "Subsidy for heat storage: lump sum",
            "h2_storage": "Subsidy for hydrogen storage: lump sum",
            "syngas_storage": "Subsidy for syngas storage: lump sum",
        },
        "percentage": {
            "electricity_storage": "Subsidy for electricity storage: percentage",
            "heat_storage": "Subsidy for heat storage: percentage",
            "h2_storage": "Subsidy for hydrogen storage: percentage",
            "syngas_storage": "Subsidy for syngas storage: percentage",
        },
    }

    for storage_label, policy_name in subsidy_configs["lump_sum"].items():
        if policy_name not in active_policies:
            continue

        subsidy = active_policies[policy_name]

        mask = data["storage"]["label"] == storage_label
        data["storage"].loc[mask, "capex"] -= subsidy

    for storage_label, policy_name in subsidy_configs["percentage"].items():
        if policy_name not in active_policies:
            continue

        percentage = active_policies[policy_name]
        subsidy_factor = 1 - (percentage / 100)

        storage_subsidy = data["storage"]["label"] == storage_label
        data["storage"].loc[storage_subsidy, "capex"] *= subsidy_factor

    return data["storage"]


if __name__ == "__main__":
    data = read_raw_data("input_data.xlsx")
    active_policies = (
        data["policies"]
        .loc[data["policies"]["activate"] == "x", ["policy", "value 1"]]
        .set_index("policy")["value 1"]
        .to_dict()
    )
    implement_storage_subsidies(data, active_policies)
