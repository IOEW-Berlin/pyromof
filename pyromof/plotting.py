import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from oemof.solph import EnergySystem
from plotly.subplots import make_subplots

from pyromof import helpers
from pyromof.paths import (
    scenario_dumping_space_path,
    scenario_meta_info_path,
    scenario_results_path,
)


def prepare_amount_sequences_for_plotting(RESULTS):
    """
    Reads the csv file with the sequences from the optimization results and splits it into
    2 according to the unit of the flows.
    # TODO: Save input data in optimize.py and retrieve units from the input data
    # instead of specifying them in the script.
    """
    amount_sequences = pd.read_csv(
        os.path.join(RESULTS, "sequences.csv"),
        sep=";",
        index_col=0,
        parse_dates=True,
    )
    units = {
        "b_biochar": "kg",
        "b_co2": "kg",
        "b_electricity": "kWh",
        "b_electricity_2": "kWh",
        "b_heat_ht": "kWh",
        "b_heat_lt": "kWh",
        "b_oil": "kg",
        "b_biomass": "kg",
        "b_biomass_dry": "kg",
        "b_heat_mt": "kWh",
        "b_syngas_hot": "kWh",
        "b_syngas_cold": "kWh",
        "b_h2": "kWh",
        "b_valuable_biochar": "kg",
    }

    sequences_in_kg = pd.DataFrame(index=amount_sequences.index)
    sequences_in_kWh = pd.DataFrame(index=amount_sequences.index)
    for flow in amount_sequences.columns:
        bus = helpers.filter_bus_in_string(flow)
        if bus not in units.keys():
            print(
                "The unit for "
                + flow
                + " is not defined. Therefore it will not be plotted in "
                + "the amount sequences."
            )
        elif units[bus] == "kg":
            sequences_in_kg[flow] = amount_sequences[flow]
        elif units[bus] == "kWh":
            sequences_in_kWh[flow] = amount_sequences[flow]
        else:
            print(
                "The unit for "
                + flow
                + " is neither kg nor kWh. Therefore it will not be plotted "
                + "in the amount sequences."
            )
    return sequences_in_kg, sequences_in_kWh


def plot_amount_sequences(sequences_in_kg, sequences_in_kWh, scenario, RESULTS):
    """
    Takes two dataframes, one with flow sequences in tonnes and one in kWh,
    and plots them as line plots one below the other.
    """
    fig = make_subplots(rows=2, cols=1)

    for col in sequences_in_kg.columns:
        fig.add_trace(
            go.Scatter(
                x=sequences_in_kg.index,
                y=sequences_in_kg[col],
                mode="lines",
                line=dict(dash="solid"),
                name=col,
            ),
            row=1,
            col=1,
        )
    for col in sequences_in_kWh.columns:
        fig.add_trace(
            go.Scatter(
                x=sequences_in_kWh.index,
                y=sequences_in_kWh[col],
                mode="lines",
                line=dict(dash="solid"),
                name=col,
            ),
            row=2,
            col=1,
        )

    fig.update_yaxes(title_text="kg/hour", row=1)
    fig.update_yaxes(title_text="kWh/hour", row=2)
    fig.update_layout(hoverlabel_namelength=-1)
    fig.write_html(os.path.join(RESULTS, "amount_sequences_{}.html".format(scenario)))


def prepare_cost_sequences_for_plotting(RESULTS):
    """
    Reads the csv files of time-variable cost data, selects the columns
    that contain non-0 data and stores them in
    a dictionary of dataframes, sorted by the cost type (e.g. variable costs, start-up costs)
    """
    # Create a dictionary to hold the dataframes:
    df_dict = {}
    varcosts = pd.read_csv(
        os.path.join(RESULTS, "effective_variable_costs.csv"),
        sep=";",
        index_col=0,
        parse_dates=True,
    )
    # Remove all columns where all values are 0
    varcosts = varcosts.loc[:, varcosts.any()]
    varcosts = varcosts * -1
    df_dict["variable costs"] = varcosts
    # When more types of variable costs occur, the code for converting
    # them in dfs ready for plotting should be added here:
    return df_dict


def plot_cost_sequences(df_dict, scenario, RESULTS):
    """
    Takes a dictionary of dataframes and plots them, each with a different line style.
    """
    dashtypes = [
        "solid",
        "dot",
        "dash",
        "longdash",
        "dashdot",
        "longdashdot",
    ]  # also possible: dash length list
    fig = go.Figure()
    dashtypenumber = 0
    for df in df_dict.values():
        # Loop df columns and plot columns to the figure
        for col in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[col],
                    mode="lines",
                    line=dict(dash=dashtypes[dashtypenumber]),  # dash='dash'
                    name=col,
                )
            )
        dashtypenumber = dashtypenumber + 1
    fig.update_layout(yaxis=dict(title="Euros/hour"))
    fig.write_html(os.path.join(RESULTS, "cost_sequences_{}.html".format(scenario)))


