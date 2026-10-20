import matplotlib.pyplot as plt
import pandas as pd

from pyromof.paths import scenario_results_path


def get_data_csv(scenario: str) -> pd.DataFrame:
    """Read data from CSV file of the chosen scenario."""
    file_path = scenario_results_path(scenario) / "sequences.csv"
    separator = ";"
    parse_dates = True
    target_columns = [
        "b_electricity to electricity_grid",
        "b_biomass_dry to pyrolysis",
    ]

    data = pd.read_csv(file_path, sep=separator, parse_dates=parse_dates)
    return data[target_columns]


def sort_values_descending(df: pd.DataFrame, column: str) -> pd.Series:
    """Sort values in descending order."""
    s = pd.to_numeric(df[column])
    return s.sort_values(ascending=False)


def create_plot(sorted_column, xlabel, ylabel, title, save_path):
    """Plot the load duration curve."""
    plt.figure(figsize=(10, 6))
    plt.plot(range(len(sorted_column)), sorted_column.values)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    plt.savefig(save_path)
    plt.close()


def plot_load_duration_curves(scenario=None):
    """Execute the load duration curve generation."""
    general = pd.read_excel("input_data.xlsx", sheet_name="general")
    scenario = general.loc[general["label"] == "scenario", "value"].item()

    columns = get_data_csv(scenario)

    descending_power_data = sort_values_descending(columns, "b_electricity to electricity_grid")
    descending_biomass_data = sort_values_descending(columns, "b_biomass_dry to pyrolysis")

    create_plot(
        sorted_column=descending_power_data,
        xlabel="Hours",
        ylabel="Electricity feed-in (kWh)",
        title=f"Scenario {scenario}: Load duration curve - Power",
        save_path=scenario_results_path(scenario) / "load_duration_curve_power.png",
    )
    create_plot(
        sorted_column=descending_biomass_data,
        xlabel="Hours",
        ylabel="Biomass input (kg)",
        title=f"Scenario {scenario}: Load duration curve - Biomass",
        save_path=scenario_results_path(scenario) / "load_duration_curve_biomass.png",
    )
