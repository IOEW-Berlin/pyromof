import os
import shutil
from pathlib import Path
from typing import Tuple

import pandas as pd
from oemof import solph
from oemof.network.graph import create_nx_graph
from pyomo.environ import Binary, Constraint, Set, Var
from typeguard import typechecked

from pyromof import helpers, postprocessing
from pyromof.paths import ROOT_PATH
from pyromof.preprocessing_functions.implement_input_data_functions import preprocess


@typechecked
def extract_components_and_buses_from_input_data(
    sinks: pd.DataFrame,
    sources: pd.DataFrame,
    converters: pd.DataFrame,
    storage: pd.DataFrame,
):
    """
    Takes the dfs from the input data sheets and the selected scenario and extracts
    (1) the components included in the scenario and (2) the buses which are connected
    to these components. The buses are returned as a dataframe with one column named
    "label" and the components are returned as a list.
    """

    # Create component list for the selected scenario
    components = (
        sinks["label"].tolist()
        + sources["label"].tolist()
        + converters["label"].tolist()
        + storage["label"].tolist()
    )

    # Create list of unique buses for the selected scenario
    buses = (
        sinks["bus_in"].tolist()
        + sources["bus_out"].tolist()
        + converters[
            [
                "bus_in_1",
                "bus_in_1_alternative",
                "bus_in_2",
                "bus_out_1",
                "bus_out_2",
                "bus_out_3",
            ]
        ]
        .stack()
        .tolist()
        + storage[["bus_in", "bus_out"]].stack().tolist()
    )
    # Filter unique values
    buses = set(buses)
    # Convert back to list
    buses = list(buses)
    # Convert to dataframe
    buses_df = pd.DataFrame(data={"label": buses})
    return buses_df, components


