import os
import time
import pickle
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely import wkt


def station_placement_kmeans(X, k, fixed_stations):
    x_df = pd.DataFrame(X)
    diff = 1
    cluster = np.zeros(X.shape[0])
    is_not_fixed = np.ones(X.shape[0])
    centroids_not_fixed = x_df.sample(n=k).values
    fixed_centroid_nr = len(fixed_stations)
    while diff:
        centroids = np.concatenate(
            (fixed_stations, centroids_not_fixed), axis=0
        )
        # for each observation
        tic = time.time()
        for i, row in enumerate(X):
            dists = np.sum((centroids - row) ** 2, axis=1)
            cluster[i] = np.argmin(dists)
            is_not_fixed[i] = cluster[i] >= fixed_centroid_nr
        print("time one iteration of Kmeans:", time.time() - tic)

        fixed_indicator = is_not_fixed.astype(bool)
        new_centroids = (
            x_df[fixed_indicator]
            .groupby(by=cluster[fixed_indicator])
            .mean()
            .values
        )

        if len(new_centroids) < len(centroids_not_fixed):
            # if some centroids got lost (no population assigned), reinitialize
            init_new = x_df.sample(
                n=len(centroids_not_fixed) - len(new_centroids)
            ).values
            new_centroids = np.concatenate((new_centroids, init_new), axis=0)
            print("reinitialize stations", len(init_new))

        # if centroids are same then leave
        if np.count_nonzero(centroids_not_fixed - new_centroids) == 0:
            diff = 0
            new_centroids_median = (
                x_df[fixed_indicator]
                .groupby(by=cluster[fixed_indicator])
                .median()
                .values
            )  # changed to median
            centroids = np.concatenate(
                (fixed_stations, new_centroids_median), axis=0
            )
        else:
            centroids_not_fixed = new_centroids

    return centroids, cluster


def place_new_stations(
    nr_new_stations, trips_simple, station_locations=None,
):
    # use geom_origin
    if not isinstance(trips_simple, gpd.GeoDataFrame):
        trips_simple["geom_origin"] = trips_simple["geom_origin"].apply(
            wkt.loads
        )
        trips_simple = gpd.GeoDataFrame(trips_simple, geometry="geom_origin")

    # convert to numpy array
    population_locations = np.vstack(
        [trips_simple.geometry.x.values, trips_simple.geometry.y.values]
    ).swapaxes(1, 0)

    if station_locations is None:
        station_locations = np.zeros((0, 2))

    # run kmeans
    centroids, _ = station_placement_kmeans(
        population_locations, nr_new_stations, station_locations
    )

    # assert that the fixed stations remain the same
    if station_locations is not None:
        assert np.all(centroids[: len(station_locations)] == station_locations)
    # make GDF of new stations
    new_stations_gdf = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(
            x=centroids[len(station_locations) :, 0],
            y=centroids[len(station_locations) :, 1],
        )
    )
    return new_stations_gdf
