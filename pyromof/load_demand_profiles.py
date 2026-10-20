import datetime

import pandas as pd
from demandlib import bdew

from pyromof.paths import PREPROCESSING_DIR


def load_demand_profiles():
    # read example temperature series
    filename = "Lufttemperatur_2024_DWD.csv"
    datapath = PREPROCESSING_DIR / filename

    temperature = pd.read_csv(datapath, sep=";")["TT_TU"]
    temperature = temperature.mask((temperature < -50) | (temperature > 50))
    temperature = temperature.interpolate()  # interpolate NA values

    # Annual heat demands for medium-sized German municipality (~20,000 inhabitants)
    # Assumptions: ~6,000 households, building mix typical for German municipality
    ann_demands_per_type = {
        "efh": 6000 * 18000,  # Single family homes: 6,000 units × 18 MWh/year
        "mfh": 2000 * 35000,  # Multi-family homes: 2,000 units × 35 MWh/year
        "ghd": 1 * 5000000,  # Commercial/service sector: 5 GWh/year
    }

    # Create DataFrame for 2024
    demand = pd.DataFrame(
        index=pd.date_range(datetime.datetime(2024, 1, 1, 0), periods=8784, freq="h")
    )

    # Single family house (efh: Einfamilienhaus)
    demand["efh"] = bdew.HeatBuilding(
        demand.index,
        temperature=temperature,
        shlp_type="EFH",
        building_class=2,
        wind_class=0,
        annual_heat_demand=ann_demands_per_type["efh"],
        name="EFH",
    ).get_normalized_bdew_profile()

    # Multi family house (mfh: Mehrfamilienhaus)
    demand["mfh"] = bdew.HeatBuilding(
        demand.index,
        temperature=temperature,
        shlp_type="MFH",
        building_class=2,
        wind_class=0,
        annual_heat_demand=ann_demands_per_type["mfh"],
        name="MFH",
    ).get_normalized_bdew_profile()

    # General commercial and service sector (ghd: Gewerbe, Handel, Dienstleistungen)
    demand["ghd"] = bdew.HeatBuilding(
        demand.index,
        temperature=temperature,
        shlp_type="GHD",
        building_class=0,
        wind_class=0,
        annual_heat_demand=ann_demands_per_type["ghd"],
        name="GHD",
    ).get_normalized_bdew_profile()

    # Calculate total heat demand
    demand["total"] = demand["efh"] + demand["mfh"] + demand["ghd"]

    demand.to_csv(PREPROCESSING_DIR / "heat_profile.csv")
