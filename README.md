# Pryomof
Pyromof is an [oemof.solph](https://oemof-solph.readthedocs.io/en/stable/index.html)-based optimization modelling framework for individual pyrolysis plants with flexibility options. Its purpose is to assess the profitability of different pyrolysis plants with different sets of flexibility-enhancing components under different economic policy incentives. The framework is being developed within the project [PyFlex](https://www.ioew.de/projekt/pyflex_pyrolysetechnologie_als_intersektorale_flexibilitaetsmassnahme_im_energiesystem_deutschland).

 The following components are available:
|sinks|sources|converter|storage|
|-----|------|---------|--------|
|markets for biochar, CO2 removal certificats, heat, electricity, hydrogen, bio-oil|biomass, heat|biomass dryer, pyrolysis, combined heat and power, combustor, organic rankine cycle, power to heat, hydrogen extraction from syngas, heat exchanger, condensor|storage for syngas, heat, electricity and hydrogen|

Available policy options up to know are a fixed feed-in premium for electricity, a sliding premium for electricity and investment subsidies for pyrolysis. More will be implemented soon.

## Getting started

Pyromof has been tested with Python3.12. In order to install pyromof, proceed with the following steps:
1. Create a virtual environment (e.g. with venv)
2. Clone the github repository (`git clone https://github.com/IOEW-FF2/pyromof.git`)
3. Enter the folder and
4. Install the package with `pip install -e .`.

In order to run the model you need a solver. By default, the code expects the solver cbc which you can find in https://github.com/coin-or/Cbc/releases. If you want to use a different one, you have to adjust the code in pyromof/optimize.py `om.solve(solver="your_solver")`. If you use Windows, the file "cbc.exe" (located in the bin folder) should be placed in the same folder as this readme-file.

## Data
The input data are not yet provided within this repository. A description on how to design the input data and how to run the model is provided in docs/usage.md.

## Contribute
We welcome your feedback and the creation of issues if you notice bugs or have ideas for improvements.
