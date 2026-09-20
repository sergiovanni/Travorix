"""
Connexion au terminal MT5 et récupération des données OHLCV.

IMPORTANT : le package `MetaTrader5` ne fonctionne qu'avec un terminal
MetaTrader 5 réellement installé et lancé (Windows nativement, ou via
Wine sur Linux/Mac). Ce module échouera si aucun terminal n'est trouvé.
"""
import sys
from datetime import datetime, timedelta

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

import config

TIMEFRAME_MAP = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


def _require_mt5():
    if mt5 is None:
        sys.exit(
            "Le package 'MetaTrader5' n'est pas installé ou n'est pas "
            "disponible sur cet OS. Installe-le avec `pip install MetaTrader5` "
            "sur une machine Windows (ou Linux/Mac via Wine) où le terminal "
            "MT5 est installé."
        )


def connect() -> None:
    """Initialise la connexion au terminal MT5."""
    _require_mt5()

    kwargs = {}
    if config.MT5_PATH:
        kwargs["path"] = config.MT5_PATH

    if not mt5.initialize(**kwargs):
        sys.exit(f"Échec de l'initialisation MT5 : {mt5.last_error()}")

    if config.MT5_LOGIN and config.MT5_PASSWORD and config.MT5_SERVER:
        authorized = mt5.login(
            login=config.MT5_LOGIN,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
        )
        if not authorized:
            mt5.shutdown()
            sys.exit(f"Échec du login MT5 : {mt5.last_error()}")

    account_info = mt5.account_info()
    if account_info is None:
        mt5.shutdown()
        sys.exit("Impossible de récupérer les infos du compte MT5.")

    print(f"[MT5] Connecté au compte {account_info.login} "
          f"({'DEMO' if account_info.trade_mode == 0 else 'RÉEL'}), "
          f"solde={account_info.balance} {account_info.currency}")


def disconnect() -> None:
    if mt5 is not None:
        mt5.shutdown()


def is_demo_account() -> bool:
    """Retourne True si le compte connecté est un compte démo."""
    _require_mt5()
    info = mt5.account_info()
    if info is None:
        return False
    # trade_mode: 0 = démo, 1 = contest, 2 = réel (selon build MT5)
    return info.trade_mode == 0


def fetch_history(symbol: str = None, timeframe: str = None,
                   years: int = None) -> pd.DataFrame:
    """Récupère l'historique OHLCV pour l'entraînement / le backtest."""
    _require_mt5()

    symbol = symbol or config.SYMBOL
    timeframe = timeframe or config.TIMEFRAME
    years = years or config.HISTORY_YEARS

    tf_const = getattr(mt5, TIMEFRAME_MAP[timeframe])

    if not mt5.symbol_select(symbol, True):
        sys.exit(f"Impossible de sélectionner le symbole {symbol}")

    date_to = datetime.now()
    date_from = date_to - timedelta(days=365 * years)

    rates = mt5.copy_rates_range(symbol, tf_const, date_from, date_to)
    if rates is None or len(rates) == 0:
        sys.exit(f"Aucune donnée renvoyée pour {symbol} {timeframe}. "
                  f"Vérifie que le symbole est bien disponible chez ton broker.")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["time", "open", "high", "low", "close", "volume", "spread"]]
    df = df.set_index("time").sort_index()
    return df


def fetch_latest_bars(symbol: str, timeframe: str, n_bars: int) -> pd.DataFrame:
    """Récupère les n dernières bougies clôturées (pour le live trading)."""
    _require_mt5()
    tf_const = getattr(mt5, TIMEFRAME_MAP[timeframe])
    rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, n_bars)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    df = df[["time", "open", "high", "low", "close", "volume", "spread"]]
    df = df.set_index("time").sort_index()
    return df
