import numpy as np
import geopandas as gpd
import os
import time
import json
import pandas as pd
from shapely import wkt
from ast import literal_eval
import warnings
import datetime as dt

from v2g4carsharing.import_data.import_utils import to_datetime_bizend

RANDOM_DATE = pd.to_datetime("2020-01-20")


def derive_decision_time(
    acts_gdf_mode, avg_drive_speed=50
):  # 50 kmh average speed
    # rename distance column if necessary
    if "distance" not in acts_gdf_mode.columns:
        if "feat_distance" not in acts_gdf_mode.columns:
            raise RuntimeError("distance between geometries must be computed")
        acts_gdf_mode.rename(columns={"feat_distane": "distance"}, inplace=True)

    print(
        "max distance between activities",
        round(acts_gdf_mode["distance"].max()),
    )
    # get appriximate travel time in minutes
    acts_gdf_mode["drive_time"] = (
        60 * acts_gdf_mode["distance"] / (1000 * avg_drive_speed)
    )
    drive_time_vals = acts_gdf_mode["drive_time"].values + 10
    # compute time for decision making
    acts_gdf_mode["mode_decision_time"] = (
        # in seconds, giving 10min decision time
        acts_gdf_mode["started_at_destination"]
        - pd.Series([dt.timedelta(minutes=d) for d in drive_time_vals])
    )
    # drop the rows of activities that are repeated
    print("Number of activities", len(acts_gdf_mode))
    acts_gdf_mode = acts_gdf_mode[acts_gdf_mode["distance"] > 0]
    print("Activities after dropping 0-distance ones:", len(acts_gdf_mode))

    # correct wrong decision times (sometimes they are lower than the one of
    # the previous activity, due to rough approximation of vehicle speed)
    cond1, cond2 = np.array([True]), np.array([True])
    while np.sum(cond1 & cond2) > 0:
        acts_gdf_mode["prev_dec_time"] = acts_gdf_mode[
            "mode_decision_time"
        ].shift(1)
        acts_gdf_mode["prev_person"] = acts_gdf_mode["person_id"].shift(1)
        cond1 = (
            acts_gdf_mode["prev_dec_time"] > acts_gdf_mode["mode_decision_time"]
        )
        cond2 = acts_gdf_mode["prev_person"] == acts_gdf_mode["person_id"]
        if sum(cond1 & cond2) > 0:
            # reset decision time to after the previously chosen
            pad_sequence = pd.Series(
                [dt.timedelta(minutes=2) for _ in range(sum(cond1 & cond2))]
            )
            acts_gdf_mode.loc[(cond1 & cond2), "mode_decision_time"] = (
                acts_gdf_mode.loc[(cond1 & cond2), "prev_dec_time"]
                + pad_sequence
            )  # add two minutes to the previous decision time

    # now all the decision times should be sorted
    assert acts_gdf_mode.equals(
        acts_gdf_mode.sort_values(["person_id", "mode_decision_time"])
    )

    return acts_gdf_mode


