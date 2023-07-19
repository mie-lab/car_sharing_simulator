import os
from carsharing.stations import place_new_stations, place_vehicles
if __name__ == "__main__":
    from carsharing.utils import read_trips_csv, write_stations_csv
    import argparse

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
        "-n",
        "--number_stations",
        type=int,
        default=100,
        help="How many stations to place",
    )
    args = parser.parse_args()

    trips = read_trips_csv(args.inp_path)
    stations = place_new_stations(args.number_stations, trips)
    stations = place_vehicles(stations)
    write_stations_csv(stations.reset_index(), args.out_path)
