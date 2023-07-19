import os
from carsharing.features import ModeChoiceFeatures


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

