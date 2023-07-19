import argparse
import os
import pandas as pd
from carsharing.plotting import *

if __name__ == "__main__":        
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--in_path",
        type=str,
        default=os.path.join("outputs", "siouxfalls_sim"),
        help="path to simulated trips csv",
    )
    parser.add_argument(
        "-o",
        "--out_path",
        type=str,
        default=os.path.join("outputs", "siouxfalls_sim"),
        help="path to save output",
    )
    args = parser.parse_args()

    # Load results
    res = pd.read_csv(os.path.join(args.in_path, "sim_reservations.csv"))
    sim_modes = pd.read_csv(os.path.join(args.in_path, "sim_modes.csv"))

    plot_modal_split(sim_modes, out_path=args.out_path)
    plot_station_dist(res, out_path=args.out_path)
    for col in ["reservationfrom", "reservationto", "duration", "drive_km"]:
        plot_distribution(res, col, out_path=args.out_path)
