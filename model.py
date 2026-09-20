"""
Entraînement, évaluation et persistance du modèle ML.

Utilise un split CHRONOLOGIQUE (jamais de shuffle) : on entraîne sur le
passé, on teste sur une période plus récente jamais vue à l'entraînement.
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

import config
from features import FEATURE_COLUMNS


def chronological_split(X: pd.DataFrame, y: pd.Series):
    if config.TRAIN_TEST_SPLIT_DATE:
        split_date = pd.Timestamp(config.TRAIN_TEST_SPLIT_DATE)
        train_mask = X.index < split_date
    else:
        split_idx = int(len(X) * 0.8)
        split_date = X.index[split_idx]
        train_mask = np.arange(len(X)) < split_idx

    X_train, X_test = X[train_mask], X[~train_mask]
    y_train, y_test = y[train_mask], y[~train_mask]
    print(f"[split] train={len(X_train)} lignes (jusqu'à {X_train.index[-1] if len(X_train) else 'N/A'}) "
          f"| test={len(X_test)} lignes (depuis {X_test.index[0] if len(X_test) else 'N/A'})")
    return X_train, X_test, y_train, y_test


def train_model(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        min_samples_leaf=50,   # limite le sur-apprentissage
        class_weight="balanced",
        random_state=config.RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series) -> None:
    preds = model.predict(X_test)
    print("\n=== Rapport de classification (hors échantillon) ===")
    print(classification_report(y_test, preds, digits=3))
    print("Matrice de confusion (lignes=réel, colonnes=prédit) [-1, 0, 1] :")
    print(confusion_matrix(y_test, preds, labels=[-1, 0, 1]))

    # Importance des features
    importances = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS)
    print("\nImportance des features :")
    print(importances.sort_values(ascending=False).round(3).to_string())


def save_model(model, path: str = None) -> None:
    path = path or config.MODEL_PATH
    joblib.dump(model, path)
    print(f"[model] Modèle sauvegardé -> {path}")


def load_model(path: str = None):
    path = path or config.MODEL_PATH
    return joblib.load(path)


def predict_with_confidence(model, X_row: pd.DataFrame):
    """Retourne (classe_prédite, probabilité_associée) pour la dernière ligne."""
    proba = model.predict_proba(X_row)[-1]
    classes = model.classes_
    best_idx = np.argmax(proba)
    return classes[best_idx], proba[best_idx]
