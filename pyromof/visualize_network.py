# The following code has been written by Tobias Hörter and Andreas Wunsch and
# has been only slightly changed.
# The original code is available here: https://gitlab.cc-asp.fraunhofer.de/-/snippets/1016
# It has been published under the GPLv3 licence.

import socket

import dash
import dash_cytoscape as cyto
import networkx as nx
from dash import html
from dash.dependencies import Input, Output
from IPython import get_ipython
from oemof import solph


def make_network(energysystem):
    # construct directed graph from oemof energysystem

    def get_parameters(component):
        parameters = {}

        if (
            isinstance(component, solph.components.GenericStorage)
            or isinstance(component, solph.components.Converter)
            or isinstance(component, solph.components.GenericCHP)
        ):
            for attr, value in vars(component).items():
                if not attr.startswith(
                    "_"
                ):  # Skip private attributes that are not relevant for the system
                    if isinstance(value, list):
                        value = ";  ".join(map(str, value))
                    value = str(value)  # Value needs to be a string if it is a list
                    parameters[attr] = value

            for input, flow in component.inputs.items():
                nominal_value_in = getattr(flow, "nominal_value", "N/A")
                nominal_value_in = str(nominal_value_in)
                variable_costs_in = getattr(flow, "variable_costs", "N/A")
                variable_costs_in = str(variable_costs_in)

                parameters["nominal_value_in"] = nominal_value_in
                parameters["variable_costs_input"] = variable_costs_in

            for output, flow in component.outputs.items():
                nominal_value_out = getattr(flow, "nominal_value", "N/A")
                variable_costs_out = getattr(flow, "variable_costs", "N/A")
                variable_costs_out = str(variable_costs_out)

                nominal_value_out = str(nominal_value_out)
                parameters["nominal_value_out"] = nominal_value_out
                parameters["variable_costs_out"] = variable_costs_out
            return parameters

        if isinstance(
            component, solph.components.Source
        ):  # For sources the relevant properties are in the output flow(sources have no input flow)
            for output, flow in component.outputs.items():
                nominal_value = getattr(flow, "nominal_value", "N/A")
                nominal_value = str(nominal_value)
                variable_costs = getattr(flow, "variable_costs", "N/A")
                variable_costs = str(variable_costs)
                parameters["nominal_value"] = nominal_value
                parameters["variable_costs"] = variable_costs

        if isinstance(
            component, solph.components.Sink
        ):  # For sinks relevant properties are in the input flow
            for input, flow in component.inputs.items():
                nominal_value = getattr(flow, "nominal_value", "No nominal value")
                nominal_value = str(nominal_value)
                variable_costs = getattr(flow, "variable_costs", "N/A")
                variable_costs = str(variable_costs)
                parameters["nominal_value"] = nominal_value
                parameters["variable_costs"] = variable_costs

        return parameters

    G = nx.DiGraph()  # Directed Graph using networkx

    for component in energysystem.nodes:
        parameters = get_parameters(component)
        G.add_node(component.label)  # Use the real Oemof label for nodes

        if isinstance(component, solph.components.Source):
            G.nodes[component.label]["type"] = "source"
            G.nodes[component.label]["parameters"] = parameters
            G.nodes[component.label]["color"] = "yellow"
            G.nodes[component.label]["shape"] = "custom-source"
        elif isinstance(component, solph.components.Sink):
            G.nodes[component.label]["type"] = "sink"
            G.nodes[component.label]["parameters"] = parameters
            G.nodes[component.label]["color"] = "green"
            G.nodes[component.label]["shape"] = "custom-sink"
        elif isinstance(component, solph.components.Converter) or isinstance(
            component, solph.components.GenericCHP
        ):
            G.nodes[component.label]["type"] = "converter"
            G.nodes[component.label]["parameters"] = parameters
            G.nodes[component.label]["color"] = "gray"
            G.nodes[component.label]["shape"] = "rectangle"
        elif isinstance(component, solph.buses.Bus):
            G.nodes[component.label]["color"] = "red"
            G.nodes[component.label]["shape"] = "ellipse"
        elif isinstance(component, solph.components.GenericStorage):
            G.nodes[component.label]["type"] = "storage"
            G.nodes[component.label]["parameters"] = parameters
            G.nodes[component.label]["color"] = "black"
            G.nodes[component.label]["shape"] = "round-rectangle"
        else:
            G.nodes[component.label]["color"] = "light-blue"
            G.nodes[component.label]["shape"] = "round-rectangle"

        for input_component in component.inputs:
            G.add_edge(input_component.label, component.label)
        for output_component in component.outputs:
            G.add_edge(component.label, output_component.label)

    return G