@typechecked
def create_energysystem(
    META_INFO,
    data: dict[str, pd.DataFrame],
    time,
    epcs: dict[str, float],
) -> Tuple[solph.EnergySystem, solph.Model]:

    profiles = data["profiles"]
    sinks = data["sinks"]
    sources = data["sources"]
    converters = data["converters"]
    storage = data["storage"]

    # Model definition
    es = solph.EnergySystem(timeindex=time)

    buses, components = extract_components_and_buses_from_input_data(
        sinks, sources, converters, storage
    )

    if "combustor" in components:
        buses.loc[len(buses.index)] = ["b_combustor_cap"]

    # Create Bus objects from buses table

    print("Adding the following buses to the energy system:")
    print(buses.label.tolist())

    nodes = []
    busd = {}

    for i, b in buses.iterrows():
        bus = solph.Bus(label=b["label"])
        nodes.append(bus)
        busd[b["label"]] = bus
        es.add(bus)

    # Create other components
    print("Adding the following components to the energysystem ")
    print(components)

    def get_value_or_profile(row, column_name, profiles):
        value = row[column_name].item()
        return profiles[value] if isinstance(value, str) else value

    # SINKS
    if "biochar_market" in components:
        row = sinks.loc[sinks.label == "biochar_market", :]

        biochar_market = solph.components.Sink(
            label="biochar_market",
            inputs={
                busd[row.bus_in.item()]: solph.Flow(variable_costs=row.variable_costs.item()),
            },
        )
        es.add(biochar_market)

    if "co2_market" in components:
        row = sinks.loc[sinks.label == "co2_market", :]
        co2_market = solph.components.Sink(
            label="co2_market",
            inputs={
                busd[row.bus_in.item()]: solph.Flow(
                    # nominal_capacity=row.nominal_capacity.item(),
                    # min=row["min"].item(),
                    # max=row["max"].item(),
                    variable_costs=row.variable_costs.item(),
                )
            },
        )
        es.add(co2_market)

    if "electricity_grid" in components:
        row = sinks.loc[sinks.label == "electricity_grid", :]
        subsidy_row = sinks.loc[sinks.label == "electricity_grid_subsidy"]
        active_policies = (
            data["policies"]
            .loc[data["policies"]["activate"] == "x", ["policy", "value 1"]]
            .set_index("policy")["value 1"]
            .to_dict()
        )

        electricity_grid = solph.components.Sink(
            label="electricity_grid",
            inputs={
                busd[row.bus_in.item()]: solph.Flow(
                    nominal_capacity=row.nominal_capacity.item(),
                    variable_costs=get_value_or_profile(row, "variable_costs", profiles),
                )
            },
        )
        subsidy_specs = {
            "nominal_capacity": row.nominal_capacity.item(),
            "variable_costs": get_value_or_profile(subsidy_row, "variable_costs", profiles),
        }

        if "limitation of subsidized full load hours" in active_policies:
            subsidy_specs["full_load_time_max"] = float(
                active_policies["limitation of subsidized full load hours"]
            )

        electricity_premium = solph.components.Sink(
            label="electricity_grid_subsidy",
            inputs={busd[row.bus_in.item()]: solph.Flow(**subsidy_specs)},
        )
        es.add(electricity_grid, electricity_premium)

    if "heat_demand_mt" in components:
        row = sinks.loc[sinks.label == "heat_demand_mt", :]
        heat_demand_ht = solph.components.Sink(
            label="heat_demand_mt",
            inputs={
                busd[row.bus_in.item()]: solph.Flow(
                    nominal_capacity=row.nominal_capacity.item(),
                    min=get_value_or_profile(row, "min", profiles),
                    max=get_value_or_profile(row, "max", profiles),
                    variable_costs=get_value_or_profile(row, "variable_costs", profiles),
                )
            },
        )
        es.add(heat_demand_ht)

    if "oil_market" in components:
        row = sinks.loc[sinks.label == "oil_market", :]
        oil_market = solph.components.Sink(
            label="oil_market",
            inputs={
                busd[row.bus_in.item()]: solph.Flow(
                    variable_costs=row.variable_costs.item(),
                )
            },
        )
        es.add(oil_market)

    if "h2_market" in components:
        row = sinks.loc[sinks.label == "h2_market", :]
        h2_market = solph.components.Sink(
            label="h2_market",
            inputs={
                busd[row.bus_in.item()]: solph.Flow(
                    variable_costs=row.variable_costs.item(),
                )
            },
        )
        es.add(h2_market)

    if "torch" in components:
        row = sinks.loc[sinks.label == "torch", :]
        torch = solph.components.Sink(
            label="torch",
            inputs={
                busd[row.bus_in.item()]: solph.Flow(
                    variable_costs=row.variable_costs.item(),
                )
            },
        )
        es.add(torch)

    if "heat_lt_excess" in components:
        row = sinks.loc[sinks.label == "heat_lt_excess", :]
        heat_lt_excess = solph.components.Sink(
            label="heat_lt_excess",
            inputs={
                busd[row.bus_in.item()]: solph.Flow(
                    variable_costs=row.variable_costs.item(),
                )
            },
        )
        es.add(heat_lt_excess)

    if "heat_ht_excess" in components:
        row = sinks.loc[sinks.label == "heat_ht_excess", :]
        heat_ht_excess = solph.components.Sink(
            label="heat_ht_excess",
            inputs={
                busd[row.bus_in.item()]: solph.Flow(
                    variable_costs=row.variable_costs.item(),
                )
            },
        )
        es.add(heat_ht_excess)

    # SOURCES
    if "biomass" in components:
        row = sources.loc[sources.label == "biomass", :]
        biomass = solph.components.Source(
            label="biomass",
            outputs={
                busd[row.bus_out.item()]: solph.Flow(
                    nominal_capacity=row.nominal_capacity.item(),
                    variable_costs=row.variable_costs.item(),
                )
            },
        )
        es.add(biomass)

    if "heat_source" in components:
        row = sources.loc[sources.label == "heat_source", :]
        heat_source = solph.components.Source(
            label="heat_source",
            outputs={
                busd[row.bus_out.item()]: solph.Flow(variable_costs=row.variable_costs.item())
            },
        )
        es.add(heat_source)

    # CONVERTERS

    if "orc" in components:
        row = converters.loc[converters.label == "orc"]
        if row.investment.item() is True:
            epc = epcs["orc"]
            orc = solph.components.Converter(
                label="orc",
                inputs={busd[row.bus_in_1.item()]: solph.Flow()},
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=solph.Investment(ep_costs=epc, minimum=row.minimum.item())
                    ),
                    busd[row.bus_out_2.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                    busd[row.bus_out_2.item()]: row.eff_out_2.item(),
                },
            )
        elif row.investment.item() is False:
            orc = solph.components.Converter(
                label="orc",
                inputs={busd[row.bus_in_1.item()]: solph.Flow()},
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(),
                    busd[row.bus_out_2.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                    busd[row.bus_out_2.item()]: row.eff_out_2.item(),
                },
            )
        es.add(orc)

    if "chp" in components:
        row = converters.loc[converters.label == "chp"]
        if row.investment.item() is True:
            epc = epcs["chp"]
            chp = solph.components.Converter(
                label="chp",
                inputs={busd[row.bus_in_1.item()]: solph.Flow()},
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=solph.Investment(ep_costs=epc, minimum=row.minimum.item()),
                    ),
                    busd[row.bus_out_2.item()]: solph.Flow(),
                    busd[row.bus_out_3.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                    busd[row.bus_out_2.item()]: row.eff_out_2.item(),
                    busd[row.bus_out_3.item()]: row.eff_out_3.item(),
                },
            )

        elif row.investment.item() is False:
            # Create chp for cold gas
            chp = solph.components.Converter(
                label="chp",
                inputs={busd[row.bus_in_1.item()]: solph.Flow()},
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=row.nominal_capacity.item()
                    ),
                    busd[row.bus_out_2.item()]: solph.Flow(),
                    busd[row.bus_out_3.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                    busd[row.bus_out_2.item()]: row.eff_out_2.item(),
                    busd[row.bus_out_3.item()]: row.eff_out_3.item(),
                },
            )
        es.add(chp)

    if "power_to_heat" in components:
        row = converters.loc[converters.label == "power_to_heat"]
        if row.investment.item() is True:
            epc = epcs["power_to_heat"]
            power_to_heat = solph.components.Converter(
                label="power_to_heat",
                inputs={busd[row.bus_in_1.item()]: solph.Flow()},
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=solph.Investment(ep_costs=epc, minimum=row.minimum.item()),
                    ),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                },
            )
        elif row.investment.item() is False:
            power_to_heat = solph.components.Converter(
                label="power_to_heat",
                inputs={busd[row.bus_in_1.item()]: solph.Flow()},
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=row.nominal_capacity.item()
                    ),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                },
            )
        es.add(power_to_heat)

    if "h2_filtration" in components:
        row = converters.loc[converters.label == "h2_filtration"]
        if row.investment.item() is True:
            epc = epcs["h2_filtration"]
            h2_filtration = solph.components.Converter(
                label="h2_filtration",
                inputs={busd[row.bus_in_1.item()]: solph.Flow()},
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=solph.Investment(ep_costs=epc, minimum=row.minimum.item()),
                    ),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                },
            )
        elif row.investment.item() is False:
            h2_filtration = solph.components.Converter(
                label="h2_filtration",
                inputs={busd[row.bus_in_1.item()]: solph.Flow()},
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=row.nominal_capacity.item()
                    ),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                },
            )
        es.add(h2_filtration)

    if "pyrolysis" in components:
        row = converters.loc[converters.label == "pyrolysis"]
        if row.investment.item() is True:
            epc = epcs["pyrolysis"]
            pyrolysis = solph.components.Converter(
                label="pyrolysis",
                inputs={
                    busd[row.bus_in_1.item()]: solph.Flow(),
                    busd[row.bus_in_2.item()]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        min=row.min_load_share.item(),  # Minimal load
                        max=1,  # A maximum is required for linearization
                        # A positive gradient limit isn't possible in investment
                        # optimization.
                        nonconvex=solph.NonConvex(
                            # Startup_costs cannot be set in investment optimization
                            minimum_downtime=int(row.minimum_downtime.item()),
                            initial_status=row.initial_status.item(),
                            maximum_startups=row.maximum_startups.item(),
                        ),
                        nominal_capacity=solph.Investment(
                            ep_costs=epc,
                            minimum=row.minimum.item(),
                            maximum=row.maximum.item(),  # necessary for linearization
                        ),
                    ),
                    busd[row.bus_out_2.item()]: solph.Flow(),
                    busd[row.bus_out_3.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_in_2.item()]: row.eff_in_2.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                    busd[row.bus_out_2.item()]: row.eff_out_2.item(),
                    busd[row.bus_out_3.item()]: row.eff_out_3.item(),
                },
            )
        elif row.investment.item() is False:
            pyrolysis = solph.components.Converter(
                label="pyrolysis",
                inputs={
                    busd[row.bus_in_1.item()]: solph.Flow(),
                    busd[row.bus_in_2.item()]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=row.nominal_capacity.item(),
                        # No positive_gradient_limit here because it is
                        # set in the ramping constraint
                        min=row.min_load_share.item(),
                        max=1,
                        nonconvex=solph.NonConvex(
                            startup_costs=row.startup_costs.item(),
                            minimum_downtime=int(row.minimum_downtime.item()),
                            initial_status=row.initial_status.item(),
                            maximum_startups=row.maximum_startups.item(),
                        ),
                    ),
                    busd[row.bus_out_2.item()]: solph.Flow(),
                    busd[row.bus_out_3.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_in_2.item()]: row.eff_in_2.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                    busd[row.bus_out_2.item()]: row.eff_out_2.item(),
                    busd[row.bus_out_3.item()]: row.eff_out_3.item(),
                },
            )
        es.add(pyrolysis)

    if "heat_exchanger" in components:
        row = converters.loc[converters.label == "heat_exchanger"]
        if row.investment.item() is True:
            epc = epcs["heat_exchanger"]
            heat_exchanger = solph.components.Converter(
                label="heat_exchanger",
                inputs={
                    busd[row.bus_in_1.item()]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=solph.Investment(ep_costs=epc)
                    ),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                },
            )
        elif row.investment.item() is False:
            heat_exchanger = solph.components.Converter(
                label="heat_exchanger",
                inputs={
                    busd[row.bus_in_1.item()]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                },
            )
        es.add(heat_exchanger)

    if "combustor" in components:
        row = converters.loc[converters.label == "combustor"]
        if row.investment.item() is True:
            epc = epcs["combustor"]
            combustor_hot = solph.components.Converter(
                label="combustor_hot",
                inputs={
                    busd[row.bus_in_1.item()]: solph.Flow(),
                },
                outputs={
                    busd["b_combustor_cap"]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd["b_combustor_cap"]: row.eff_out_1.item(),
                },
            )
            combustor_cold = solph.components.Converter(
                label="combustor_cold",
                inputs={
                    busd[row.bus_in_1_alternative.item()]: solph.Flow(),
                },
                outputs={
                    busd["b_combustor_cap"]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1_alternative.item()]: row.eff_in_1.item(),
                    busd["b_combustor_cap"]: row.eff_out_1.item(),
                },
            )
            # Create a virtual converter with investment that collects the first outputs
            # from combustor_hot and combustor_cold and converts them into the actual first output
            combustor_to_out1 = solph.components.Converter(
                label="combustor_to_out1",
                inputs={
                    busd["b_combustor_cap"]: solph.Flow(
                        nominal_capacity=solph.Investment(ep_costs=epc, minimum=row.minimum.item()),
                    ),
                },
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd["b_combustor_cap"]: 1,
                    busd[row.bus_out_1.item()]: 1,
                },
            )
            es.add(combustor_hot, combustor_cold, combustor_to_out1)

        elif row.investment.item() is False:
            combustor_hot = solph.components.Converter(
                label="combustor_hot",
                inputs={
                    busd[row.bus_in_1.item()]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                },
            )
            combustor_cold = solph.components.Converter(
                label="combustor_cold",
                inputs={
                    busd[row.bus_in_1_alternative.item()]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(),
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                },
            )
            es.add(combustor_hot, combustor_cold)

    if "condensor" in components:
        row = converters.loc[converters.label == "condensor"]
        if row.investment.item() is True:
            epc = epcs["condensor"]
            condensor = solph.components.Converter(
                label="condensor",
                inputs={
                    busd[row.bus_in_1.item()]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=solph.Investment(ep_costs=epc, minimum=row.minimum.item())
                    ),  # cold syngas
                    busd[row.bus_out_2.item()]: solph.Flow(),  # heat
                    busd[row.bus_out_3.item()]: solph.Flow(),  # oil
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                    busd[row.bus_out_2.item()]: row.eff_out_2.item(),
                    busd[row.bus_out_3.item()]: row.eff_out_3.item(),
                },
            )
        elif row.investment.item() is False:
            condensor = solph.components.Converter(
                label="condensor",
                inputs={
                    busd[row.bus_in_1.item()]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out_1.item()]: solph.Flow(
                        nominal_capacity=row.nominal_capacity.item()
                    ),  # cold syngas
                    busd[row.bus_out_2.item()]: solph.Flow(),  # heat
                    busd[row.bus_out_3.item()]: solph.Flow(),  # oil
                },
                conversion_factors={
                    busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                    busd[row.bus_out_1.item()]: row.eff_out_1.item(),
                    busd[row.bus_out_2.item()]: row.eff_out_2.item(),
                    busd[row.bus_out_3.item()]: row.eff_out_3.item(),
                },
            )
        es.add(condensor)

    if "biomass_dryer" in components:
        row = converters.loc[converters.label == "biomass_dryer"]
        biomass_dryer = solph.components.Converter(
            label="biomass_dryer",
            inputs={
                busd[row.bus_in_1.item()]: solph.Flow(),
                busd[row.bus_in_2.item()]: solph.Flow(),
            },
            outputs={
                busd[row.bus_out_1.item()]: solph.Flow(),
            },
            conversion_factors={
                busd[row.bus_in_1.item()]: row.eff_in_1.item(),
                busd[row.bus_in_2.item()]: row.eff_in_2.item(),
                busd[row.bus_out_1.item()]: row.eff_out_1.item(),
            },
        )
        es.add(biomass_dryer)

    # STORAGE

    def instantiate_storage(row):

        if row.investment is True:
            label = row.label
            epc_nominal_storage_capacity = epcs[row.label]

            nominal_cap = solph.Investment(
                ep_costs=epc_nominal_storage_capacity, maximum=row.maximum
            )
            storage = solph.components.GenericStorage(
                label=label,
                inputs={
                    busd[row.bus_in]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out]: solph.Flow(),
                },
                loss_rate=row.loss_rate,
                initial_storage_level=row.initial_storage_level,
                inflow_conversion_factor=row.inflow_conversion_factor,
                outflow_conversion_factor=row.outflow_conversion_factor,
                nominal_capacity=nominal_cap,
            )
        elif row.investment is False:
            storage = solph.components.GenericStorage(
                label=row.label,
                inputs={
                    busd[row.bus_in]: solph.Flow(),
                },
                outputs={
                    busd[row.bus_out]: solph.Flow(),
                },
                loss_rate=row.loss_rate,
                initial_storage_level=row.initial_storage_level,
                inflow_conversion_factor=row.inflow_conversion_factor,
                outflow_conversion_factor=row.outflow_conversion_factor,
                nominal_storage_capacity=row.nominal_storage_capacity,
            )
        es.add(storage)

    if not storage.empty:
        storage.apply(lambda row: instantiate_storage(row), axis=1).any()

    # Initialise the operational model
    om = solph.Model(es)

    print("The model has been constructed.")

    # Set flow boundarie for electricity grid and electricity grid sybsidy sink
    if "electricity_grid" in components:
        row = sinks.loc[sinks.label == "electricity_grid", :]
        nominal_capacity = row.nominal_capacity.item()
        min = get_value_or_profile(row, "min", profiles)
        max = get_value_or_profile(row, "max", profiles)

        def value_at(profile, t):
            return profile.iloc[t] if isinstance(profile, pd.Series) else profile

        def electricity_flow_boundaries(om, t):
            total_flow = (
                om.flow[electricity_grid, busd[row.bus_in.item()], t]
                + om.flow[electricity_premium, busd[row.bus_in.item()], t]
            )
            lower_bound = nominal_capacity * value_at(min, t)
            upper_bound = nominal_capacity * value_at(max, t)
            return (lower_bound, total_flow, upper_bound)

        om.electricity_export_limit = Constraint(om.TIMESTEPS, rule=electricity_flow_boundaries)

    if "pyrolysis" in components:
        row = converters.loc[converters.label == "pyrolysis"]

        if row.investment.item() is False:
            print("Creating costum constraints for pyrolysis")

            pyrolysis_component = pyrolysis
            bus_out_1 = busd[row.bus_out_1.item()]
            bus_out_2 = busd[row.bus_out_2.item()]
            eff_out_1 = row.eff_out_1.item()

            def tradeoff_bounds_lower(om, t):
                out1 = om.flow[pyrolysis_component, bus_out_1, t]
                out2 = om.flow[pyrolysis_component, bus_out_2, t]
                min_ratio = (eff_out_1 + eff_out_1 * row.out_1_max_decrease.item()) / (
                    row.eff_out_2.item()
                    + row.eff_out_2.item() * row.out_2_corresponding_increase.item()
                )
                # Only enforce when biochar is active
                return out1 >= min_ratio * out2

            def tradeoff_bounds_upper(om, t):
                out1 = om.flow[pyrolysis_component, bus_out_1, t]
                out2 = om.flow[pyrolysis_component, bus_out_2, t]
                max_ratio = eff_out_1 / row.eff_out_2.item()
                return out1 <= max_ratio * out2

            def ramp_rule(om, t):
                """
                This constraint ensures that the ramping of the pyrolysis unit is limited according
                to the positive_gradient_limit parameter.
                The limitation is only enforced above the minimum load share to avoid conflicting
                constraints in the case positive_gradient_limit < minimum_load_share.
                The constraint is only active in dispatch mode to keep the optimization
                problem linear.
                """
                if t == om.TIMESTEPS.first():
                    return Constraint.Skip
                else:
                    out1 = om.flow[pyrolysis_component, bus_out_1, t]
                    out1_prev = om.flow[pyrolysis_component, bus_out_1, t - 1]

                    status_t = om.NonConvexFlowBlock.status[pyrolysis_component, bus_out_1, t]
                    status_prev = om.NonConvexFlowBlock.status[
                        pyrolysis_component, bus_out_1, t - 1
                    ]

                    nominal_capacity = row.nominal_capacity.item()
                    min_load = row.min_load_share.item()
                    max_ramp = row.positive_gradient_limit.item()

                    return (
                        out1 - out1_prev
                    ) <= max_ramp * nominal_capacity + min_load * nominal_capacity * (
                        status_t - status_prev
                    )

            om.tradeoff_lower_constraint = Constraint(om.TIMESTEPS, rule=tradeoff_bounds_lower)
            om.tradeoff_upper_constraint = Constraint(om.TIMESTEPS, rule=tradeoff_bounds_upper)
            om.custom_ramp = Constraint(om.TIMESTEPS, rule=ramp_rule)

    # Add active-flow-count-limit to avoid the use of storage to waste energy
    if not storage.empty:
        print("Creating flow count limits for storage")
        storage_components = []

        for _, row in storage.iterrows():
            label = row.label
            comp = next(n for n in es.nodes if n.label == label)
            storage_components.append(comp)

        om.STORAGES = Set(initialize=storage_components)
        om.storage_direction = Var(om.STORAGES, om.TIMESTEPS, within=Binary)
        M = 100000  # a safe but tight upper bound

        def make_limit_charge(bus_in, storage_comp):
            # Factory function to create a charge constraint for a specific storage's inflow
            def limit_charge(m, t):
                flow_in = m.flow[(bus_in, storage_comp), t]
                return flow_in <= M * m.storage_direction[storage_comp, t]

            return limit_charge

        def make_limit_discharge(storage_comp, bus_out):
            # Factory function to create a discharge constraint for a specific storage's outflow
            def limit_discharge(m, t):
                flow_out = m.flow[(storage_comp, bus_out), t]
                return flow_out <= M * (1 - m.storage_direction[storage_comp, t])

            return limit_discharge

        for idx, (_, row) in enumerate(storage.iterrows()):
            label = row.label
            storage_component = next(n for n in es.nodes if n.label == label)
            bus_in = busd[row.bus_in]
            bus_out = busd[row.bus_out]

            # Apply constraints with unique names for each storage component
            setattr(
                om,
                f"flow_count_limit_charge_{idx}",
                Constraint(om.TIMESTEPS, rule=make_limit_charge(bus_in, storage_component)),
            )
            setattr(
                om,
                f"flow_count_limit_discharge_{idx}",
                Constraint(om.TIMESTEPS, rule=make_limit_discharge(storage_component, bus_out)),
            )

    # Store lp file
    file_path = os.path.join(META_INFO, "lp_file.lp")
    om.write(file_path, io_options={"symbolic_solver_labels": True})

    # Solve the system with error handling
    from pyomo.opt import SolverStatus, TerminationCondition

    print("Solving the model...")
    om.solve(solver="cbc", tee=True)

    # Check solver status
    if (
        om.solver_results.Solver.Status == SolverStatus.warning
        or om.solver_results.Solver.termination_condition == TerminationCondition.infeasible
    ):
        print("\n=== MODEL IS INFEASIBLE ===")
        print(f"Solver Status: {om.solver_results.Solver.Status}")
        print(f"Termination Condition: {om.solver_results.Solver.termination_condition}")

    elif om.solver_results.Solver.termination_condition == TerminationCondition.optimal:
        print("\n=== MODEL SOLVED SUCCESSFULLY ===")
    else:
        print("Model solving failed. Check the error above.")
        return es, om

    return es, om


