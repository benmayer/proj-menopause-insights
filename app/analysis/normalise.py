"""Map any supported cycle CSV to one schema.

Schema: user_id, cycle_start (date), cycle_length (int days), period_length, flow, age.
period_length / flow / age may be missing (NaN). Used by the upload endpoint and the demo scripts.
"""
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
