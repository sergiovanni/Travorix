"""
Boucle d'exécution live : lit la dernière bougie, calcule les features,
interroge le modèle, et passe un ordre si les conditions sont réunies.

SÉCURITÉS INTÉGRÉES :
1. Refuse de trader sur un compte réel tant que config.ALLOW_REAL_ACCOUNT
   n'est pas explicitement mis à True.
2. Coupe-circuit journalier : arrête le bot si la perte du jour dépasse
   MAX_DAILY_LOSS_PCT.
3. Ne prend qu'une position à la fois (MAX_OPEN_POSITIONS).
4. N'agit que sur une confiance modèle >= MIN_MODEL_CONFIDENCE.

Usage :
    python live_trader.py            # tourne indéfiniment (Ctrl+C pour arrêter)
"""
import sys
import time
from datetime import datetime, timedelta

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

import config
import data_loader
import model as model_module
from features import build_features, FEATURE_COLUMNS


def _check_account_safety():
    if not data_loader.is_demo_account() and not config.ALLOW_REAL_ACCOUNT:
        sys.exit(
            "\n[SÉCURITÉ] Ce compte n'est PAS un compte démo, et "
            "config.ALLOW_REAL_ACCOUNT est à False.\n"
            "Le bot refuse de trader de l'argent réel tant que tu n'as pas "
            "validé la stratégie en démo sur une période significative "
            "et changé ce paramètre en toute connaissance de cause."
        )


def _get_daily_loss_pct() -> float:
    info = mt5.account_info()
    if info is None:
        return 0.0
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    deals = mt5.history_deals_get(today_start, datetime.now())
    if not deals:
        return 0.0
    pnl_today = sum(d.profit for d in deals)
    if pnl_today >= 0 or info.balance == 0:
        return 0.0
    return abs(pnl_today) / info.balance * 100


def _count_open_positions(symbol: str) -> int:
    positions = mt5.positions_get(symbol=symbol)
    return len(positions) if positions else 0


def _place_order(symbol: str, direction: int, confidence: float):
    tick = mt5.symbol_info_tick(symbol)
    price = tick.ask if direction == 1 else tick.bid
    point = mt5.symbol_info(symbol).point
    sl_points = config.STOP_LOSS_PIPS * config.PIP_SIZE / point
    tp_points = config.TAKE_PROFIT_PIPS * config.PIP_SIZE / point

    sl_price = price - direction * sl_points * point
    tp_price = price + direction * tp_points * point

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": config.LOT_SIZE,
        "type": mt5.ORDER_TYPE_BUY if direction == 1 else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 10,
        "magic": config.MAGIC_NUMBER,
        "comment": f"ml-bot conf={confidence:.2f}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[ordre] ÉCHEC retcode={result.retcode} comment={result.comment}")
    else:
        print(f"[ordre] {'ACHAT' if direction == 1 else 'VENTE'} "
              f"{config.LOT_SIZE} lot {symbol} @ {price} "
              f"(confiance={confidence:.2%})")
    return result


def run_live():
    data_loader.connect()
    _check_account_safety()

    clf = model_module.load_model()
    print(f"[live] Modèle chargé, démarrage de la boucle sur {config.SYMBOL} "
          f"{config.TIMEFRAME} (Ctrl+C pour arrêter)\n")

    last_bar_time = None

    try:
        while True:
            daily_loss = _get_daily_loss_pct()
            if daily_loss >= config.MAX_DAILY_LOSS_PCT:
                print(f"[COUPE-CIRCUIT] Perte du jour ({daily_loss:.2f}%) "
                      f">= limite ({config.MAX_DAILY_LOSS_PCT}%). Arrêt du bot.")
                break

            bars = data_loader.fetch_latest_bars(
                config.SYMBOL, config.TIMEFRAME, n_bars=200
            )
            if bars.empty:
                time.sleep(config.POLL_SECONDS)
                continue

            current_bar_time = bars.index[-1]
            if current_bar_time == last_bar_time:
                time.sleep(config.POLL_SECONDS)
                continue
            last_bar_time = current_bar_time

            feats = build_features(bars).dropna(subset=FEATURE_COLUMNS)
            if feats.empty:
                time.sleep(config.POLL_SECONDS)
                continue

            X_last = feats[FEATURE_COLUMNS].iloc[[-1]]
            pred_class, confidence = model_module.predict_with_confidence(clf, X_last)

            print(f"[{current_bar_time}] prédiction={pred_class} "
                  f"confiance={confidence:.2%}")

            if pred_class == 0 or confidence < config.MIN_MODEL_CONFIDENCE:
                time.sleep(config.POLL_SECONDS)
                continue

            if _count_open_positions(config.SYMBOL) >= config.MAX_OPEN_POSITIONS:
                print("[live] Position déjà ouverte, on attend.")
                time.sleep(config.POLL_SECONDS)
                continue

            _place_order(config.SYMBOL, int(pred_class), confidence)
            time.sleep(config.POLL_SECONDS)

    except KeyboardInterrupt:
        print("\n[live] Arrêt demandé par l'utilisateur.")
    finally:
        data_loader.disconnect()


if __name__ == "__main__":
    run_live()
