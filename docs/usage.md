# Usage of pyromof

The main task in using pyromof is to prepare the input data. Afterwards, the model has to be created and optimized (in optimize.py), it should be postprocessed to store the results in a readable format (in postprocessing.py) and the results can be plotted (in plotting.py). It is also possible to compare the results of different scenarios in a plot (compare_scenarios.py) or to do a sensitivity analysis (analyse_sensitivity.py). In the following, the different steps and options therein will be explained.

## Preparing the input data
A template for the input data is provided in the docs folder. It is an excel file that must be located in the top layer of the pyromof folder and must be named "input_data.xlsx". Within the input data, there must be the sheets "general", "sink", "source", "converter", "storage" and "profiles". Other sheets will be ignored. The sheet "general" must contain a value for the weighted average costs of capital (wacc). In the converter sheet at least a component named "pyrolysis" must exist. All other components can be freely added or removed as long as the system is in itself complete.
Below is a list of the available components and their implemented attributes:

The available components and their attributes are listed in the input data template, in which you can also find a short explanation for each attribute. Further information is available in the [documentation of oemof solph](https://oemof-solph.readthedocs.io/en/stable/reference/oemof.solph.flow.html).

Two costum attributes have been added for the pyrolysis component in this model: out 1 max decrease and out max 2 corresponding increase. The two values together are used to define a minimum ratio between outputs 1 and 2:
```math
ratio_{min} = \frac{eff(out1) + eff(out1)*\text{out\_1\_max\_decrease}}{eff(out2) + eff(out2) *\text{out\_2\_corresponding\_increase}}
```
$ratio_{max}$ is given by the unchanged relation between the two output efficiencies.

The scenario in the input data can be a single scenario, multiple scenarios separated by commas or the word *all*. In any case there must be a string in the scenario column for every row that has a label, otherwise the model will throw an error.

## Building and optimizing the model
To build and optimize the model you have to run execute the command *pyromof optimize* in the command line. After the optimization, you have the option to vizualize the model in dash.

## Postprocessing and Plotting
Postprocessing is very straight forward by running *pyromof postprocess*. For plotting use *pyromof plot*. The scenario to be postprocessed or plotted is read from the input data.

 In *compare_scenarios.py* you will be prompted to type in multiple scenarios separated by commas. The script will plot the scalar results (= mostly summed up costs and flows over the entire period) in bar charts next to each other.

## Scenario comparison and Sensitivity analysis
*pyromof compare_scenarios* requires that you type the scenarios you want to compare at the bottom of the script (scenarios = ["scenario1", "scenario2"]). You can select as many scenarios as you whish. The names must match the names of the scenario folders. The scenarios are also compared with regards to some flexibility criteria.
A sensitivity analysis can be done with *pyromof analyse_sensitivity*. Here you also have to adjust the parameters directly in the script. The parameters to be set are the component type (sinks, sources, converters or storage), the component, the target parameter, its minimum value, its maximum value and the step width. Furthermore, you must also select the scenario and the time period directly in the script.
