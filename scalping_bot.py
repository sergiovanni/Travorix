"""
Bot de scalping independant du pipeline ML (train.py / live_trader.py).

Direction basee sur une tendance court terme (EMA rapide vs EMA lente sur
SCALP_TIMEFRAME), pas sur le modele entraine. Pense pour du test manuel
supervise sur compte demo, pas pour tourner sans surveillance.

Regles :
- Fermeture sur retournement de tendance, uniquement si la position est en
  gain (jamais de fermeture en perte - le stop-loss de config.py reste le
  seul filet contre une perte qui degenere).
- Verrouillage de gain de securite a SCALP_TOP_LEVEL_CLOSE, pour ne pas
  laisser un gros gain flottant repartir a zero sur un retournement brutal.
- Pyramidage : ajout de lot sur une position deja gagnante dont la tendance
  se renforce. Jamais d'ajout sur une position perdante (pas de moyennage a
  la baisse).
- Coupe-circuit dur sur l'equity du compte : arret et fermeture totale si
  l'equity descend sous SCALP_EQUITY_FLOOR_PCT du solde de depart.

Usage :
    python scalping_bot.py
"""
import time

import MetaTrader5 as mt5

import config
import data_loader
from live_trader import _supported_filling_mode, _check_account_safety


def get_trend_signal():
    """Retourne (direction, ecart) : direction = 1 (hausse), -1 (baisse) ou
    None si l'ecart EMA rapide/lente est sous le seuil de tendance."""
    bars = data_loader.fetch_latest_bars(config.SYMBOL, config.SCALP_TIMEFRAME,
                                          n_bars=config.SCALP_EMA_SLOW + 10)
    if bars.empty or len(bars) < config.SCALP_EMA_SLOW:
        return None, 0.0
    closes = bars["close"]
    ema_fast = closes.ewm(span=config.SCALP_EMA_FAST, adjust=False).mean().iloc[-1]
    ema_slow = closes.ewm(span=config.SCALP_EMA_SLOW, adjust=False).mean().iloc[-1]
    gap = ema_fast - ema_slow
    if gap >= config.SCALP_MIN_TREND_GAP:
        return 1, gap
    if gap <= -config.SCALP_MIN_TREND_GAP:
        return -1, gap
    return None, gap


def open_position(direction: int, comment: str):
    tick = mt5.symbol_info_tick(config.SYMBOL)
    price = tick.ask if direction == 1 else tick.bid
    sl_price = price - direction * config.STOP_LOSS_PIPS * config.PIP_SIZE
    tp_price = price + direction * config.TAKE_PROFIT_PIPS * config.PIP_SIZE
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": config.SYMBOL,
        "volume": config.SCALP_LOT_SIZE,
        "type": mt5.ORDER_TYPE_BUY if direction == 1 else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 10,
        "magic": config.MAGIC_NUMBER,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _supported_filling_mode(config.SYMBOL),
    }
    return mt5.order_send(request)


def close_position(pos):
    tick = mt5.symbol_info_tick(config.SYMBOL)
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": config.SYMBOL,
        "volume": pos.volume,
        "type": close_type,
        "position": pos.ticket,
        "price": price,
        "deviation": 10,
        "magic": config.MAGIC_NUMBER,
        "comment": "scalp-close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _supported_filling_mode(config.SYMBOL),
    }
    return mt5.order_send(request)


