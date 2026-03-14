import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

if CONFIG_PATH.exists():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        
        DEFAULT_COINTEGRATION_CORRELATION_MONTHS = int(cfg.get("cointegration_correlation_months", 12))
        DEFAULT_CHART_MONTHS = int(cfg.get("chart_months", 12))
        DEFAULT_CSV_FILE = cfg.get("default_csv_file", "top200_hourly_1year_combined.csv")
        
        print(f"✅ Loaded config.json → cointegration_correlation_months={DEFAULT_COINTEGRATION_CORRELATION_MONTHS}m | "
              f"chart_months={DEFAULT_CHART_MONTHS}m")
    except Exception as e:
        print(f"⚠️ Config load error: {e}. Falling back to defaults.")
        DEFAULT_COINTEGRATION_CORRELATION_MONTHS = 12
        DEFAULT_CHART_MONTHS = 12
        DEFAULT_CSV_FILE = "top200_hourly_1year_combined.csv"
else:
    print("ℹ️ No config.json found — using built-in defaults (12 months)")
    DEFAULT_COINTEGRATION_CORRELATION_MONTHS = 12
    DEFAULT_CHART_MONTHS = 12
    DEFAULT_CSV_FILE = "top200_hourly_1year_combined.csv"
