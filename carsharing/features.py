import pandas as pd
import numpy as np
import os
import time
import json
import trackintel as ti
import geopandas as gpd
from shapely import wkt
from datetime import timedelta

from carsharing.utils import write_trips_csv


def compute_dist_to_station(trips, station):
    # delete columns if they already exist
    assert trips.crs == station.crs, "Trips and stations must have the same CRS"
    initial_crs = trips.crs
    trips.drop(
        [
            "distance_to_station_origin",
            "closest_station_origin",
            "index_right",
            "distance_to_station_destination",
            "closest_station_destination",
        ],
        axis=1,
        inplace=True,
        errors="ignore",
    )
    # get closest station to origin
    trips.set_geometry("geom_origin", inplace=True)
    trips = trips.sjoin_nearest(
        station[["geom"]], distance_col="distance_to_station_origin"
    )
    trips.rename(
        columns={"index_right": "closest_station_origin"}, inplace=True
    )
    # get closest station to destination
    trips.set_geometry("geom_destination", inplace=True)
    trips.crs = initial_crs
    trips = trips.sjoin_nearest(
        station[["geom"]], distance_col="distance_to_station_destination"
    )
    trips.rename(
        columns={"index_right": "closest_station_destination"}, inplace=True
    )
    return trips


class ModeChoiceFeatures:
    def __init__(self, trips, stations):
        self.trips = trips
        self.stations = stations
        self.initial_crs = self.trips.crs

    def subsample(self, nr_users_desired=100000):
        persons_sim = self.trips["person_id"].unique()
        rand_inds = np.random.permutation(len(persons_sim))[:nr_users_desired]
        persons_sampled = persons_sim[rand_inds]
        self.trips = self.trips[self.trips["person_id"].isin(persons_sampled)]
        print(
            f"After subsampling, there are {self.trips['person_id'].nunique()}\
                 unique persons in the simulated data"
        )

    def add_purpose_features(
        self,
        col_name="purpose_destination",
        included_purposes=["home", "leisure", "work", "shopping", "education"],
    ):
        occuring = self.trips[col_name].unique()
        included_w_prefix = [
            "feat_" + col_name + "_" + p for p in included_purposes
        ]
        included_and_occuring = [
            p for p in included_w_prefix if p.split("_")[-1] in occuring
        ]
        one_hot = pd.get_dummies(
            self.trips[col_name], prefix="feat_" + col_name
        )[included_and_occuring]
        for p in included_w_prefix:
            if p not in included_and_occuring:
                one_hot[p] = 0
        self.trips = self.trips.merge(
            one_hot, left_index=True, right_index=True
        )

    def add_distance_feature(self):
        # add distance feature
        dest_geom = gpd.GeoSeries(self.trips["geom_destination"])
        dest_geom.crs = self.initial_crs
        start_geom = gpd.GeoSeries(self.trips["geom_origin"])
        start_geom.crs = self.initial_crs
        self.trips["feat_distance"] = start_geom.distance(dest_geom)

    def add_pt_accessibility(
        self,
        pt_accessibility,
        class_col="class",
        origin_or_destination="origin",
    ):
        """
        Arguments:
            pt_accessibility: GeoDataFrame with polygons as geometry and
            corresponding accessibility class with column name class_col
            class_col: str, name of column with accessibility class (column must
            contain numeric values)
        """
        self.trips = gpd.GeoDataFrame(
            self.trips, geometry="geom_" + origin_or_destination
        )
        self.trips = self.trips.sjoin(pt_accessibility, how="left")
        self.trips = self.trips.drop(["index_right"], axis=1).rename(
            columns={class_col: "feat_pt_accessibility" + origin_or_destination}
        )

    def add_weather(self):
        # import of meteostat here in order to remove the requirement
        from meteostat import Hourly, Daily
        from meteostat import Point as MeteoPoint

        def get_daily_weather(row):
            loc = MeteoPoint(
                row["geom_destination"].y, row["geom_destination"].x
            )
            end = row["started_at_destination"].replace(tzinfo=None)
            data = Daily(loc, end - timedelta(days=1, minutes=1), end).fetch()
            if len(data) == 1:
                return pd.Series(data.iloc[0])
            else:
                for random_testing in [100, 250, 500]:
                    loc = MeteoPoint(
                        row["geom_destination"].y,
                        row["geom_destination"].x,
                        random_testing,
                    )
                    data = Daily(loc, end - timedelta(days=1), end).fetch()
                    if len(data) == 1:
                        return pd.Series(data.iloc[0])
                return pd.NA

        weather_input = self.trips[
            ["started_at_destination", "geom_destination"]
        ].dropna()
        weather_input["geom_destination"] = weather_input[
            "geom_destination"
        ].to_crs("EPSG:4326")
        weather_data = weather_input.apply(get_daily_weather, axis=1)

        weather_data["prcp"] = weather_data["prcp"].fillna(0)
        weather_data.rename(
            columns={c: "feat_weather_" + c for c in weather_data.columns},
            inplace=True,
        )
        self.trips = self.trips.merge(
            weather_data, how="left", left_index=True, right_index=True
        )

    def add_dist2station(self):
        """Compute distance to next car sharing station"""
        self.trips = compute_dist_to_station(self.trips, self.stations)

        # use as features as well as for car sharing data generation
        for col in ["origin", "destination"]:
            self.trips["feat_distance_to_station_" + col] = self.trips[
                "distance_to_station_" + col
            ].copy()

    def add_time_features(self, origin_or_destination="origin"):
        col_name = "started_at_" + origin_or_destination
        self.trips[col_name] = pd.to_datetime(self.trips[col_name])
        self.trips[f"feat_{origin_or_destination}_hour"] = self.trips[
            col_name
        ].apply(lambda x: x.hour)
        self.trips[f"feat_{origin_or_destination}_day"] = self.trips[
            col_name
        ].apply(lambda x: x.dayofweek if ~pd.isna(x) else print(x))

    def fake_ht_ga_features(self):
        self.trips["feat_ga"] = 0
        self.trips["feat_halbtax"] = 0

    def add_all_features(self, pt_accessibility_gdf=None):
        tic = time.time()
        self.add_distance_feature()
        before_distance_0_removal = len(self.trips)
        self.trips = self.trips[self.trips["feat_distance"] > 0]
        print(
            "Removed distance-0-trips (in %):",
            1 - len(self.trips) / before_distance_0_removal,
        )
        print(time.time() - tic, "\nAdd purpose:")
        tic = time.time()
        self.add_purpose_features("purpose_destination")
        self.add_purpose_features("purpose_origin")
        if pt_accessibility_gdf is not None:
            print(time.time() - tic, "\nAdd pt accessibility:")
            tic = time.time()
            self.add_pt_accessibility(origin_or_destination="origin")
            self.add_pt_accessibility(origin_or_destination="destination")
        else:
            # model is trained on [0, 1, 2, 3, 4] where 0 is worst
            self.trips["feat_pt_accessibilitydestination"] = 1
            self.trips["feat_pt_accessibilityorigin"] = 1
        print(time.time() - tic, "\nAdd dist2station:")
        tic = time.time()
        self.add_dist2station()
        print(time.time() - tic, "\nAdd time:")
        tic = time.time()
        self.add_time_features(origin_or_destination="origin")
        self.add_time_features(origin_or_destination="destination")
        print(time.time() - tic)

    def save(self, out_path, remove_geom=False):
        # remove geom (for more efficient saving)
        if remove_geom:
            out_trips = self.trips.drop(
                [col for col in self.trips.columns if "geom" in col], axis=1
            )
        else:
            out_trips = self.trips
        write_trips_csv(out_trips, out_path)


if __name__ == "__main__":
    import argparse
    from carsharing.utils import read_trips_csv, read_stations_csv

    # args
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--in_path",
        type=str,
        default=os.path.join("data", "siouxfalls_trips.csv"),
        help="path to trips",
    )
    parser.add_argument(
        "-s",
        "--station_path",
        type=str,
        default=os.path.join("data", "stations.csv"),
    )
    parser.add_argument(
        "-k",
        "--keep_geom",
        default=1,
        type=int,
        help="if set to 1, keep the geometry column",
    )
    parser.add_argument(
        "-o",
        "--out_path",
        type=str,
        default=os.path.join("data", "siouxfalls_trips_features.csv"),
    )
    args = parser.parse_args()

    trips = read_trips_csv(args.in_path, crs="EPSG:26914")
    stations = read_stations_csv(
        args.station_path, geom_col="geometry", crs="EPSG:26914"
    )

    feat_collector = ModeChoiceFeatures(trips, stations)
    feat_collector.add_all_features()
    feat_collector.save(
        out_path=args.out_path, remove_geom=(not args.keep_geom)
    )

