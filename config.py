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
SYMBOL = "EURUSD"
TIMEFRAME = "H1"          # M1, M5, M15, M30, H1, H4, D1
HISTORY_YEARS = 5         # profondeur d'historique pour l'entraînement

# --- Features / Labeling ---
LABEL_HORIZON_BARS = 4        # nb de bougies dans le futur pour définir le label
LABEL_THRESHOLD_PIPS = 8      # mouvement mini (en pips) pour classer "up"/"down" vs "neutre"
PIP_SIZE = 0.0001             # 0.01 pour les paires en JPY

# --- Modèle ---
MODEL_PATH = "model.joblib"
TRAIN_TEST_SPLIT_DATE = None  # ex: "2024-01-01" ; None = split auto 80/20 chronologique
RANDOM_STATE = 42

# --- Trading / Risque ---
LOT_SIZE = 0.01               # taille fixe de départ, très prudente
MAX_OPEN_POSITIONS = 1
STOP_LOSS_PIPS = 20
TAKE_PROFIT_PIPS = 30
MAX_DAILY_LOSS_PCT = 2.0      # coupe-circuit : stoppe le bot si -2% du solde dans la journée
MIN_MODEL_CONFIDENCE = 0.60   # ne trade que si le modèle est confiant à >= 60%

# --- Sécurité : compte réel ---
# Le bot refuse de trader sur un compte non-démo tant que ceci n'est pas True.
# Ne passe à True qu'après des semaines concluantes de démo + backtest solide.
ALLOW_REAL_ACCOUNT = False

# --- Exécution live ---
POLL_SECONDS = 30             # fréquence de vérification d'une nouvelle bougie
MAGIC_NUMBER = 20260920       # identifiant unique des ordres passés par ce bot
