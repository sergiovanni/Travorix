"""
Pipeline complet : connexion MT5 -> données -> features -> entraînement ->
évaluation -> backtest -> sauvegarde du modèle.

Usage :
    python train.py
"""
import config
import data_loader
import model as model_module
from features import prepare_dataset
from backtest import run_backtest, summarize


def main():
    data_loader.connect()
    try:
        print(f"[data] Téléchargement de {config.HISTORY_YEARS} ans de "
              f"{config.SYMBOL} en {config.TIMEFRAME}...")
        raw = data_loader.fetch_history()
        print(f"[data] {len(raw)} bougies récupérées "
              f"({raw.index[0]} -> {raw.index[-1]})")
    finally:
        data_loader.disconnect()

    X, y, full_data = prepare_dataset(raw)
    print(f"[features] {len(X)} lignes exploitables après nettoyage")
    print(f"[labels] distribution :\n{y.value_counts()}")

    X_train, X_test, y_train, y_test = model_module.chronological_split(X, y)

    print("\n[train] Entraînement du modèle...")
    clf = model_module.train_model(X_train, y_train)

    model_module.evaluate_model(clf, X_test, y_test)

    print("\n[backtest] Simulation sur la période de test...")
    test_data = full_data.loc[X_test.index]
    trades = run_backtest(clf, test_data, X_test)
    summarize(trades)

    model_module.save_model(clf)


if __name__ == "__main__":
    main()
