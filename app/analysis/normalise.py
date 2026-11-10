"""Map any supported cycle CSV to one schema.

Schema: user_id, cycle_start (date), cycle_length (int days), period_length, flow, age.
period_length / flow / age may be missing (NaN). Used by the upload endpoint and the demo scripts.
"""
import io
import json

import pandas as pd

COLUMNS = ["user_id", "cycle_start", "cycle_length", "period_length", "flow", "age"]

# Accepted header names (lower-cased, spaces/underscores ignored) per schema column.
ALIASES = {
    "user_id": ["userid", "user", "id"],
    "cycle_start": ["cyclestart", "cyclestartdate", "startdate", "start", "date", "periodstart"],
    "cycle_length": ["cyclelength", "cyclelengthdays", "length"],
    "period_length": ["periodlength", "perioddays", "perioddurationdays"],
    "flow": ["flow", "flowlevel", "flowintensity"],
    "age": ["age"],
}


class NormaliseError(ValueError):
    """Raised with a user-readable message when a CSV cannot be mapped."""


def _key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _rename(df: pd.DataFrame) -> pd.DataFrame:
    lookup = {_key(c): c for c in df.columns}
    mapping = {}
    for target, names in ALIASES.items():
        for n in [_key(target)] + names:
            if n in lookup:
                mapping[lookup[n]] = target
                break
    return df.rename(columns=mapping)[list(mapping.values())]


def normalise(df: pd.DataFrame, profile: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return the normalised frame. `profile` optionally supplies age per user_id."""
    df = _rename(df)
    if "cycle_start" not in df:
        raise NormaliseError("Need a cycle start date column (e.g. 'cycle_start', 'start_date').")
    if "user_id" not in df:
        df["user_id"] = "me"  # single-person export (e.g. Clue)
    df["user_id"] = df["user_id"].astype(str)
    df["cycle_start"] = pd.to_datetime(df["cycle_start"], errors="coerce").dt.normalize()
    if df["cycle_start"].isna().any():
        raise NormaliseError("Some cycle start dates could not be read as dates.")
    df = df.sort_values(["user_id", "cycle_start"]).reset_index(drop=True)

    if "cycle_length" not in df:
        # Derive from the gap to the next start; the last cycle per user has no length.
        gap = df.groupby("user_id")["cycle_start"].shift(-1) - df["cycle_start"]
        df["cycle_length"] = gap.dt.days
    df["cycle_length"] = pd.to_numeric(df["cycle_length"], errors="coerce")

    if profile is not None and "age" not in df:
        p = _rename(profile).drop_duplicates("user_id")
        p["user_id"] = p["user_id"].astype(str)
        df = df.merge(p[["user_id", "age"]], on="user_id", how="left")

    for col in COLUMNS:
        if col not in df:
            df[col] = pd.NA
    df["cycle_length"] = df["cycle_length"].astype("Int64")
    return df[COLUMNS]


# --- JSON / Clue ------------------------------------------------------------
NEW_CYCLE_GAP_DAYS = 7  # bleeding days further apart than this belong to different cycles


def _is_clue(records: list) -> bool:
    return bool(records) and isinstance(records[0], dict) and {"type", "date", "value"} <= set(records[0])


def from_clue_measurements(records: list) -> pd.DataFrame:
    """Clue `measurements.json`: one row per logged item. Keep `period` days and group
    them into cycles: a gap of more than NEW_CYCLE_GAP_DAYS starts a new cycle."""
    days = []
    for r in records:
        if r.get("type") == "period":
            v = r.get("value")
            days.append({"day": r["date"], "flow": (v.get("option") if isinstance(v, dict) else None)})
    if not days:
        raise NormaliseError("No 'period' entries found in this Clue export.")
    d = pd.DataFrame(days)
    d["day"] = pd.to_datetime(d["day"], errors="coerce")
    d = d.dropna(subset=["day"]).sort_values("day").drop_duplicates("day").reset_index(drop=True)
    d["cycle"] = (d["day"].diff().dt.days.fillna(0) > NEW_CYCLE_GAP_DAYS).cumsum()
    g = d.groupby("cycle")
    out = pd.DataFrame({
        "cycle_start": g["day"].min(),
        "period_length": g["day"].agg(lambda x: (x.max() - x.min()).days + 1),
        "flow": g["flow"].agg(lambda x: x.mode().iloc[0].capitalize() if x.notna().any() else pd.NA),
    }).reset_index(drop=True)
    return normalise(out)  # user_id defaults to 'me'; cycle_length derived from the gaps


def load_upload(content: bytes, filename: str = "") -> pd.DataFrame:
    """Parse an uploaded CSV or JSON file and return the normalised frame."""
    try:
        if filename.lower().endswith(".json") or content.lstrip()[:1] in (b"[", b"{"):
            data = json.loads(content)
            if isinstance(data, dict):  # {"cycles": [...]} style wrapper
                data = next((v for v in data.values() if isinstance(v, list)), None)
            if not isinstance(data, list) or not data:
                raise NormaliseError("JSON must be a list of records.")
            return from_clue_measurements(data) if _is_clue(data) else normalise(pd.DataFrame(data))
        return normalise(pd.read_csv(io.BytesIO(content)))
    except (json.JSONDecodeError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as e:
        raise NormaliseError(f"Could not read the file: {e}") from e
