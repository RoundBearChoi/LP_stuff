import numpy as np
import pandas as pd
from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import coint
from dataclasses import dataclass


@dataclass
class EngleGrangerResults:
    """All results from the Engle-Granger method in one clean object.
    This is now the SINGLE source of truth for cointegration calculations."""
    beta: float
    p_value: float
    half_life_days: float
    spread: pd.Series
    zscore: pd.Series
    verdict_console: str
    verdict_chart: str
    box_color: str


def compute_engle_granger_cointegration(p1: pd.Series, p2: pd.Series) -> EngleGrangerResults:
    """Core Engle-Granger cointegration + half-life.
    Used by get_cointegration.py, get_all_cointegration_and_correlation.py,
    and any future scripts."""
    log_p1 = np.log(p1)
    log_p2 = np.log(p2)

    # === Step 1: Beta (hedge ratio) via OLS ===
    X = add_constant(log_p2)
    model = OLS(log_p1, X).fit()
    beta = model.params.iloc[1]

    # === Step 2: Spread & Z-score ===
    spread = log_p1 - beta * log_p2
    zscore = (spread - spread.mean()) / spread.std()

    # === Step 3: Engle-Granger cointegration test ===
    _, p_value, _ = coint(log_p1, log_p2, autolag='AIC')

    # === Step 4: Half-life (Ornstein-Uhlenbeck) ===
    lagged = spread.shift(1).dropna()
    delta = spread.diff().dropna()
    if len(lagged) > 5:
        ou_model = OLS(delta, add_constant(lagged)).fit()
        kappa = -ou_model.params.iloc[1]
        half_life_hours = np.log(2) / kappa if kappa > 1e-8 else float('inf')
        half_life_days = half_life_hours / 24
    else:
        half_life_days = float('inf')

    # === Step 5: Verdict (exact same strings & colors as original) ===
    if p_value < 0.01:
        verdict_console = "✅ STRONG COINTEGRATION (p < 0.01)"
        verdict_chart = "STRONG COINTEGRATION (p < 0.01)"
        box_color = 'lime'
    elif p_value < 0.05:
        verdict_console = "✅ MODERATE COINTEGRATION (p < 0.05)"
        verdict_chart = "MODERATE COINTEGRATION (p < 0.05)"
        box_color = 'lightgreen'
    elif p_value < 0.10:
        verdict_console = "⚠️ WEAK / MARGINAL (p < 0.10)"
        verdict_chart = "WEAK / MARGINAL (p < 0.10)"
        box_color = 'yellow'
    else:
        verdict_console = "❌ NO COINTEGRATION (p ≥ 0.10)"
        verdict_chart = "NO COINTEGRATION (p ≥ 0.10)"
        box_color = 'salmon'

    return EngleGrangerResults(
        beta=beta,
        p_value=p_value,
        half_life_days=half_life_days,
        spread=spread,
        zscore=zscore,
        verdict_console=verdict_console,
        verdict_chart=verdict_chart,
        box_color=box_color
    )
