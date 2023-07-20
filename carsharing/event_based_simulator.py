import os
import pandas as pd
import argparse
import numpy as np
from scipy.stats import poisson
from datetime import timedelta
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt


def chisquare(x, a, b, c):
    return a * x**c * np.exp(-b * x)


SIMULATED_DAY = pd.to_datetime("2023-02-01 00:00:00")
SIMULATE_WEEKEND = False  # we want to simulate a weekday


def load_real_reservations(in_path):
    res = pd.read_csv(in_path)
    res["reservationfrom"] = pd.to_datetime(res["reservationfrom"])
    res["reservationto"] = pd.to_datetime(res["reservationto"])
    res["duration"] = (res["reservationto"] - res["reservationfrom"]).dt.total_seconds() / 3600 # in hours
    res["hour"] = res["reservationfrom"].dt.hour
    res["weekend"] = res["reservationfrom"].dt.weekday > 4
    return res


def fit_distribution_params(real_reservations, plot_distributions=False):
    res = real_reservations.copy()
    # Compute total number of unique weekdays and weekend days --> each hour can occur this many times
    unique_weekdays = res.loc[~res["weekend"], "reservationfrom"].dt.date.sort_values().nunique()
    unique_weekend = res.loc[res["weekend"], "reservationfrom"].dt.date.sort_values().nunique()
    unique_weekdays, unique_weekend

    # distribution over stations
    # start with basic dataframe containing the station numbers as indices
    station_dist = res.groupby("start_station_no")[["start_station_no"]].count().rename({"start_station_no": "all"}, axis=1)
    poisson_params = {}
    distance_params = {}
    duration_params = {}

    for (w, h), res_subset in res.groupby(["weekend", "hour"]):
        # get rate
        if w:
            # 0.5 because getting the rate for half an hour
            poisson_params[(h, w)] = 0.5 * len(res_subset) / unique_weekend
        else:
            poisson_params[(h, w)] = 0.5 * len(res_subset) / unique_weekdays
            
        # get categorical distribution over stations
        station_dist_hour = res_subset.groupby("start_station_no")[["start_station_no"]].count().rename({"start_station_no": f"{int(w)}-{h}"}, axis=1)
        station_dist_hour = station_dist_hour / station_dist_hour.sum()
        station_dist = station_dist.merge(station_dist_hour, how="left", left_index=True, right_index=True)
        
        # get distance dist --> chisquare
        drive_km = res_subset.loc[(res_subset["drive_km"] < 300) & (res_subset["drive_km"]>0), "drive_km"]
        if plot_distributions:
            a = plt.hist(drive_km, bins=100)
        else:
            a = np.histogram(drive_km, bins=100)
        x = a[1][:-1]
        y = a[0] / 1000
        popt_dist, pcov = curve_fit(chisquare, x, y, p0=[0.1, 0.05, 0.3])
    #     print(popt_dist)
        if plot_distributions:
            xx = np.linspace(0, 100, 100)
            yy = chisquare(xx, *popt_dist)
            plt.plot(xx, yy * 1000, lw=5)
            plt.title("Distance")
            plt.show()
        # APPEND
        distance_params[(h, w)] = popt_dist
        
        # get duration dist --> chisquare
        duration = res_subset.loc[(res_subset["duration"] < 24) & (res_subset["duration"]>0), "duration"]
        if plot_distributions:
            a = plt.hist(duration, bins=100, color="blue")
        else:
            a = np.histogram(duration, bins=100)
        x = a[1][:-1]
        y = a[0] / 300
        try:
            popt_dur, _ = curve_fit(chisquare, x, y, p0=[10, 0.5, 1])
        except RuntimeError:
            # Sometimes the curve fitting does not converge
            print("Using parameters of previous hour")
            pass
        # print(popt_dur)
        if plot_distributions:
            xx = np.linspace(0, 24, 100)
            yy = chisquare(xx, *popt_dur)
            plt.plot(xx, yy * 300, lw=5)
            plt.title("Duration")
            plt.show()
        # APPEND
        duration_params[(h, w)] = popt_dur

    return {"station": station_dist, "duration": duration_params, 
            "distance": distance_params, "poisson": poisson_params} 
     

def simulated_eventbased(out_path, distribution_param_dict, w=False):
    slots = 48 # simulate one day, every half an hour
    slot_names = [SIMULATED_DAY + timedelta(minutes=30 * i) for i in range(48)]
    possible_durations = np.arange(0.5, 24, 0.5)
    booking_dfs = []
    for slot in range(slots):
        h = slot // 2
        num_bookings = poisson.rvs(distribution_param_dict["poisson"][(h, w)], size=1) # draw from poisson distribution the events / 0.5h
        
        # draw duration
        dur_params = distribution_param_dict["duration"][(h, w)]
        duration_probs = chisquare(possible_durations, *dur_params)
        booking_durations = np.random.choice(possible_durations, p = duration_probs / np.sum(duration_probs), size=num_bookings)

        # draw distance
        dist_params = distribution_param_dict["distance"][(h, w)]
        possible_distances = np.random.uniform(0, 200, 200)  # randomize
        distance_probs = chisquare(possible_distances, *dist_params)
        booking_distances = np.random.choice(possible_distances, p = distance_probs / np.sum(distance_probs), size=num_bookings)
        # TODO: duration not really aligned with distance (but it's the reservation duration, so maybe fine)
        
    #     print(num_bookings, booking_durations)
        # draw stations
        stations_avail = distribution_param_dict["station"][f"{int(w)}-{h}"]
        stations_avail = stations_avail.dropna()
    #     print(stations_avail)
        booking_stations = np.random.choice(stations_avail.index, p=stations_avail.values, size=num_bookings)
        
        booking_df = pd.DataFrame()
        booking_df["start_station_no"] = booking_stations
        booking_df["drive_km"] = booking_distances
        booking_df["duration"] = booking_durations
        booking_df["start_station_no"] = booking_stations
        booking_df["reservationfrom"] = slot_names[slot]
        booking_dfs.append(booking_df)
    booking_dfs = pd.concat(booking_dfs)

    # add reservationto
    booking_dfs["reservationto"] = [row["reservationfrom"] + timedelta(hours=row["duration"]) for i, row in booking_dfs.iterrows()]
    booking_dfs.reset_index(drop=True, inplace=True)
    booking_dfs.index.name = "reservation_no"
    booking_dfs.to_csv(os.path.join(out_path, "sim_reservations.csv"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--in_path",
        type=str,
        default=os.path.join("../../v2g4carsharing/data/reservation.csv"),
        help="Path to real reservations (used to fit the distributions)",
    )
    parser.add_argument(
        "-o",
        "--out_path",
        type=str,
        default=os.path.join("outputs", "event_based_simulation"),
        help="Path where to output the simulated reservations",
    )
    args = parser.parse_args()
    os.makedirs(args.out_path, exist_ok=True)

    real_reservations = load_real_reservations(args.in_path)
    fitted_parameters = fit_distribution_params(real_reservations, plot_distributions=False)
    simulated_eventbased(args.out_path, fitted_parameters, w=SIMULATE_WEEKEND)
