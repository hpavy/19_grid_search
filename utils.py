# Les fonctions utiles ici
import pandas as pd
import numpy as np
from pathlib import Path
import torch.nn as nn
import torch.optim as optim
from model import PINNs
import torch
import scipy


def write_csv(data, path, file_name):
    dossier = Path(path)
    df = pd.DataFrame(data)
    # Créer le dossier si il n'existe pas
    dossier.mkdir(parents=True, exist_ok=True)
    df.to_csv(path + file_name)


def read_csv(path):
    return pd.read_csv(path)


def charge_data(hyper_param, param_adim):
    """
    Charge the data of X_full, U_full with every points
    And X_train, U_train with less points
    """
    # La data
    # On adimensionne la data
    df = pd.read_csv("data_john_2024.csv")
    df_modified = df[
        (df["Points:0"] >= hyper_param["x_min"])
        & (df["Points:0"] <= hyper_param["x_max"])
        & (df["Points:1"] >= hyper_param["y_min"])
        & (df["Points:1"] <= hyper_param["y_max"])
        & (df["Time"] > hyper_param["t_min"])
        & (df["Time"] < hyper_param["t_max"])
        & (df["Points:2"] == 0.0)
        # pour ne pas avoir dans le cylindre
        & (df["Points:0"]**2+df["Points:1"]**2 > (0.025/2)**2)
    ]
    # Uniquement la fin de la turbulence

    x_full, y_full, t_full = (
        np.array(df_modified["Points:0"])/param_adim['L'],
        np.array(df_modified["Points:1"])/param_adim['L'],
        np.array(df_modified["Time"])/(param_adim['L']/param_adim['V']),
    )
    u_full, v_full, p_full = (
        np.array(df_modified["Velocity:0"])/param_adim['V'],
        np.array(df_modified["Velocity:1"])/param_adim['V'],
        np.array(df_modified["Pressure"]) /
        ((param_adim['V']**2)*param_adim['rho']),
    )

    x_norm_full = (x_full - x_full.mean()) / x_full.std()
    y_norm_full = (y_full - y_full.mean()) / y_full.std()
    t_norm_full = (t_full - t_full.mean()) / t_full.std()
    p_norm_full = (p_full - p_full.mean()) / p_full.std()
    u_norm_full = (u_full - u_full.mean()) / u_full.std()
    v_norm_full = (v_full - v_full.mean()) / v_full.std()

    X_full = np.array(
        [x_norm_full, y_norm_full, t_norm_full], dtype=np.float32).T
    U_full = np.array(
        [u_norm_full, v_norm_full, p_norm_full], dtype=np.float32).T

    x_int = (x_norm_full.max()-x_norm_full.min())/hyper_param['nb_points_axes']
    y_int = (y_norm_full.max()-y_norm_full.min())/hyper_param['nb_points_axes']
    X_train = np.zeros((0, 3))
    U_train = np.zeros((0, 3))

    for time in np.unique(t_norm_full):
        # les points autour du cylindre dans un rayon de 0.025
        masque = (
            ((x_full**2 + y_full**2) < ((0.025/param_adim['L'])**2))
            & (t_norm_full == time))
        indice = np.random.choice(
                        np.arange(len(x_norm_full[masque])), size=hyper_param['nb_points_close_cylinder'], replace=False)
        new_x = np.concatenate(
            (
                x_norm_full[masque][indice].reshape(-1, 1),
                y_norm_full[masque][indice].reshape(-1, 1),
                t_norm_full[masque][indice].reshape(-1, 1)
            ), axis=1
        )
        new_y = np.concatenate(
            (
                u_norm_full[masque][indice].reshape(-1, 1),
                v_norm_full[masque][indice].reshape(-1, 1),
                p_norm_full[masque][indice].reshape(-1, 1)
            ), axis=1
        )
        X_train = np.concatenate((X_train, new_x))
        U_train = np.concatenate((U_train, new_y))

        # les points sur chaque axe
        for x_num in range(hyper_param['nb_points_axes']):
            for y_num in range(hyper_param['nb_points_axes']):
                masque = (
                    (x_norm_full > x_norm_full.min()+x_int*x_num)
                    & (x_norm_full < x_norm_full.min()+(x_num+1)*x_int)
                    & (y_norm_full < y_norm_full.min()+(y_num+1)*y_int)
                    & (y_norm_full > y_norm_full.min()+(y_num)*y_int)
                    & (t_norm_full == time)
                )
                if len(x_norm_full[masque]) > 0:
                    indice = np.random.choice(
                        np.arange(len(x_norm_full[masque])), size=1, replace=False)
                    new_x = np.array(
                        [
                            x_norm_full[masque][indice],
                            y_norm_full[masque][indice],
                            t_norm_full[masque][indice]

                        ]
                    ).reshape(-1, 3)
                    new_y = np.array(
                        [
                            u_norm_full[masque][indice],
                            v_norm_full[masque][indice],
                            p_norm_full[masque][indice]

                        ]
                    ).reshape(-1, 3)
                    X_train = np.concatenate((X_train, new_x))
                    U_train = np.concatenate((U_train, new_y))

    # les points du bord

    nb_border = hyper_param['nb_border']
    teta_int = np.linspace(0, 2*np.pi, nb_border)
    X_border = np.zeros((0, 3))
    for time in np.unique(t_norm_full):
        for teta in teta_int:
            x_ = ((((0.025/2)*np.cos(teta)) /
                  param_adim['L'])-x_full.mean())/x_full.std()
            y_ = ((((0.025/2)*np.sin(teta)) /
                  param_adim['L'])-y_full.mean())/y_full.std()
            new_x = np.array(
                [
                    x_,
                    y_,
                    time
                ]
            ).reshape(-1, 3)
            X_border = np.concatenate((X_border, new_x))

    teta_int_test = np.linspace(0, 2*np.pi, 1000)
    X_border_test = np.zeros((0, 3))
    for time in np.unique(t_norm_full):
        for teta in teta_int_test:
            x_ = ((((0.025/2)*np.cos(teta)) /
                  param_adim['L'])-x_full.mean())/x_full.std()
            y_ = ((((0.025/2)*np.sin(teta)) /
                  param_adim['L'])-y_full.mean())/y_full.std()
            new_x = np.array(
                [
                    x_,
                    y_,
                    time
                ]
            ).reshape(-1, 3)
            X_border_test = np.concatenate((X_border_test, new_x))

    mean_std = {
        "u_mean": u_full.mean(),
        "v_mean": v_full.mean(),
        "p_mean": p_full.mean(),
        "x_mean": x_full.mean(),
        "y_mean": y_full.mean(),
        "t_mean": t_full.mean(),
        "x_std": x_full.std(),
        "y_std": y_full.std(),
        "t_std": t_full.std(),
        "u_std": u_full.std(),
        "v_std": v_full.std(),
        "p_std": p_full.std(),
    }

    return X_train, U_train, X_full, U_full, X_border, X_border_test, mean_std