def assign_mode(acts_gdf_mode, station_scenario, mode_choice_function):
    # now sort by mode decision time, not by person
    acts_gdf_mode = acts_gdf_mode.sort_values("mode_decision_time")
    # keep track in a dictionary how many vehicles are available at each station
    per_station_veh_avail = station_scenario["vehicle_list"].to_dict()
    # keep track for each person where their shared trips started (station no and location ID)
    shared_starting_station, shared_starting_location = {}, {}
    # keep track of the vehicle ID of the currently borrowed car
    shared_vehicle_id = {}
    # keep list of cars that are scheduled to be given back at a certain time
    scheduled_car_returns = []

    tic = time.time()
    final_modes, final_veh_ids, final_start_station, final_end_station = (
        [],
        [],
        [],
        [],
    )
    for idx, row in acts_gdf_mode.iterrows():

        # return all cars that are scheduled for return
        number_returned = 0
        for car_return_info in scheduled_car_returns:
            return_time, return_station, return_vehicle = car_return_info
            if return_time > row["mode_decision_time"]:
                # stop iteration if we have a car that has
                break
            # return the vehicle
            per_station_veh_avail[return_station].append(return_vehicle)
            number_returned += 1
            print(f"returned {return_vehicle} to station {return_station}")
        if number_returned > 0:
            scheduled_car_returns = scheduled_car_returns[number_returned:]

        # get necessary variables
        person_id = row["person_id"]
        closest_station = row[
            "closest_station_origin"
        ]  # closest station at previous activity for starting
        nr_avail = len(per_station_veh_avail[closest_station])

        # check if we already borrowed a car --> need to keep it for return trip
        shared_start = shared_starting_station.get(person_id, None)
        if shared_start:
            shared_vehicle = shared_vehicle_id[person_id]
            final_veh_ids.append(
                shared_vehicle
            )  # current veh ID is the shared vehicle
            final_start_station.append(-1)
            final_modes.append("Mode::CarsharingMobility")
            # check whether we are back at the start station - give back the car
            # Two possibilities: Either we picked up the car at the closest
            # station, and we are back there, or we are
            # simply back at the same ID
            shared_start_loc = shared_starting_location[person_id]
            if (
                shared_start == row["closest_station_destination"]
                or shared_start_loc == row["location_id_destination"]
            ):
                # schedule return of the vehicle at a certain time and place
                scheduled_car_returns.append(
                    (
                        row["started_at_destination"],
                        shared_start,
                        shared_vehicle,
                    )
                )
                print("scheduled for return", scheduled_car_returns[-1])
                # resort the return schedule by time
                scheduled_car_returns = sorted(
                    scheduled_car_returns, key=lambda x: x[0]
                )
                # clean the dictionary entries
                del shared_starting_station[person_id]
                del shared_starting_location[person_id]
                del shared_vehicle_id[person_id]
                # if we returned the car, we log the start station
                final_end_station.append(shared_start)
            else:
                # if we kept the car, we log -1 as the end station
                final_end_station.append(-1)
            continue

        # otherwise: decide whether to borrow the car
        if nr_avail < 1:
            # recompute distance to closest station with available vehicles
            stations_with_vehicles = [
                station_no
                for station_no in per_station_veh_avail.keys()
                if len(per_station_veh_avail[station_no]) > 0
            ]
            station_geometries = station_scenario[["geom"]].loc[
                stations_with_vehicles
            ]
            distances_to_available_stations = station_geometries.distance(
                row["geom_origin"]
            )
            closest_station = distances_to_available_stations.idxmin()
            row["closest_station_origin"] = closest_station
            # update origin station in main dataframe for further use later
            acts_gdf_mode.loc[idx, "closest_station_origin"] = closest_station
            row[
                "distance_to_station_origin"
            ] = distances_to_available_stations.min()
            row[
                "feat_distance_to_station_origin"
            ] = distances_to_available_stations.min()

        mode = mode_choice_function(row)
        # Hard cutoff if distance to car sharing station is disproportionally
        # large, or there is no free station
        if mode == "Mode::CarsharingMobility" and (
            row["distance_to_station_origin"] > row["distance"] * 0.5
            or pd.isna(closest_station)
        ):
            # print("Applying hard cutoff: using car instead of carsharing")
            mode = "Mode::Car"

        # if shared, set vehicle as borrowed and remember the pick up station
        # (for return)
        if mode == "Mode::CarsharingMobility":
            veh_id_borrow = per_station_veh_avail[closest_station].pop()
            shared_vehicle_id[person_id] = veh_id_borrow
            shared_starting_station[person_id] = closest_station
            shared_starting_location[person_id] = row["location_id_origin"]
            final_veh_ids.append(veh_id_borrow)
            final_start_station.append(closest_station)
            final_end_station.append(-1)
            print(person_id, "borrowed car at station", closest_station)

        final_modes.append(mode)
        if mode != "Mode::CarsharingMobility":
            final_veh_ids.append(-1)
            final_start_station.append(-1)
            final_end_station.append(-1)
        if len(final_modes) % 1000 == 0:
            print("decision time", row["mode_decision_time"])
            print("Step:", len(final_modes), ": currend mode share:")
            uni, counts = np.unique(final_modes, return_counts=True)
            print({u: c for u, c in zip(uni, counts)})

    print("time for reservation generation:", time.time() - tic)
    acts_gdf_mode["mode"] = final_modes
    acts_gdf_mode["vehicle_no"] = final_veh_ids
    acts_gdf_mode["start_station_no"] = final_start_station
    acts_gdf_mode["end_station_no"] = final_end_station
    # sort back
    acts_gdf_mode.sort_values(["person_id", "activity_index"], inplace=True)
    return acts_gdf_mode


