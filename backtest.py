"""
Backtest vectorisé simple du modèle sur la période de test hors échantillon.

Hypothèses simplificatrices (à garder en tête) :
- Exécution au prix de clôture de la bougie du signal.
- Coût = spread moyen observé (colonne 'spread', en points) + un slippage fixe.
- Une seule position à la fois, fermée après LABEL_HORIZON_BARS bougies
  OU si le stop-loss / take-profit est touché (approximation sur les high/low).
"""
import numpy as np
import pandas as pd

import config


def run_backtest(model, data: pd.DataFrame, X: pd.DataFrame, point: float = None) -> pd.DataFrame:
    """
    data : DataFrame complet (avec close/high/low/spread et l'index temporel) déjà
           aligné avec X (même index, post-dropna).
    point : "point" MT5 du symbole, pour convertir la colonne 'spread' (en points)
            en coût réel. Si None, retombe sur une approximation d'1 pip.
    """
    preds = model.predict(X)
    proba = model.predict_proba(X)
    classes = model.classes_
    confidences = proba.max(axis=1)

    sl = config.STOP_LOSS_PIPS * config.PIP_SIZE
    tp = config.TAKE_PROFIT_PIPS * config.PIP_SIZE
    horizon = config.LABEL_HORIZON_BARS

    trades = []
    closes = data["close"].values
    highs = data["high"].values
    lows = data["low"].values
    if point is not None and "spread" in data.columns:
        spread_costs = data["spread"].values * point
    else:
        spread_costs = np.full(len(data), config.PIP_SIZE)  # approx. 1 pip de coût par aller-retour
    idx = data.index

    n = len(data)
    for i in range(n - horizon):
        pred = preds[i]
        conf = confidences[i]
        if pred == 0 or conf < config.MIN_MODEL_CONFIDENCE:
            continue

        entry = closes[i]
        direction = 1 if pred == 1 else -1
        sl_price = entry - direction * sl
        tp_price = entry + direction * tp

        exit_price = closes[i + horizon]
        exit_reason = "horizon"
        for h in range(1, horizon + 1):
            hi, lo = highs[i + h], lows[i + h]
            if direction == 1:
                if lo <= sl_price:
                    exit_price, exit_reason = sl_price, "stop_loss"
                    break
                if hi >= tp_price:
                    exit_price, exit_reason = tp_price, "take_profit"
                    break
            else:
                if hi >= sl_price:
                    exit_price, exit_reason = sl_price, "stop_loss"
                    break
                if lo <= tp_price:
                    exit_price, exit_reason = tp_price, "take_profit"
                    break

        pnl_price = direction * (exit_price - entry) - spread_costs[i]
        pnl_pips = pnl_price / config.PIP_SIZE

        trades.append({
            "time": idx[i],
            "direction": "long" if direction == 1 else "short",
            "confidence": conf,
            "entry": entry,
            "exit": exit_price,
            "exit_reason": exit_reason,
            "pnl_pips": pnl_pips,
        })

    trades_df = pd.DataFrame(trades)
    return trades_df


def summarize(trades_df: pd.DataFrame) -> None:
    if trades_df.empty:
        print("Aucun trade généré sur la période de test "
              "(seuil de confiance trop élevé ou modèle trop prudent).")
        return

    n = len(trades_df)
    wins = (trades_df["pnl_pips"] > 0).sum()
    win_rate = wins / n * 100
    total_pips = trades_df["pnl_pips"].sum()
    avg_pips = trades_df["pnl_pips"].mean()

    gross_win = trades_df.loc[trades_df["pnl_pips"] > 0, "pnl_pips"].sum()
    gross_loss = -trades_df.loc[trades_df["pnl_pips"] < 0, "pnl_pips"].sum()
    profit_factor = gross_win / gross_loss if gross_loss > 0 else np.inf

    equity = trades_df["pnl_pips"].cumsum()
    running_max = equity.cummax()
    drawdown = equity - running_max
    max_drawdown = drawdown.min()

    print("\n=== Résumé du backtest ===")
    print(f"Nombre de trades      : {n}")
    print(f"Taux de réussite      : {win_rate:.1f}%")
    print(f"Total pips            : {total_pips:.1f}")
    print(f"Pips moyens / trade   : {avg_pips:.2f}")
    print(f"Profit factor         : {profit_factor:.2f}")
    print(f"Max drawdown (pips)   : {max_drawdown:.1f}")
    print("\nRappel : ceci ignore la taille réelle des lots, les commissions "
          "exactes du broker, et suppose une exécution parfaite. "
          "Un profit factor > 1.3-1.5 avec un nombre de trades suffisant "
          "(>100) est un minimum avant d'envisager la démo réelle.")
