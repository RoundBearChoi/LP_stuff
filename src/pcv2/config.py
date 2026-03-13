import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

if CONFIG_PATH.exists():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        DEFAULT_MAX_MONTHS = int(cfg.get("default_max_months", 12))
        DEFAULT_CSV_FILE = cfg.get("default_csv_file", "top100_hourly_1year_combined.csv")
        print(f"✅ Loaded config.json → default_max_months={DEFAULT_MAX_MONTHS}")
    except Exception as e:
        print(f"⚠️ Config load error: {e}. Falling back to 12 months.")
        DEFAULT_MAX_MONTHS = 12
        DEFAULT_CSV_FILE = "top100_hourly_1year_combined.csv"
else:
    print("ℹ️ No config.json found — using built-in default (12 months)")
    DEFAULT_MAX_MONTHS = 12
    DEFAULT_CSV_FILE = "top100_hourly_1year_combined.csv"
