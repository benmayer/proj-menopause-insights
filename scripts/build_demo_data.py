"""Normalise the two Kaggle sets into demo CSVs under samples/ (demo data only)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pandas as pd
from app.analysis.normalise import normalise

raw, out = ROOT / "data" / "raw", ROOT / "samples"
out.mkdir(exist_ok=True)

b = normalise(pd.read_csv(raw / "menstrual-health-dataset" / "Period_Log.csv"),
              profile=pd.read_csv(raw / "menstrual-health-dataset" / "User_Profile.csv"))
b.to_csv(out / "demo_kaggle_menstrual_health.csv", index=False)

a = normalise(pd.read_csv(raw / "menstrual-cycle-data-with-factors-dataset" / "menstrual_cycle_dataset_with_factors.csv"))
a.to_csv(out / "demo_kaggle_cycle_factors.csv", index=False)

for name, df in [("B menstrual-health", b), ("A cycle-factors", a)]:
    print(name, df.shape, "users:", df.user_id.nunique(), "nulls:", df.isna().sum().to_dict())