def derive_reservations(acts_gdf_mode, mean_h_oneway=1.7, std_h_oneway=0.7):
    acts_gdf_mode["index_temp"] = acts_gdf_mode.index.values
    acts_gdf_mode["next_person_id"] = (
        acts_gdf_mode["person_id"].shift(-1).values
    )
    acts_gdf_mode["next_mode"] = acts_gdf_mode["mode"].shift(-1).values
    # # relevant if including cond5 / cond6
    # acts_gdf_mode["next_activity_index"] = acts_gdf_mode["activity_index"].shift(-1).values
    acts_gdf_mode["next_vehicle_no"] = (
        acts_gdf_mode["vehicle_no"].shift(-1).values
    )
    acts_gdf_mode["next_start_station_no"] = (
        acts_gdf_mode["start_station_no"].shift(-1).values
    )

    # merge the bookings to subsequent activities:
    cond = pd.Series(data=False, index=acts_gdf_mode.index)
    cond_old = pd.Series(data=True, index=acts_gdf_mode.index)
    cond_diff = cond != cond_old

    while np.sum(cond_diff) >= 1:
        # .values is important otherwise the "=" would imply a join via the new index
        acts_gdf_mode["next_id"] = acts_gdf_mode["index_temp"].shift(-1).values

        # identify rows to merge
        cond0 = acts_gdf_mode["next_person_id"] == acts_gdf_mode["person_id"]
        cond1 = (
            acts_gdf_mode["index_temp"] != acts_gdf_mode["next_id"]
        )  # already merged
        cond2 = acts_gdf_mode["mode"] == "Mode::CarsharingMobility"
        cond3 = acts_gdf_mode["next_mode"] == "Mode::CarsharingMobility"
        cond4 = ~pd.isna(acts_gdf_mode["next_id"])
        # cond5 = acts_gdf_mode["activity_index"] == acts_gdf_mode["next_activity_index"] - 1
        # # we cannot trust activity index because the repeated locations were removed --> cond5 is unsuitable.
        # # therefore, cond 2 and 3 were included instead
        cond5 = acts_gdf_mode["vehicle_no"] == acts_gdf_mode["next_vehicle_no"]
        # include cond5? Contra: We might give the vehicle back and borrow another one an hour later at the same
        # location, # which does not make sense. Pro: If we aggregate two different vehicles, another user might now
        # have the first vehicle, so one vehicle is used twice by two different users! --> leads to problems
        # NOTE: there is still a special case if a user by chance borrows the same car again. I decided to ignore it
        cond6 = (acts_gdf_mode["end_station_no"] == -1) & (
            acts_gdf_mode["next_start_station_no"] == -1
        )

        cond = cond0 & cond1 & cond2 & cond3 & cond4 & cond5 & cond6

        # assign index to next row
        acts_gdf_mode.loc[cond, "index_temp"] = acts_gdf_mode.loc[
            cond, "next_id"
        ]

        # check whether anything was changed
        cond_diff = cond != cond_old
        cond_old = cond.copy()

    # now after setting the index, reduce to shared
    shared_rides = acts_gdf_mode[
        acts_gdf_mode["mode"] == "Mode::CarsharingMobility"
    ]

    # aggregate into car sharing bookings instead
    agg_dict = {
        "id": list,
        "person_id": "first",
        "vehicle_no": "first",
        "distance_to_station_origin": "first",
        "distance_to_station_destination": "last",
        "mode_decision_time": "first",  # first decision time is the start of the booking
        "started_at_destination": "last",  # last start time (of activity) is the end of the booking
        "distance": "sum",  # covered distance
        "start_station_no": "first",  # first station must be the start station (possibly, the car is not returned)
        "end_station_no": "last",
    }
    sim_reservations = (
        shared_rides.reset_index().groupby(by="index_temp").agg(agg_dict)
    )
    sim_reservations = sim_reservations.rename(
        columns={
            "id": "trip_ids",
            "person_id": "person_no",
            "mode_decision_time": "reservationfrom",
            "started_at_destination": "reservationto",
        }
    )
    sim_reservations.index.name = "reservation_no"

    # correct the one-way trips
    # (they occur when the day ends before the car was returned)
    one_way = (
        sim_reservations["start_station_no"]
        != sim_reservations["end_station_no"]
    )
    print("ratio of one way trips", sum(one_way) / len(one_way))
    # add some time to return the car
    duration_buffer = pd.Series(
        [
            dt.timedelta(hours=h)
            for h in np.clip(
                np.random.normal(
                    mean_h_oneway, std_h_oneway, size=sum(one_way)
                ),
                0,
                None,
            )
        ]
    )
    sim_reservations.loc[one_way, "reservationto"] += duration_buffer
    sim_reservations.loc[one_way, "end_station_no"] = sim_reservations.loc[
        one_way, "start_station_no"
    ]

    # amend with some more information
    sim_reservations["drive_km"] = sim_reservations["distance"] / 1000
    sim_reservations["duration"] = (
        sim_reservations["reservationto"] - sim_reservations["reservationfrom"]
    ).total_seconds() / 3600
    print(
        "average duration of one way trips (after adding 2 hours):",
        np.mean((sim_reservations.loc[one_way, "duration"]).values),
    )
    print(
        "average duration of return trips:",
        np.mean(sim_reservations.loc[~one_way, "duration"].values),
    )

    return sim_reservations