def plot_cost_scalars(scalcosts, scenario, RESULTS):
    total = scalcosts[scenario].sum()

    fig = px.bar(scalcosts, x="type", y=scenario, color="variable", barmode="stack")

    # Add point for total
    fig.add_trace(
        go.Scatter(
            x=["total"],
            y=[total],
            mode="markers",
            marker_symbol="diamond",
            marker_color="black",
            marker=dict(size=15),
            hoverinfo="text+y",
            text=["Sum of cash flow and epc"],
            name="Total",
        )
    )

    # Plot negative values below the x-axis
    fig.update_layout(barmode="relative")
    # Save plot as html
    fig.write_html(os.path.join(RESULTS, "cost_scalars_{}.html".format(scenario)))


def plot_storage_content(storage_content, scenario, RESULTS):
    # Creates a line plot with the storage content over time for each storage type
    fig = go.Figure()
    for col in storage_content.columns:
        fig.add_trace(
            go.Scatter(
                x=storage_content.index,
                y=storage_content[col],
                mode="lines",
                line=dict(dash="solid"),
                name=col,
            )
        )
    fig.write_html(os.path.join(RESULTS, "storage_content_{}.html".format(scenario)))


def plot_demand_and_revenue_for_elec_and_heat(profiles, sinks, scenario, RESULTS):
    # Creates a line plot with the demand and revenue for electricity and heat over time
    if "sliding_premium_profile" in profiles.columns:
        profile_column = profiles["sliding_premium_profile"]
    else:
        profile_column = profiles[sinks.loc["electricity_grid", "variable_costs"]]
    fig = make_subplots(rows=2, cols=1)

    fig.add_trace(
        go.Scatter(
            x=profiles.index,
            y=profile_column,
            mode="lines",
            line=dict(dash="solid"),
            name="Electricity revenue",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=profiles.index,
            y=profiles["heat_village"],
            mode="lines",
            line=dict(dash="solid"),
            name="Heat demand",
        ),
        row=2,
        col=1,
    )

    fig.update_yaxes(title_text="EUR/kWh", row=1)
    fig.update_yaxes(title_text="kWh/hour", row=2)
    fig.update_layout(hoverlabel_namelength=-1)
    fig.write_html(os.path.join(RESULTS, "demand_and_revenue_{}.html".format(scenario)))


def plot(scenario, RESULTS):
    df_dict = prepare_cost_sequences_for_plotting(RESULTS)
    plot_cost_sequences(df_dict, scenario, RESULTS)
    scalcosts = helpers.prepare_cost_scalars_for_plotting(RESULTS, "scalar_results.csv", scenario)
    plot_cost_scalars(scalcosts, scenario, RESULTS)
    sequences_in_kg, sequences_in_kWh = prepare_amount_sequences_for_plotting(RESULTS)
    plot_amount_sequences(sequences_in_kg, sequences_in_kWh, scenario, RESULTS)
    storage_contents = pd.read_csv(
        os.path.join(RESULTS, "storage_contents.csv"),
        sep=";",
        index_col=0,
        parse_dates=True,
    )
    plot_storage_content(storage_contents, scenario, RESULTS)
    meta_info_dir = scenario_meta_info_path(scenario)
    input_data_path = meta_info_dir / "input_preprocessed" / "input_data_with_applied_policies.xlsx"
    profiles = pd.read_excel(input_data_path, sheet_name="profiles", index_col=0, parse_dates=True)
    sinks = pd.read_excel(input_data_path, sheet_name="sinks", index_col=0)
    plot_demand_and_revenue_for_elec_and_heat(profiles, sinks, scenario, RESULTS)


def plot_sequences_and_scalars():
    general = pd.read_excel("input_data.xlsx", sheet_name="general")
    scenario = general.loc[general["label"] == "scenario", "value"].item()

    RESULTS = scenario_results_path(scenario)
    DUMPING_SPACE = scenario_dumping_space_path(scenario)

    es = EnergySystem()
    es.restore(DUMPING_SPACE, "es_dump.oemof")
    scenario = helpers.retreive_scenario_from_results(es)
    plot(scenario, RESULTS)


if __name__ == "__main__":
    plot_sequences_and_scalars()
