from ast import Mod
import os
import pickle
import argparse
import pandas as pd
from carsharing.features import compute_dist_to_station
from carsharing.car_sharing_patterns import (
    derive_decision_time,
    derive_reservations,
    assign_mode,
)
from carsharing.utils import read_stations_csv, read_trips_csv

if __name__ == "__main__":
    # args
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--in_path_sim_trips",
        type=str,
        default=os.path.join("data", "siouxfalls_trips_features.csv"),
        help="path to simulated trips csv",
    )
    parser.add_argument(
        "-o",
        "--out_path",
        type=str,
        default=os.path.join("outputs", "siouxfalls_sim"),
        help="path to save output",
    )
    parser.add_argument(
        "-s",
        "--station_scenario",
        type=str,
        default=os.path.join("data", "stations.csv"),
        help="path to station_scenario",
    )
    parser.add_argument(
        "-m",
        "--model_path",
        type=str,
        default=os.path.join("trained_models", "xgb_model.p"),
        help="path to mode choice model",
    )
    # path to use for postgis_json_path argument: "../../dblogin_mielab.json"
    args = parser.parse_args()

    in_path_sim_trips = args.in_path_sim_trips
    out_path = args.out_path
    os.makedirs("outputs", exist_ok=True)
    os.makedirs(out_path, exist_ok=True)

    # load activities and shared-cars availability
    acts_gdf = read_trips_csv(in_path_sim_trips, crs="EPSG:26914")
    # define mode choice model
    # mode_choice_model = simple_mode_choice
    with open(args.model_path, "rb") as infile:
        mode_choice_model = pickle.load(infile)

    station_scenario = read_stations_csv(
        args.station_scenario, geom_col="geometry", crs="EPSG:26914"
    )

    # If we have the same stations, the distance to the closest station is
    # automatically computed in the feature computation. If we have more
    # stations, we need to recompute where is the closest station (or do it at
    # runtime for computing the closest station that has vehicles available)
    assert (
        "geom" in station_scenario.columns
    ), "station scenario must have geometry"
    assert (
        "geom_origin" in acts_gdf.columns
    ), "acts gdf must have geometry to recompute distance to station"
    print("Recomputing distance to station..")
    # compute dist to station for each trip start and end point
    acts_gdf = compute_dist_to_station(acts_gdf, station_scenario)

    # sort
    acts_gdf.sort_values(["person_id", "activity_index"], inplace=True)

    # get time when decision is made
    acts_gdf = derive_decision_time(acts_gdf)

    # Run: iteratively assign modes
    acts_gdf_mode = assign_mode(acts_gdf, station_scenario, mode_choice_model)

    # Save trip modes
    acts_gdf_mode[
        [
            "person_id",
            "activity_index",
            "mode_decision_time",
            "mode",
            "vehicle_no",
        ]
    ].to_csv(os.path.join(out_path, "sim_modes.csv"), index=False)

    # get shared only and derive the reservations by merging subsequent car sharing trips
    sim_reservations = derive_reservations(acts_gdf_mode)

    # Save reservations
    sim_reservations.to_csv(os.path.join(out_path, "sim_reservations.csv"))

