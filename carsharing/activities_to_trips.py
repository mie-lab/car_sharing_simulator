import os
import xmltodict
from collections import defaultdict
import pandas as pd
import geopandas as gpd


def xml_to_activities(xml_path, crs="EPSG:4326"):
    with open(xml_path, "r") as myfile:
        obj = xmltodict.parse(myfile.read())

    out_dict = defaultdict(list)

    for entry in obj["population"]["person"]:
        if isinstance(entry["plan"]["act"], list):
            prev_end_time = "00:00:00"
            for i, act in enumerate(entry["plan"]["act"]):
                if "@x" not in act.keys():
                    continue
                out_dict["person_id"].append(entry["@id"])
                out_dict["feat_sex"].append(entry["@sex"])
                out_dict["feat_age"].append(entry["@age"])
                out_dict["feat_employed"].append(entry["@employed"])
                out_dict["feat_caraccess"].append(entry["@car_avail"])
                out_dict["activity_index"].append(i)
                out_dict["purpose"].append(act["@type"])
                # add start time
                if "@start_time" in act.keys():
                    out_dict["started_at"].append(act["@start_time"])
                else:
                    out_dict["started_at"].append(prev_end_time)
                # update prev end time
                if "@end_time" in act.keys():
                    prev_end_time = act["@end_time"]
                out_dict["x"].append(act["@x"])
                out_dict["y"].append(act["@y"])
    out_df = pd.DataFrame(out_dict)
    # transform to gdf
    out_df = gpd.GeoDataFrame(
        out_df,
        geometry=gpd.points_from_xy(x=out_df["x"], y=out_df["y"]),
        crs=crs,
    ).drop(["x", "y"], axis=1)
    return out_df


def activities_to_trips(act_df):
    act_df.sort_values(["person_id", "activity_index"], inplace=True)
    act_df["geom_origin"] = act_df["geometry"].shift(1)
    act_df["distance"] = act_df.distance(act_df["geom_origin"])
    act_df["purpose_origin"] = act_df["purpose"].shift(1)
    act_df["started_at_origin"] = act_df["started_at"].shift(1)
    caraccess_dict = {"always": 1, "never": 0}
    act_df["feat_caraccess"] = act_df["feat_caraccess"].apply(
        lambda x: caraccess_dict.get(x, 0.5)
    )
    act_df["feat_sex"] = act_df["feat_sex"].apply(
        lambda x: 0 if x == "m" else 1
    )
    act_df["feat_employed"] = act_df["feat_employed"].map({"yes": 1, "no": 0})
    act_df["purpose"] = act_df["purpose"].apply(
        lambda x: x if x in ["home", "work", "leisure", "shopping"] else "other"
    )
    # TODO: is it a problem if the time is not in seconds-of-day
    act_df = act_df[act_df["activity_index"] != 0]
    act_df = act_df.rename(
        columns={
            "geometry": "geom_destination",
            "purpose": "purpose_destination",
            "started_at": "started_at_destination",
        }
    )
    return act_df


if __name__ == "__main__":
    from carsharing.utils import write_trips_csv
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--inp_path",
        type=str,
        default=os.path.join("data", "siouxfalls_population.xml"),
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
