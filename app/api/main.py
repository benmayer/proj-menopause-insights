"""FastAPI data service. Returns computed stats; the LLM never sees raw rows.

Run: uvicorn app.api.main:app --reload   (docs at /docs)
"""
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile

from app.analysis.normalise import NormaliseError, load_upload
from app.analysis.stats import compute_stats
from app.api.models import CycleRecord, CyclesResponse, StatsResponse, UploadResponse
from app.api.store import DatasetNotFound, store

SAMPLES = Path(__file__).resolve().parent.parent.parent / "samples"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Bundled demo files (synthetic / Kaggle) are always available as dataset ids "demo_<name>".
    for f in sorted(SAMPLES.glob("demo_*.csv")):
        store.put(load_upload(f.read_bytes(), f.name), dataset_id=f.stem, permanent=True)
    yield


app = FastAPI(title="Menopause Insights data API", lifespan=lifespan)


def _user_frame(dataset_id: str, user_id: str | None) -> tuple[str, pd.DataFrame]:
    try:
        df = store.get(dataset_id)
    except DatasetNotFound:
        raise HTTPException(404, f"Unknown or expired dataset '{dataset_id}'. Upload the file again.")
    users = df["user_id"].unique()
    if user_id is None:
        if len(users) != 1:
            raise HTTPException(422, "This dataset has several users; pass user_id.")
        user_id = users[0]
    sub = df[df["user_id"] == user_id]
    if sub.empty:
        raise HTTPException(404, f"No user '{user_id}' in this dataset.")
    return user_id, sub


def _int(v):
    return None if pd.isna(v) else int(v)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/demos")
def demos():
    return {"datasets": store.ids("demo_")}


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)):
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (max 5 MB).")
    try:
        df = load_upload(content, file.filename or "")
    except NormaliseError as e:
        raise HTTPException(422, str(e))
    dataset_id = store.put(df)
    users = df["user_id"].unique().tolist()
    return UploadResponse(dataset_id=dataset_id, n_rows=len(df), n_users=len(users), users=users[:50],
                          has_period_length=bool(df["period_length"].notna().any()),
                          has_flow=bool(df["flow"].notna().any()), has_age=bool(df["age"].notna().any()))


@app.get("/users")
def users(dataset_id: str):
    try:
        df = store.get(dataset_id)
    except DatasetNotFound:
        raise HTTPException(404, "Unknown or expired dataset.")
    return {"dataset_id": dataset_id, "users": df["user_id"].unique().tolist()[:200]}


@app.get("/cycles", response_model=CyclesResponse)
def cycles(dataset_id: str, user_id: str | None = None):
    user_id, sub = _user_frame(dataset_id, user_id)
    recs = [CycleRecord(cycle_start=str(r.cycle_start.date()), cycle_length=_int(r.cycle_length),
                        period_length=_int(r.period_length), flow=None if pd.isna(r.flow) else str(r.flow))
            for r in sub.sort_values("cycle_start").itertuples()]
    return CyclesResponse(dataset_id=dataset_id, user_id=user_id, cycles=recs)


@app.get("/stats", response_model=StatsResponse)
def stats(dataset_id: str, user_id: str | None = None):
    user_id, sub = _user_frame(dataset_id, user_id)
    return StatsResponse(dataset_id=dataset_id, user_id=user_id, **compute_stats(sub))