def visualize_network_in_dash(es: solph.EnergySystem):
    if input("Visualize network in dash app? (yes/no) ") == "yes":
        from pyromof.visualize_network import make_network, shownetwork

        network = make_network(es)
        shownetwork(network)


@typechecked
def save_results(
    es: solph.EnergySystem,
    om: solph.Model,
    META_INFO: Path,
    DUMPING_SPACE: Path,
    scenario: str,
    time: pd.date_range,
    epcs: dict[str, float] | None = None,
):
    # Save model structure as a graph in the graphml format. Can be opened e.g. in Gephi.
    filename = os.path.join(META_INFO, "es_graph.graphml")
    create_nx_graph(es, filename=filename)

    es.params = solph.processing.parameter_as_dict(es)
    es.results["main"] = solph.processing.results(om)
    es.results["meta"] = solph.processing.meta_results(om)
    es.results["scenario"] = scenario

    flows = solph.processing.convert_keys_to_strings(om.flows)
    columns = [a for a, b in flows.items()]
    df = pd.DataFrame(columns=columns)
    for col in df.columns:
        series = list([b for a, b in flows.items() if a == col][0].variable_costs)
        df[col] = series[: len(time) - 1]
    variable_costs = helpers.convert_tuple_columnnames_to_strings(df)
    variable_costs.to_csv(os.path.join(DUMPING_SPACE, "variable_costs_from_model.csv"), sep=";")

    if epcs is not None:
        epcs_df = pd.DataFrame(epcs.items(), columns=["object", "value"])
        epcs_df.to_csv(os.path.join(DUMPING_SPACE, "epcs_from_optimization.csv"), sep=";")

    # dump the EnergySystem
    es.dump(dpath=DUMPING_SPACE, filename="es_dump.oemof")
    print("The results have been saved.")


def optimize():
    data, time, scenario, epcs = preprocess("input_data.xlsx")
    SCENARIO_PATH, META_INFO, DUMPING_SPACE = helpers.define_and_create_folders(ROOT_PATH, scenario)

    # Save current input data version in the scenario folder
    shutil.copy("input_data.xlsx", os.path.join(META_INFO, "input_data.xlsx"))

    es, om = create_energysystem(
        META_INFO=META_INFO,
        data=data,
        time=time,
        epcs=epcs,
    )

    visualize_network_in_dash(es)
    save_results(es, om, META_INFO, DUMPING_SPACE, scenario, time, epcs=epcs)

    # Dump results to CSV before further processing
    sequences, scalars, storage_contents, additional_columns = (
        postprocessing.convert_result_sequences_to_df(es.results["main"])
    )

    for df, filename in [
        (sequences, "sequences.csv"),
        (scalars, "scalars.csv"),
        (storage_contents, "storage_contents.csv"),
        (additional_columns, "additional_columns.csv"),
    ]:
        df.to_csv(os.path.join(DUMPING_SPACE, filename), sep=";")


if __name__ == "__main__":
    optimize()