def init_model(f, hyper_param, device, folder_result):
    model = PINNs(hyper_param).to(device)
    optimizer = optim.Adam(model.parameters(), lr=hyper_param["lr_init"])
    scheduler = torch.optim.lr_scheduler.ExponentialLR(
        optimizer, gamma=hyper_param["gamma_scheduler"]
    )
    loss = nn.MSELoss()
    # Si on fait du transfert
    if hyper_param["transfert_learning"] == "None":
        # On regarde si notre modèle n'existe pas déjà
        if Path(folder_result + "/model_weights.pth").exists():
            # Charger l'état du modèle et de l'optimiseur
            checkpoint = torch.load(folder_result + "/model_weights.pth")
            model.load_state_dict(checkpoint["model_state_dict"])
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
            print("\nModèle chargé\n", file=f)
            print("\nModèle chargé\n")
            csv_train = read_csv(folder_result + "/train_loss.csv")
            csv_test = read_csv(folder_result + "/test_loss.csv")
            train_loss = {
                "total": list(csv_train["total"]),
                "data": list(csv_train["data"]),
                "pde": list(csv_train["pde"]),
                "border": list(csv_train["border"])
            }
            test_loss = {
                "total": list(csv_test["total"]),
                "data": list(csv_test["data"]),
                "pde": list(csv_test["pde"]),
                "border": list(csv_test["border"])
            }
            print("\nLoss chargée\n", file=f)
            print("\nLoss chargée\n")

        else:
            print("Nouveau modèle\n", file=f)
            print("Nouveau modèle\n")
            train_loss = {"total": [], "data": [], "pde": [], "border": []}
            test_loss = {"total": [], "data": [], "pde": [], "border": []}
    else:
        print("transfert learning")
        # Charger l'état du modèle et de l'optimiseur
        checkpoint = torch.load(
            hyper_param["transfert_learning"] + "/model_weights.pth"
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        print("\nModèle chargé\n", file=f)
        print("\nModèle chargé\n")
        train_loss = {
            "total": [],
            "data": [],
            "pde": [],
        }
        test_loss = {
            "total": [],
            "data": [],
            "pde": [],
        }
    return model, optimizer, scheduler, loss, train_loss, test_loss


if __name__ == "__main__":
    write_csv([[1, 2, 3], [4, 5, 6]], "ready_cluster/piche/test.csv")
