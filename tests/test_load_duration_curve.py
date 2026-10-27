import matplotlib

matplotlib.use("Agg")
import pandas as pd

from pyromof.load_duration_curve import (
    get_data_csv,
    plot_load_duration_curves,
    sort_values_descending,
)


def test_sort_values_descending():
    """Test that values are sorted in descending order."""
    df = pd.DataFrame({"col": [3, 1, 2]})
    sorted_column = sort_values_descending(df, "col")
    assert list(sorted_column.values) == [3, 2, 1]


def test_plot_load_duration_curve(tmp_path):
    """Test that plot is saved to file."""
    column = pd.Series([3, 2, 1])
    save_path = tmp_path / "test_plot.png"
    plot_load_duration_curves(column, "x-title", "y-title", "title", str(save_path))
    assert save_path.exists()


def test_get_data_csv(tmp_path, monkeypatch):
    """Test get_data_csv with mock data."""
    monkeypatch.chdir(tmp_path)

    scenario_dir = tmp_path / "results" / "test_scenario" / "results"
    scenario_dir.mkdir(parents=True)

    csv_file = scenario_dir / "sequences.csv"
    test_data = pd.DataFrame(
        {
            "b_electricity to electricity_grid": [1, 2, 3],
            "b_biomass_dry to pyrolysis": [4, 5, 6],
        }
    )
    test_data.to_csv(csv_file, sep=";", index=False)

    result = get_data_csv("test_scenario")
    assert result.shape == (3, 2)
