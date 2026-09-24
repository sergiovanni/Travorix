"""
Configuration centrale du bot de trading MT5.
Modifie ces valeurs selon ton compte, ta paire et ton appétit au risque.
"""

# --- Connexion MT5 ---
# Laisser à None pour utiliser le compte déjà connecté dans le terminal MT5.
# Sinon, remplir pour un login programmatique.
MT5_LOGIN = None          # ex: 12345678
MT5_PASSWORD = None       # ex: "motdepasse"
MT5_SERVER = None         # ex: "ICMarkets-Demo"
MT5_PATH = None           # ex: r"C:\Program Files\MetaTrader 5\terminal64.exe" (optionnel)

# --- Marché ---
SYMBOL = "XAUUSD"
TIMEFRAME = "H1"          # M1, M5, M15, M30, H1, H4, D1
HISTORY_YEARS = 5         # profondeur d'historique pour l'entraînement

# --- Features / Labeling ---
LABEL_HORIZON_BARS = 4        # nb de bougies dans le futur pour définir le label
LABEL_THRESHOLD_PIPS = 8      # mouvement mini (en "pips" = PIP_SIZE) pour classer "up"/"down" vs "neutre"
PIP_SIZE = 1.0                 # unité de mesure des mouvements : 0.0001 pour la plupart des paires,
                                # 0.01 pour les paires en JPY, 1.0 (=$1) pour XAUUSD

# --- Modèle ---
MODEL_PATH = "model.joblib"
TRAIN_TEST_SPLIT_DATE = None  # ex: "2024-01-01" ; None = split auto 80/20 chronologique
RANDOM_STATE = 42

# --- Trading / Risque ---
LOT_SIZE = 0.01               # taille fixe de départ, très prudente (0.01 lot = 1 once sur XAUUSD)
MAX_OPEN_POSITIONS = 1
STOP_LOSS_PIPS = 18            # ~1x ATR(14) H1 de l'or au moment du réglage (~17-18$)
TAKE_PROFIT_PIPS = 30          # ratio risque/rendement ~1.7
MAX_DAILY_LOSS_PCT = 2.0      # coupe-circuit : stoppe le bot si -2% du solde dans la journée
MIN_MODEL_CONFIDENCE = 0.60   # ne trade que si le modèle est confiant à >= 60%

# --- Sécurité : compte réel ---
# Le bot refuse de trader sur un compte non-démo tant que ceci n'est pas True.
# Ne passe à True qu'après des semaines concluantes de démo + backtest solide.
ALLOW_REAL_ACCOUNT = False

# --- Exécution live ---
POLL_SECONDS = 30             # fréquence de vérification d'une nouvelle bougie
MAGIC_NUMBER = 20260920       # identifiant unique des ordres passés par ce bot

# --- Scalping intelligent (scalping_bot.py) ---
# Strategie independante de train.py/live_trader.py : direction basee sur une
# tendance court terme (EMA rapide vs EMA lente), pas sur le modele ML.
SCALP_TIMEFRAME = "M1"
SCALP_EMA_FAST = 5
SCALP_EMA_SLOW = 20
SCALP_MIN_TREND_GAP = 0.15          # écart mini EMA rapide/lente (en unité PIP_SIZE) pour valider une tendance
SCALP_LOT_SIZE = 0.01

SCALP_MAX_CONCURRENT = 6            # positions simultanées normales
SCALP_ABSOLUTE_MAX_CONCURRENT = 7   # 7e position : uniquement si signal exceptionnel (cas majeur)
SCALP_LAST_SLOT_GAP_MULTIPLIER = 2.5     # seuil exigé pour utiliser la dernière position normale
SCALP_EXCEPTIONAL_GAP_MULTIPLIER = 4.0   # seuil exigé pour la 7e position exceptionnelle

SCALP_TOP_LEVEL_CLOSE = 5.0         # verrouillage de gain de sécurité (EUR), quel que soit le signal
SCALP_EXCEPTIONAL_TOP_CLOSE = 3.0   # verrouillage plus bas pour la 7e position (plus risquée)

# Trailing rapide : sur ce lot/cette volatilité, les gains flottants observés
# oscillent surtout entre 0 et ~1.5 EUR avant de repartir en négatif. Attendre
# un retournement de tendance confirmé ou le plafond de sécurité (5 EUR) est
# trop lent et laisse échapper des gains réels. Des qu'une position depasse
# SCALP_TRAIL_ACTIVATION_EUR, on suit son pic et on ferme si elle redonne
# SCALP_TRAIL_DRAWBACK_EUR depuis ce pic - sans attendre un retournement.
SCALP_TRAIL_ACTIVATION_EUR = 0.30
SCALP_TRAIL_DRAWBACK_EUR = 0.20

SCALP_MAX_PYRAMID = 2               # nb max d'ajouts de lot sur une position gagnante dont la tendance se renforce
SCALP_PYRAMID_GAP_MULTIPLIER = 1.3  # la tendance doit être 30% plus forte qu'à l'entrée pour ajouter

SCALP_MAX_TOTAL_ENTRIES = 300       # limite de nouvelles entrées par session (large vu la duree de 4h)
SCALP_LOOP_SLEEP_SECONDS = 8
SCALP_SESSION_MAX_MINUTES = 240     # 4h, a la demande
SCALP_EQUITY_FLOOR_PCT = 0.75       # coupe-circuit dur : arrêt total si equity < 75% du solde de départ
