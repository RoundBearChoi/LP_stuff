import json
from pathlib import Path
from cointegration_engine import CointegrationMethod

CONFIG_PATH = Path(__file__).parent / "config.json"

if CONFIG_PATH.exists():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        
        DEFAULT_COINTEGRATION_CORRELATION_MONTHS = int(cfg.get("cointegration_correlation_months", 12))
        DEFAULT_CSV_FILE = cfg.get("default_csv_file", "top200_hourly_1year_combined.csv")
        
        # robust bool conversion
        raw = cfg.get("get_both_directions_on_cointegration", True)
        if isinstance(raw, str):
            raw = raw.lower() in ("true", "1", "yes", "on")
        DEFAULT_GET_BOTH_DIRECTIONS = bool(raw)

        # Cointegration Calculation Method
        method_raw = str(cfg.get("cointegration_calculation_method", "engle_granger")).lower().strip()
        if method_raw in ("engle_granger", "engle", "eg"):
            DEFAULT_COINTEGRATION_METHOD = CointegrationMethod.ENGLE_GRANGER
        elif method_raw in ("johansen", "j", "johansen_test"):
            DEFAULT_COINTEGRATION_METHOD = CointegrationMethod.JOHANSEN
        else:
            print(f"⚠️ Unknown method '{method_raw}' in config.json. Defaulting to ENGLE_GRANGER.")
            DEFAULT_COINTEGRATION_METHOD = CointegrationMethod.ENGLE_GRANGER

        print(f"✅ Loaded config.json → cointegration_correlation_months={DEFAULT_COINTEGRATION_CORRELATION_MONTHS}m | "
              f"get_both_directions={DEFAULT_GET_BOTH_DIRECTIONS} | "
              f"cointegration_calculation_method={DEFAULT_COINTEGRATION_METHOD.value}")
    except Exception as e:
        print(f"⚠️ Config load error: {e}. Falling back to defaults.")
        DEFAULT_COINTEGRATION_CORRELATION_MONTHS = 12
        DEFAULT_CSV_FILE = "top200_hourly_1year_combined.csv"
        DEFAULT_GET_BOTH_DIRECTIONS = True
        DEFAULT_COINTEGRATION_METHOD = CointegrationMethod.ENGLE_GRANGER
else:
    print("ℹ️ No config.json found — using built-in defaults")
    DEFAULT_COINTEGRATION_CORRELATION_MONTHS = 12
    DEFAULT_CSV_FILE = "top200_hourly_1year_combined.csv"
    DEFAULT_GET_BOTH_DIRECTIONS = True
    DEFAULT_COINTEGRATION_METHOD = CointegrationMethod.ENGLE_GRANGER
