import os
from carsharing.trip_loading_utils import xml_to_activities, activities_to_trips

if __name__ == "__main__":
    from carsharing.utils import write_trips_csv
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--inp_path",
        type=str,
        default=os.path.join("data", "Siouxfalls_population.xml"),
        help="Path to XML file",
    )
    parser.add_argument(
        "-o",
        "--out_path",
        type=str,
        default=os.path.join("data", "siouxfalls_trips.csv"),
        help="Path where to output the trips",
    )
    args = parser.parse_args()

    act_df = xml_to_activities(args.inp_path, crs="EPSG:26914")
    trips_df = activities_to_trips(act_df)
    write_trips_csv(trips_df, args.out_path)
