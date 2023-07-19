import os
import sys
import pandas as pd
import argparse
import numpy as np
from sklearn.model_selection import train_test_split
from carsharing.mode_choice_models import RandomForestWrapper, rf_tuning
from carsharing.plotting import plot_confusion_matrix, plot_feature_importance

def prepare_data(trips, min_number_trips=200, return_normed=False, drop_columns=[]):
    # drop geometry if it exists
    dataset = trips.drop(["geom", "geom_origin", "geom_destination"] + drop_columns, axis=1, errors="ignore")
    print("Dataset raw", len(dataset))
    # only include frequently used modes (now it usually uses all because we preselect modes earlier!)
    nr_trips_with_mode = trips[[col for col in trips.columns if col.startswith("Mode")]].sum()
    included_modes = list(nr_trips_with_mode[nr_trips_with_mode > min_number_trips].index.tolist())
    print("included_modes", included_modes)

    # only get feature and label columns
    feat_cols = [col for col in dataset.columns if col.startswith("feat")]
    dataset = dataset[feat_cols + included_modes]

    # drop columns with too many nans:
    max_unavail = 0.1  # if more than 10% are NaN
    feature_avail_ratio = pd.isna(dataset).sum() / len(dataset)
    features_not_avail = feature_avail_ratio[feature_avail_ratio > max_unavail].index
    dataset.drop(features_not_avail, axis=1, inplace=True)
    print("dataset len now", len(dataset))

    # remove other NaNs (the ones because of missing origin or destination ID)
    dataset.dropna(inplace=True)
    print("dataset len after dropna", len(dataset))

    # convert features to array
    feat_cols = [col for col in dataset.columns if col.startswith("feat")]
    feat_array = dataset[feat_cols]

    labels = dataset[included_modes]
    print("labels", labels.shape, "features", feat_array.shape)

    if return_normed:
        # normalize
        feat_mean, feat_std = feat_array.mean(), feat_array.std()
        feat_array_normed = (feat_array - feat_mean) / feat_std
        return feat_array_normed, labels, (feat_mean, feat_std)

    return feat_array, labels

def fit_random_forest(trips_mobis, out_path=os.path.join("outputs", "mode_choice_model"), model_save_path="trained_models/test"):

    # prepare data
    drop_columns = [col for col in trips_mobis.columns if col.startswith("feat_prev_Mode") or col in [
        'feat_halbtax', 'feat_ga',
    #     # UNCOMMENT TO DROP FURTHER FEATURES (used to train xgb_simple.p)
    #   'feat_age', 'feat_sex', 'feat_caraccess', 'feat_employed',
    #    'feat_purpose_destination_home',
    #    'feat_purpose_destination_leisure', 'feat_purpose_destination_work',
    #    'feat_purpose_destination_shopping',
    #    'feat_purpose_destination_education', 'feat_purpose_origin_home',
    #    'feat_purpose_origin_leisure', 'feat_purpose_origin_work',
    #    'feat_purpose_origin_shopping', 'feat_purpose_origin_education',
    #    'feat_pt_accessibilityorigin', 'feat_pt_accessibilitydestination',
    ]]
    features, labels = prepare_data(trips_mobis, return_normed=False, drop_columns=drop_columns)
    print("fitting on features:", features.columns)

    # Tuning and reporting test data performance
    labels_max_str = np.array(labels.columns)[np.argmax(np.array(labels), axis=1)]
    X_train, X_test, y_train, y_test = train_test_split(features, labels_max_str, random_state=1)
    # find best max depth
    best_acc = 0
    for max_depth in [20, 30, 50, None]:
        acc = rf_tuning(X_train, X_test, y_train, y_test, max_depth=max_depth)
        # save best parameter
        if acc > best_acc:
            best_acc = acc
            final_max_depth = max_depth
    # report test data performance
    rf_tuning(X_train, X_test, y_train, y_test, max_depth=final_max_depth, plot_confusion=True, out_path=out_path)

    # Fit on whole training data:
    rf_wrapper = RandomForestWrapper(max_depth=final_max_depth)
    rf_wrapper.fit(features, labels)

    # save train accuracy
    train_pred = rf_wrapper(features)
    plot_confusion_matrix(train_pred, labels_max_str, traintest="TRAIN", out_path=out_path)

    # print most important features
    plot_feature_importance(rf_wrapper.feat_columns, rf_wrapper.rf.feature_importances_, out_path=out_path)

    # save model
    rf_wrapper.save(save_path=model_save_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s", "--model_save_path", type=str, default="trained_models/xgb.p", help="path to save model",
    )
    parser.add_argument(
        "-i",
        "--in_path_mobis",
        type=str,
        default=os.path.join("..", "..", "data", "mobis", "trips_features.csv"),
        help="path to mobis feature dataset",
    )
    parser.add_argument(
        "-o",
        "--out_path",
        type=str,
        default=os.path.join("outputs", "mode_choice_model"),
        help="path to save training results",
    )
    args = parser.parse_args()

    # out path is a new directory with the model name
    out_path = args.out_path
    os.makedirs(out_path, exist_ok=True)

    # load data
    trips_mobis = pd.read_csv(args.in_path_mobis)

    f = open(os.path.join(out_path, "stdout_model_train_test.txt"), "w")
    sys.stdout = f

    fit_random_forest(trips_mobis, out_path=out_path, model_save_path=args.model_save_path)

    f.close()