def make_cytoscape_elements(G):
    nodes = [
        {
            "data": {
                "id": node,
                "label": node,
                "type": G.nodes[node].get("type", {}),
                "color": G.nodes[node]["color"],
                "shape": G.nodes[node]["shape"],
                "parameters": G.nodes[node].get("parameters", {}),
            }
        }
        for node in G.nodes()
    ]
    edges = [{"data": {"source": u, "target": v}} for u, v in G.edges()]
    return nodes + edges


def shownetwork(network):
    app = dash.Dash(__name__, suppress_callback_exceptions=True)

    elements = make_cytoscape_elements(network)
    cyto.load_extra_layouts()
    app.layout = html.Div(
        [
            cyto.Cytoscape(
                id="cytoscape",
                layout={
                    "name": "klay"
                },  # klay means horizontal layout. Change to e.g. 'dagre' for vertical layout
                style={"width": "100%", "height": "800px"},
                elements=elements,
                stylesheet=[
                    {
                        "selector": "node",
                        "style": {
                            "content": "data(label)",
                            "background-color": "data(color)",
                            "font-size": 10,
                            "color": "white",
                            "text-valign": "center",
                            "text-halign": "center",
                            "width": "90px",
                            "height": "70px",
                            "shape": "data(shape)",
                            "text-outline-color": "black",
                            "text-outline-width": 0.5,
                        },
                    },
                    {
                        "selector": '[shape = "custom-source"]',
                        "style": {
                            "shape": "polygon",
                            "shape-polygon-points": "-0.5 0.5, 0.5 0.5, 1 -0.5, -1 -0.5",
                        },
                    },
                    {
                        "selector": '[shape = "custom-sink"]',
                        "style": {
                            "shape": "polygon",
                            "shape-polygon-points": "-0.5 -0.5, 0.5 -0.5, 1 0.5, -1 0.5",
                        },
                    },
                    {
                        "selector": "edge",
                        "style": {
                            "curve-style": "straight",
                            "width": 2,
                            "line-color": "gray",
                            "target-arrow-color": "gray",
                            "target-arrow-shape": "triangle",
                            "arrow-scale": 2,
                        },
                    },
                ],
            ),
            html.Div(
                id="node-data",
                style={
                    "white-space": "pre-line",
                    "color": "white",
                    "background-color": "#2D3033",
                    "padding": "10px",
                },
            ),
            html.Button("Export as Image", id="btn-image", n_clicks=0),
        ]
    )

    textcolor = "white"  # (change textcolor depending on preferance)

    # implement routine to make results clickable
    @app.callback(Output("node-data", "children"), Input("cytoscape", "tapNodeData"))
    def display_node_data(data):  # https://dash.plotly.com/cytoscape/events
        if data:
            parameters = data.get("parameters", {})
            components = []
            components.append(
                html.H4(
                    f"Node {data['id']} Parameters:",
                    style={"color": textcolor},
                )
            )

            if data.get("type") == "source" or data.get("type") == "sink":
                for k, v in parameters.items():
                    components.append(html.P(f"{k}: {v}", style={"color": textcolor}))

            if data.get("type") == "storage":
                for k, v in parameters.items():
                    components.append(html.P(f"{k}: {v}", style={"color": textcolor}))
            if data.get("type") == "converter" and parameters:
                for k, v in parameters.items():
                    components.append(html.P(f"{k}: {v}", style={"color": textcolor}))

            return html.Div(components)

        return html.P(
            "Click on a node to see its parameters.",
            style={"color": textcolor},
        )

    app.clientside_callback(
        """
        function(n_clicks) {
            if (n_clicks > 0) {
                var cy = window.cy;
                if (cy) {
                    var png64 = cy.png({scale: 3, full: true});
                    var a = document.createElement('a');
                    a.href = png64;
                    a.download = 'Oemof_model.png';
                    a.click();
                }
            }
            return 'Export as Image';
        }
        """,
        Output("btn-image", "children"),
        Input("btn-image", "n_clicks"),
    )

    def is_notebook():  # allow both the use within jupyter notebooks, as wells as within .py files
        try:
            shell = get_ipython().__class__.__name__
            if shell == "ZMQInteractiveShell":
                return True
            elif shell == "TerminalInteractiveShell":
                return False
            else:
                return False
        except NameError:
            return (False,)

    # -----automatically run app on a free port-----#
    # for successful visualization plotly dash needs a free port, which means
    # you cannot run this routine in two different notebooks on the same port.
    # In the following we search for a free port within a certain range:
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) == 0

    def find_free_port(start_port=8050, end_port=8100):
        for port in range(start_port, end_port):
            if not is_port_in_use(port):
                return port
        raise Exception("No free port found")

    # Example usage
    port = find_free_port(8050, 8100)  # range can be increased/decreased...

    if is_notebook():  # directly displayed in jupyter
        app.run(mode="inline", debug=True, port=port)
    else:  # gives a link for the port
        app.run(debug=True, port=port, use_reloader=False)
