import pandas as pd
from shapely import wkt
import geopandas as gpd
from ast import literal_eval


def read_trips_csv(path, geom_col="geom_origin", crs="EPSG:4326"):
    trips = pd.read_csv(path)
    trips["geom_origin"] = trips["geom_origin"].apply(wkt.loads)
    trips["geom_destination"] = trips["geom_destination"].apply(wkt.loads)
    for time_col in ["started_at_origin", "started_at_destination"]:
        if time_col in trips.columns:
            trips[time_col] = pd.to_datetime(trips[time_col])
    trips = gpd.GeoDataFrame(trips)
    trips.set_geometry(geom_col, inplace=True)
    trips.crs = crs
    return trips


def write_trips_csv(trips, path):
    trips_out = trips.copy()
    trips_out["geom_origin"] = trips_out["geom_origin"].apply(wkt.dumps)
    trips_out["geom_destination"] = trips_out["geom_destination"].apply(
        wkt.dumps
    )
    trips_out.to_csv(path, index=False)


def write_stations_csv(stations, path):
    stations_out = stations.copy()
    stations_out["geom"] = stations_out["geom"].apply(wkt.dumps)
    stations_out.to_csv(path, index=False)


def read_stations_csv(path, geom_col="geom", crs="EPSG:4326"):
    station_df = pd.read_csv(
        path, index_col="station_no", converters={"vehicle_list": literal_eval}
    ).rename(columns={geom_col: "geom"})
    station_df["geom"] = station_df["geom"].apply(wkt.loads)
    station_df = gpd.GeoDataFrame(station_df, geometry="geom", crs=crs)
    return station_df