class ScalpingSession:
    def __init__(self):
        self.position_meta = {}       # ticket -> {"root", "direction", "exceptional"}
        self.root_entry_gap = {}      # root_ticket -> écart EMA à l'ouverture
        self.root_pyramid_count = {}  # root_ticket -> nb d'ajouts déjà faits
        self.closed_results = []
        self.total_entries = 0
        self.starting_balance = mt5.account_info().balance
        self.equity_floor = self.starting_balance * config.SCALP_EQUITY_FLOOR_PCT

    def adopt_existing_positions(self):
        existing = mt5.positions_get(symbol=config.SYMBOL)
        _, gap0 = get_trend_signal()
        for pos in existing:
            direction = 1 if pos.type == mt5.ORDER_TYPE_BUY else -1
            self.position_meta[pos.ticket] = {"root": pos.ticket, "direction": direction, "exceptional": False}
            self.root_entry_gap[pos.ticket] = gap0 or (config.SCALP_MIN_TREND_GAP * direction)
            self.root_pyramid_count[pos.ticket] = 0
        print(f"[reprise] {len(existing)} position(s) existante(s) adoptée(s)", flush=True)

    def check_circuit_breaker(self) -> bool:
        equity = mt5.account_info().equity
        if equity >= self.equity_floor:
            return False
        print(f"\n[COUPE-CIRCUIT] equity={equity:.2f} < plancher {self.equity_floor:.2f}. "
              f"Fermeture totale.", flush=True)
        for pos in mt5.positions_get(symbol=config.SYMBOL):
            res = close_position(pos)
            print(f"[coupe-circuit] fermeture forcée ticket={pos.ticket} "
                  f"profit={pos.profit:.2f} (retcode={res.retcode})", flush=True)
        return True

    def manage_open_positions(self, current_direction):
        still_open_roots = set()
        for pos in mt5.positions_get(symbol=config.SYMBOL):
            meta = self.position_meta.setdefault(
                pos.ticket,
                {"root": pos.ticket, "direction": 1 if pos.type == mt5.ORDER_TYPE_BUY else -1, "exceptional": False},
            )
            self.root_entry_gap.setdefault(meta["root"], 0.0)
            self.root_pyramid_count.setdefault(meta["root"], 0)

            top_close = config.SCALP_EXCEPTIONAL_TOP_CLOSE if meta["exceptional"] else config.SCALP_TOP_LEVEL_CLOSE
            if pos.profit >= top_close:
                res = close_position(pos)
                print(f"[ticket {pos.ticket}] FERMÉE FILET SÉCURITÉ à +{pos.profit:.2f} EUR "
                      f"(retcode={res.retcode})", flush=True)
                self.closed_results.append(pos.profit)
                self.position_meta.pop(pos.ticket, None)
                continue

            reversed_signal = current_direction is not None and current_direction != meta["direction"]
            if reversed_signal and pos.profit > 0:
                res = close_position(pos)
                print(f"[ticket {pos.ticket}] FERMÉE SUR RETOURNEMENT à +{pos.profit:.2f} EUR "
                      f"(retcode={res.retcode})", flush=True)
                self.closed_results.append(pos.profit)
                self.position_meta.pop(pos.ticket, None)
                continue

            still_open_roots.add(meta["root"])
            print(f"[ticket {pos.ticket}] {'ACHAT' if meta['direction'] == 1 else 'VENTE'} "
                  f"profit={pos.profit:+.2f} EUR", flush=True)
        return still_open_roots

    def try_pyramid(self, current_direction, current_gap, still_open_roots):
        open_positions = mt5.positions_get(symbol=config.SYMBOL)
        if current_direction is None or len(open_positions) >= config.SCALP_MAX_CONCURRENT:
            return

        for root in still_open_roots:
            if self.root_pyramid_count.get(root, 0) >= config.SCALP_MAX_PYRAMID:
                continue
            members = [p for p in open_positions if self.position_meta.get(p.ticket, {}).get("root") == root]
            if not members or self.position_meta[members[0].ticket]["direction"] != current_direction:
                continue

            entry_gap = self.root_entry_gap.get(root, current_gap)
            strengthening = abs(current_gap) >= abs(entry_gap) * config.SCALP_PYRAMID_GAP_MULTIPLIER
            if max(p.profit for p in members) <= 0 or not strengthening:
                continue

            res = open_position(current_direction, comment=f"pyramid-{root}")
            if res.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"[pyramidage] échec retcode={res.retcode} {res.comment}", flush=True)
                continue
            new_pos = mt5.positions_get(symbol=config.SYMBOL)[-1]
            self.position_meta[new_pos.ticket] = {"root": root, "direction": current_direction, "exceptional": False}
            self.root_pyramid_count[root] += 1
            self.total_entries += 1
            print(f"[pyramidage] ajout {config.SCALP_LOT_SIZE} lot sur root={root} ticket={new_pos.ticket} "
                  f"(tendance renforcée: {current_gap:+.3f} vs entrée {entry_gap:+.3f}) "
                  f"[{self.root_pyramid_count[root]}/{config.SCALP_MAX_PYRAMID}]", flush=True)
            open_positions = mt5.positions_get(symbol=config.SYMBOL)
            if len(open_positions) >= config.SCALP_MAX_CONCURRENT:
                return

    def try_new_entry(self, current_direction, current_gap):
        open_positions = mt5.positions_get(symbol=config.SYMBOL)
        n_open = len(open_positions)

        if current_direction is None:
            print(f"[signal] pas de tendance claire (écart={current_gap:+.3f})", flush=True)
            return
        if self.total_entries >= config.SCALP_MAX_TOTAL_ENTRIES:
            return

        if n_open < config.SCALP_MAX_CONCURRENT:
            is_last_slot = n_open == config.SCALP_MAX_CONCURRENT - 1
            required_gap = (config.SCALP_MIN_TREND_GAP * config.SCALP_LAST_SLOT_GAP_MULTIPLIER
                             if is_last_slot else config.SCALP_MIN_TREND_GAP)
            if abs(current_gap) < required_gap:
                if is_last_slot:
                    print(f"[signal] dernière position dispo, signal trop faible "
                          f"(écart={current_gap:+.3f}, requis={required_gap:.3f})", flush=True)
                return
            self._open_and_track(current_direction, current_gap, exceptional=False)
            return

        # Slots normaux pleins : n'ouvrir la 7e que sur signal exceptionnel
        if n_open < config.SCALP_ABSOLUTE_MAX_CONCURRENT:
            required_gap = config.SCALP_MIN_TREND_GAP * config.SCALP_EXCEPTIONAL_GAP_MULTIPLIER
            if abs(current_gap) >= required_gap:
                self._open_and_track(current_direction, current_gap, exceptional=True)

    def _open_and_track(self, direction, gap, exceptional: bool):
        comment = "scalp-entry-exceptionnelle" if exceptional else "scalp-entry"
        res = open_position(direction, comment=comment)
        if res.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[entrée] échec retcode={res.retcode} {res.comment}", flush=True)
            return
        new_pos = mt5.positions_get(symbol=config.SYMBOL)[-1]
        self.position_meta[new_pos.ticket] = {"root": new_pos.ticket, "direction": direction, "exceptional": exceptional}
        self.root_entry_gap[new_pos.ticket] = gap
        self.root_pyramid_count[new_pos.ticket] = 0
        self.total_entries += 1
        label = "7e POSITION EXCEPTIONNELLE" if exceptional else "nouvelle position"
        print(f"[{label}] {'ACHAT' if direction == 1 else 'VENTE'} ticket={new_pos.ticket} "
              f"@ {new_pos.price_open} (écart={gap:+.3f}) [{self.total_entries}/{config.SCALP_MAX_TOTAL_ENTRIES}]",
              flush=True)

    def summarize(self):
        print("\n=== Résumé session scalping ===", flush=True)
        print(f"Positions fermées en gain: {len(self.closed_results)}", flush=True)
        print(f"Gain total réalisé: {sum(self.closed_results):.2f} EUR", flush=True)
        remaining = mt5.positions_get(symbol=config.SYMBOL)
        print(f"Positions encore ouvertes: {len(remaining)}", flush=True)
        info = mt5.account_info()
        print(f"Solde: {info.balance} {info.currency} | Equity: {info.equity} {info.currency}", flush=True)


def run():
    data_loader.connect()
    _check_account_safety()
    session = ScalpingSession()
    session.adopt_existing_positions()

    deadline = time.time() + config.SCALP_SESSION_MAX_MINUTES * 60
    try:
        while time.time() < deadline:
            if session.check_circuit_breaker():
                break
            direction, gap = get_trend_signal()
            still_open_roots = session.manage_open_positions(direction)
            session.try_pyramid(direction, gap, still_open_roots)
            session.try_new_entry(direction, gap)
            time.sleep(config.SCALP_LOOP_SLEEP_SECONDS)
    except KeyboardInterrupt:
        print("\n[scalping] arrêt demandé par l'utilisateur.", flush=True)
    finally:
        session.summarize()
        data_loader.disconnect()


if __name__ == "__main__":
    run()
