"""
Feature engineering et construction des labels pour l'entraînement.

Toutes les features sont calculées uniquement à partir de données PASSÉES
(rien qui "voit" le futur), pour éviter le look-ahead bias.
"""
import numpy as np
import pandas as pd

import config


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Construit les colonnes de features à partir d'un DataFrame OHLCV."""
    out = df.copy()

    # Rendements
    out["ret_1"] = out["close"].pct_change(1)
    out["ret_4"] = out["close"].pct_change(4)
    out["ret_12"] = out["close"].pct_change(12)

    # Moyennes mobiles et écart au prix
    for w in (10, 20, 50, 100):
        out[f"sma_{w}"] = out["close"].rolling(w).mean()
        out[f"dist_sma_{w}"] = (out["close"] - out[f"sma_{w}"]) / out[f"sma_{w}"]

    # Volatilité
    out["volatility_20"] = out["ret_1"].rolling(20).std()
    out["atr_14"] = (out["high"] - out["low"]).rolling(14).mean()

    # RSI / MACD
    out["rsi_14"] = _rsi(out["close"], 14)
    macd_line, signal_line, hist = _macd(out["close"])
    out["macd_hist"] = hist

    # Position dans le range récent
    roll_high = out["high"].rolling(20).max()
    roll_low = out["low"].rolling(20).min()
    out["range_pos_20"] = (out["close"] - roll_low) / (roll_high - roll_low)

    # Saisonnalité intra-journalière / hebdo
    out["hour"] = out.index.hour
    out["day_of_week"] = out.index.dayofweek

    # Spread (coût implicite)
    out["spread"] = out["spread"]

    return out


def build_labels(df: pd.DataFrame) -> pd.Series:
    """
    Label à 3 classes basé sur le mouvement futur du prix :
      1  -> hausse d'au moins LABEL_THRESHOLD_PIPS sur LABEL_HORIZON_BARS
     -1  -> baisse d'au moins LABEL_THRESHOLD_PIPS
      0  -> mouvement insuffisant (on ne trade pas)
    """
    horizon = config.LABEL_HORIZON_BARS
    threshold = config.LABEL_THRESHOLD_PIPS * config.PIP_SIZE

    future_close = df["close"].shift(-horizon)
    move = future_close - df["close"]

    label = pd.Series(0, index=df.index)
    label[move >= threshold] = 1
    label[move <= -threshold] = -1
    return label


FEATURE_COLUMNS = [
    "ret_1", "ret_4", "ret_12",
    "dist_sma_10", "dist_sma_20", "dist_sma_50", "dist_sma_100",
    "volatility_20", "atr_14", "rsi_14", "macd_hist",
    "range_pos_20", "hour", "day_of_week", "spread",
]


def prepare_dataset(df: pd.DataFrame):
    """Retourne (X, y) prêts pour l'entraînement, nettoyés des NaN."""
    feats = build_features(df)
    labels = build_labels(df)

    data = feats.copy()
    data["label"] = labels
    data = data.dropna(subset=FEATURE_COLUMNS + ["label"])

    X = data[FEATURE_COLUMNS]
    y = data["label"]
    return X, y, data
