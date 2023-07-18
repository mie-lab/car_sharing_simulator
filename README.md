# Car sharing simulator

This repository provides the code for our open-source car sharing simulator. The simulator is agent-based and only requires a population and their activity patterns as input. We have trained a mode choice model on tracking data from Switzerland, and this model is applied on the activity to generate car sharing data. The steps to simulate car sharing reservation data are described in detail in the following.

<img src="assets/sim_pipeline.jpg" width="500" />

### Installation

The required packages and our car sharing package can be installed via pip in editable mode in a virtual environment with the following commands:
```
git clone https://github.com/mie-lab/car_sharing_simulator.git
cd car_sharing_simulator
python -m venv env
source env/bin/activate
pip install -e .
````

## Car sharing simulation with the given example data

To allow execution of our pipeline, we provide example data within this repository. To simulate car sharing trips based on that data, simply execute the following command:

Download XML file [here](https://github.com/matsim-org/matsim-libs/blob/master/examples/scenarios/siouxfalls-2014/Siouxfalls_population.xml.gz).
Convert activity-XML into trips-csv file
```
python carsharing/activities_to_trips.py
```
Simulate stations based on the population distribution
```
python carsharing/simulate_stations.py
```

Transform trips-data into input features to the mode choice model:
```
python carsharing/features.py
```
Download the mode-choice prediction models [here](https://polybox.ethz.ch/index.php/s/U6Ge2Sb49rnRzV6) and copy the models from the `trained_models` folder in the zip to the `trained_models` folder in this repository. The [model tutorial](trained_models/model_usage_tutorial.ipynb) shows you how to use the models.

Run car sharing simulation
```
python generate_car_sharing_data.py -i data/siouxfalls_trips_features.csv -o outputs/siouxfalls_simulation -m trained_models/xgb.p -s data/stations.csv
```

## Car sharing simulation with your own data

### Generating a synthetic population

Our agent-based simulator is based on a population and their activity patterns. By activity patterns we mean the start and end times and locations of their activities over one day. Such data can be generated with [Equasim](https://github.com/eqasim-org/), a synthetic-population framework published by the IVT group at ETH Zürich. Their pipeline uses census data and transport survey data to simulate activity patterns and living / working locations of people. It also allows to scale the population for the purpose of studying future car sharing behaviour.

We used their pipeline but adapted it to **sample car sharing users** from the overall population. The changed code is copied here for version control. We sample car sharing users with stratisfied sampling based on the distance of the people to the next car sharing station. See our [script](v2g4carsharing/simulate/draw_car_sharing_population.py) for this code.

We allow for any kind of activity patterns as input, and do not restrict the input to equasim-outputs. The **activity patterns must simply be of a similar form as the example data data** in the `data` folder. Specifically, we expect a geodataframe with the following fields:
['person_id', 'activity_index', 'purpose_origin', 'geom_origin',
 'purpose_destination', 'geom_destination', 'started_at_destination',
 'feat_caraccess', 'feat_sex', 'feat_age', 'feat_ga', 'feat_halbtax', 'feat_employed']


### Create car sharing stations

Car sharing stations can either be simulated randomly based on the population density, or provided by the user. An example is given in the `data` folder. To generate random car sharing stations based on the population data, run

We need to make a scenario which car sharing stations exist and what vehicles are available at these stations. So far, a simple scenario can be generated with
```
python scripts/generate_station_scenario.py
```

### Run simulation

Execute the following command by pointing to your population with the -i flag and to your stations with the -s flag:
```
python generate_car_sharing_data.py [-h] [-i IN_PATH_SIM_TRIPS] [-o OUT_PATH] [-s STATION_SCENARIO] [-m MODEL_PATH] [-t MODEL_TYPE]

optional arguments:
  -h, --help            show this help message and exit
  -i IN_PATH_SIM_TRIPS, --in_path_sim_trips IN_PATH_SIM_TRIPS
                        path to simulated trips csv
  -o OUT_PATH, --out_path OUT_PATH
                        path to save output
  -s STATION_SCENARIO, --station_scenario STATION_SCENARIO
                        path to station_scenario
  -m MODEL_PATH, --model_path MODEL_PATH
                        path to mode choice model
  -t MODEL_TYPE, --model_type MODEL_TYPE
                        one of rf or irl
```





