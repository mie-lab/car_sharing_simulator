import numpy as np
import pickle
import os
import time
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, balanced_accuracy_score, ConfusionMatrixDisplay

plt.style.use("seaborn")
import scipy
import seaborn as sns

sns.set(font_scale=1.4)


name_mapping = {
    "reservationfrom_sec": "Reservation start time (h)",
    "reservationto_sec": "Reservation end time (h)",
    "reservationfrom": "Reservation start time (h)",
    "reservationto": "Reservation end time (h)",
    "drive_km": "Distance (km)",
    "duration": "Duration (h)",
    "station": "Reservation count per station",
}


def plot_distribution(res_in, col_name, out_path=None):
    res = res_in.copy()
    plt.figure(figsize=(5, 5))
    sim_col_update = {}
    
    if col_name == "duration":
        res = res.dropna(subset=[col_name])
        bins = np.arange(24)
    elif col_name == "drive_km":
        bins = np.arange(0, 50, 1)
    elif col_name == "reservationfrom" or col_name == "reservationto":
        res[col_name] = pd.to_datetime(res[col_name])
        res[col_name] = res[col_name].dt.hour
        bins = np.arange(24)
    elif "station" in col_name:
        bins = np.arange(0, 2000, 50) # max 2000 km
    else:
        raise ValueError(f"column name {col_name} not supported")

    plt.hist(res[sim_col_update.get(col_name, col_name)], bins=bins)
    plt.xticks(fontsize=20)
    plt.xlabel(name_mapping.get(col_name, col_name), fontsize=20)
    plt.ylabel("Count")
    plt.yticks(fontsize=20)
    if col_name == "duration":
        plt.xlim(0, 24)

    plt.tight_layout()
    if out_path is not None:
        plt.savefig(os.path.join(out_path, "distribution_" + col_name + ".pdf"))
    else:
        plt.show()
        
def plot_station_dist(res, out_path=None):
    stations_sim_reservation = (
        res.groupby("start_station_no")
        .agg({"start_station_no": "count"})
        .rename(columns={"start_station_no": "Station-wise bookings"})
    )
    plt.figure(figsize=(8, 5))
    sns.histplot(data=stations_sim_reservation, x="Station-wise bookings")
    plt.ylabel("Number of stations")
    plt.tight_layout()
    if out_path is not None:
        plt.savefig(os.path.join(out_path, "bookings_per_station.pdf"))
    else:
        plt.show()
    
def plot_modal_split(sim_modes, out_path=None):
    modes_grouped = sim_modes.groupby("mode")["mode"].count()
    plt.figure(figsize=(8, 5))
    plt.bar(modes_grouped.index, modes_grouped)
    plt.xticks(np.arange(len(modes_grouped)), [g.split("::")[1] for g in modes_grouped.index], rotation=90)
    plt.xlabel("Mode")
    plt.ylabel("Count")
    plt.tight_layout()
    if out_path is not None:
        plt.savefig(os.path.join(out_path, "modal_split.pdf"))
    else:
        plt.show()


def plot_confusion_matrix(
    pred, labels_max_str, traintest="TRAIN", out_path=os.path.join("outputs", "mode_choice_model")
):
    print("----- ", traintest, "results")
    print("Acc:", accuracy_score(labels_max_str, pred))
    print("Balanced Acc:", balanced_accuracy_score(labels_max_str, pred))
    for confusion_mode in [None, "true", "pred"]:
        name = "" if confusion_mode is None else confusion_mode
        fig, ax = plt.subplots(1, 1, figsize=(10, 10))
        ConfusionMatrixDisplay.from_predictions(
            labels_max_str, pred, normalize=confusion_mode, xticks_rotation="vertical", values_format="2.2f", ax=ax
        )
        plt.tight_layout()
        plt.savefig(os.path.join(out_path, f"random_forest_{traintest}_confusion_{name}.png"))

def plot_feature_importance(features, feature_importances, out_path=os.path.join("outputs", "mode_choice_model")):
    sorted_feats = features[np.argsort(feature_importances)]
    sorted_importances = feature_importances[np.argsort(feature_importances)]
    plt.figure(figsize=(10, 7))
    plt.bar(sorted_feats, sorted_importances)
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.savefig(os.path.join(out_path, "feature_importances.png"))
