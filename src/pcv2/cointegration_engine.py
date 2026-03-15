import numpy as np
import pandas as pd
from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import coint
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from dataclasses import dataclass
from enum import Enum


class CointegrationMethod(Enum):
    """All supported cointegration methods — add more here later."""
    ENGLE_GRANGER = "engle_granger"
    JOHANSEN = "johansen"


@dataclass
class CointegrationResults:
    """Unified results object — used by charts, analyzers, and CSV output.
    Everything stays exactly the same no matter which method you choose."""
    method_used: CointegrationMethod
    beta: float
    p_value: float               # pseudo p-value for Johansen (mapped from trace test)
    half_life_days: float
    spread: pd.Series
    zscore: pd.Series
    verdict_console: str
    verdict_chart: str
    box_color: str
    # Extra Johansen info (safe to ignore for Engle-Granger)
    rank: int | None = None
    trace_statistic: float | None = None
    critical_values_95: float | None = None


def compute_cointegration(
    p1: pd.Series,
    p2: pd.Series,
    method: CointegrationMethod = CointegrationMethod.ENGLE_GRANGER
) -> CointegrationResults:
    """Main entry point — ONE function for all methods.
    Default = Engle-Granger (identical to your old code).
    Change to Johansen with: method=CointegrationMethod.JOHANSEN"""
    
    if method == CointegrationMethod.ENGLE_GRANGER:
        return _compute_engle_granger(p1, p2)
    elif method == CointegrationMethod.JOHANSEN:
        return _compute_johansen(p1, p2)
    else:
        raise ValueError(f"Unknown method: {method}")


def _compute_engle_granger(p1: pd.Series, p2: pd.Series) -> CointegrationResults:
    """Original Engle-Granger logic — unchanged."""
    log_p1 = np.log(p1)
    log_p2 = np.log(p2)

    # Beta via OLS
    X = add_constant(log_p2)
    model = OLS(log_p1, X).fit()
    beta = model.params.iloc[1]

    # Spread & Z-score
    spread = log_p1 - beta * log_p2
    zscore = (spread - spread.mean()) / spread.std()

    # Cointegration test
    _, p_value, _ = coint(log_p1, log_p2, autolag='AIC')

    # Half-life
    lagged = spread.shift(1).dropna()
    delta = spread.diff().dropna()
    if len(lagged) > 5:
        ou_model = OLS(delta, add_constant(lagged)).fit()
        kappa = -ou_model.params.iloc[1]
        half_life_hours = np.log(2) / kappa if kappa > 1e-8 else float('inf')
        half_life_days = half_life_hours / 24
    else:
        half_life_days = float('inf')

    # Verdict (exact same strings/colors as before)
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

    return CointegrationResults(
        method_used=CointegrationMethod.ENGLE_GRANGER,
        beta=beta,
        p_value=p_value,
        half_life_days=half_life_days,
        spread=spread,
        zscore=zscore,
        verdict_console=verdict_console,
        verdict_chart=verdict_chart,
        box_color=box_color
    )


def _compute_johansen(p1: pd.Series, p2: pd.Series) -> CointegrationResults:
    """Johansen trace test for pairs (rank 0/1/2).
    Returns same fields as Engle-Granger for perfect drop-in compatibility."""
    log_p1 = np.log(p1)
    log_p2 = np.log(p2)
    data = np.column_stack((log_p1.values, log_p2.values))

    # Johansen test (det_order=0, k_ar_diff=1 is standard for crypto)
    joh = coint_johansen(data, det_order=0, k_ar_diff=1)

    trace_stat = joh.lr1[0]          # trace statistic for r=0
    cv_95 = joh.cvt[0, 1]            # 95% critical value
    rank = sum(joh.lr1 > joh.cvt[:, 1])  # number of cointegrating relations

    # Beta from first eigenvector (normalized to match Engle-Granger style)
    evec = joh.evec[:, 0]
    beta = -evec[1] / evec[0]        # hedge ratio: log_p1 ~ beta * log_p2

    # Spread & Z-score (same formula)
    spread = log_p1 - beta * log_p2
    zscore = (spread - spread.mean()) / spread.std()

    # Map trace test → pseudo p-value for verdict compatibility
    if trace_stat > joh.cvt[0, 2]:      # 99%
        p_value = 0.005
    elif trace_stat > joh.cvt[0, 1]:    # 95%
        p_value = 0.025
    elif trace_stat > joh.cvt[0, 0]:    # 90%
        p_value = 0.075
    else:
        p_value = 0.20

    # Half-life (same Ornstein-Uhlenbeck logic)
    lagged = spread.shift(1).dropna()
    delta = spread.diff().dropna()
    if len(lagged) > 5:
        ou_model = OLS(delta, add_constant(lagged)).fit()
        kappa = -ou_model.params.iloc[1]
        half_life_hours = np.log(2) / kappa if kappa > 1e-8 else float('inf')
        half_life_days = half_life_hours / 24
    else:
        half_life_days = float('inf')

    # Verdict (same style, but mentions method)
    if rank >= 1 and p_value < 0.01:
        verdict_console = "✅ STRONG COINTEGRATION (Johansen rank≥1, p<0.01)"
        verdict_chart = "STRONG COINTEGRATION (Johansen rank≥1)"
        box_color = 'lime'
    elif rank >= 1 and p_value < 0.05:
        verdict_console = "✅ MODERATE COINTEGRATION (Johansen rank≥1, p<0.05)"
        verdict_chart = "MODERATE COINTEGRATION (Johansen rank≥1)"
        box_color = 'lightgreen'
    elif rank >= 1:
        verdict_console = "⚠️ WEAK / MARGINAL (Johansen rank≥1)"
        verdict_chart = "WEAK / MARGINAL (Johansen rank≥1)"
        box_color = 'yellow'
    else:
        verdict_console = "❌ NO COINTEGRATION (Johansen rank=0)"
        verdict_chart = "NO COINTEGRATION (Johansen rank=0)"
        box_color = 'salmon'

    return CointegrationResults(
        method_used=CointegrationMethod.JOHANSEN,
        beta=beta,
        p_value=p_value,
        half_life_days=half_life_days,
        spread=spread,
        zscore=zscore,
        verdict_console=verdict_console,
        verdict_chart=verdict_chart,
        box_color=box_color,
        rank=rank,
        trace_statistic=trace_stat,
        critical_values_95=cv_95
    )
