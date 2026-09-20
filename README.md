# MT5 ML Bot — Bot de trading Forex avec modèle entraîné

Pipeline complet : données historiques MT5 → feature engineering →
modèle ML (RandomForest, 3 classes : hausse / baisse / neutre) →
backtest hors échantillon → exécution automatique sur compte démo.

## ⚠️ Prérequis importants

Le package `MetaTrader5` ne fonctionne **qu'avec un terminal MetaTrader 5
réellement installé et connecté à un compte**. Il ne fonctionne nativement
que sous **Windows** (sous Linux/Mac, il faut passer par Wine, ce qui est
plus fragile). Ce projet ne peut donc pas tourner tel quel dans un
environnement Linux sans terminal MT5 — tu devras l'exécuter sur ta propre
machine Windows.

Ce dont tu as besoin :
1. **Un terminal MetaTrader 5** installé (téléchargeable gratuitement chez
   n'importe quel broker : IC Markets, Pepperstone, XTB, Admirals…).
2. **Un compte démo** ouvert chez ce broker (gratuit, argent fictif).
   Connecte-toi une première fois manuellement dans le terminal MT5.
3. **Python 3.10+** installé sur la même machine.
4. Dans le terminal MT5 : `Outils > Options > Expert Advisors` → cocher
   "Autoriser le trading algorithmique".

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Ouvre `config.py` et renseigne au minimum :
- `SYMBOL` (ex: `"EURUSD"`)
- `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` — **uniquement si tu veux te
  connecter automatiquement à un compte différent de celui déjà ouvert
  dans le terminal**. Sinon laisse `None`, le bot utilisera la session
  déjà active dans MT5.

Les autres paramètres (taille de lot, stop-loss, take-profit, seuil de
confiance du modèle) sont commentés dans le fichier.

## Étape 1 — Entraîner et évaluer le modèle

```bash
python train.py
```

Ce script :
1. Se connecte à MT5 et télécharge plusieurs années d'historique.
2. Construit les features (RSI, MACD, moyennes mobiles, volatilité…).
3. Entraîne un RandomForest sur 80% des données les plus anciennes.
4. Évalue sur les 20% les plus récentes (jamais vues à l'entraînement).
5. Lance un backtest simplifié et affiche un résumé (taux de réussite,
   profit factor, drawdown).
6. Sauvegarde le modèle dans `model.joblib`.

**Ne passe pas à l'étape 2 si le backtest est mauvais** (profit factor
< 1.2, très peu de trades, ou drawdown énorme). Ajuste les features, le
seuil de label, ou le seuil de confiance, et relance.

## Étape 2 — Tourner en compte démo

```bash
python live_trader.py
```

Le bot :
- Vérifie automatiquement que le compte connecté est bien un compte
  **démo**. S'il détecte un compte réel, il refuse de trader tant que
  `config.ALLOW_REAL_ACCOUNT` n'est pas mis à `True` dans `config.py`.
- Surveille les nouvelles bougies, calcule les features, interroge le
  modèle, et ne passe un ordre que si la confiance dépasse
  `MIN_MODEL_CONFIDENCE`.
- S'arrête automatiquement (coupe-circuit) si la perte du jour dépasse
  `MAX_DAILY_LOSS_PCT`.

**Laisse-le tourner en démo pendant plusieurs semaines minimum** avant
d'envisager quoi que ce soit avec de l'argent réel. Compare les résultats
réels obtenus en démo à ceux du backtest — s'ils divergent fortement,
il y a un problème (souvent : spread/slippage sous-estimés, ou
overfitting du modèle).

## Étape 3 — Compte réel (à ne faire qu'en connaissance de cause)

1. Change `MT5_LOGIN` / `MT5_SERVER` pour pointer vers ton compte réel.
2. Passe `ALLOW_REAL_ACCOUNT = True` dans `config.py`.
3. Relance `python live_trader.py`.

Je ne suis pas conseiller financier — cette étape engage de l'argent réel
et le résultat du backtest/démo ne garantit rien sur le futur. Commence
avec une taille de lot minimale (`LOT_SIZE = 0.01`) et un capital que tu
es prêt à perdre entièrement.

## Structure du projet

```
config.py        # tous les paramètres réglables
data_loader.py    # connexion MT5 + récupération des données
features.py       # feature engineering + labels
model.py          # entraînement / évaluation / sauvegarde du modèle
backtest.py        # simulation vectorisée hors échantillon
train.py           # pipeline complet d'entraînement (à lancer en premier)
live_trader.py     # boucle d'exécution live avec garde-fous de sécurité
```

## Limites connues à garder en tête

- Le backtest est une approximation (exécution parfaite au close,
  spread simplifié) — les résultats réels seront toujours moins bons.
- Un modèle qui "marche" sur 5 ans d'historique peut très bien cesser de
  marcher si le régime de marché change (le marché n'est pas stationnaire).
- Ce système ne fait aucun position sizing dynamique ni money management
  avancé (Kelly, volatility targeting…) — tout est en lot fixe pour rester
  simple et prudent au départ.
- Aucune gestion multi-devises / multi-actifs pour l'instant : un seul
  symbole à la fois.
