import os
import argparse
import pandas as pd
import numpy as np
from carsharing.stations import place_new_stations, place_vehicles
from carsharing.utils import read_trips_csv, write_stations_csv

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--inp_path",
        type=str,
        default=os.path.join("data", "siouxfalls_trips.csv"),
        help="Path to trips file",
    )
    parser.add_argument(
        "-o",
        "--out_path",
        type=str,
        default=os.path.join("data", "stations.csv"),
        help="Path where to output the simulated stations",
    )
    parser.add_argument(
        "-f",
        "--fixed_stations",
        type=str,
        default=os.path.join("data", "existing_stations.csv"),
        help="Path to fixed stations that are already there",
    )
    parser.add_argument(
        "-n",
        "--number_stations",
        type=int,
        default=100,
        help="How many stations to place",
    )
    args = parser.parse_args()

    existing_stations = pd.read_csv(args.fixed_stations)
    if len(existing_stations) == 0:
        station_locations = np.zeros((0, 2))
    else:
        assert "x" in existing_stations.columns and "y" in existing_stations.columns, "station table requires x and y coordinates"
        station_locations = np.array(existing_stations[["x", "y"]])

    trips = read_trips_csv(args.inp_path)
    stations = place_new_stations(args.number_stations, trips, station_locations=station_locations)
    stations = place_vehicles(stations)
    write_stations_csv(stations.reset_index(), args.out_path)
