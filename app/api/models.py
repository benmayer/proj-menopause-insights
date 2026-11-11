from pydantic import BaseModel


class UploadResponse(BaseModel):
    dataset_id: str
    n_rows: int
    n_users: int
    users: list[str]  # first 50 only
    has_period_length: bool
    has_flow: bool
    has_age: bool


class CycleRecord(BaseModel):
    cycle_start: str
    cycle_length: int | None
    period_length: int | None
    flow: str | None


class CyclesResponse(BaseModel):
    dataset_id: str
    user_id: str
    cycles: list[CycleRecord]


class CycleEvent(BaseModel):
    type: str
    date: str
    length_days: int
    first_time: bool


class StatsResponse(BaseModel):
    dataset_id: str
    user_id: str
    n_cycles: int
    first_cycle: str | None = None
    last_cycle: str | None = None
    low_confidence: bool
    age: float | None = None
    mean_length: float | None = None
    median_length: float | None = None
    sd_length: float | None = None
    min_length: float | None = None
    max_length: float | None = None
    trend_days_per_cycle: float | None = None
    trend_total_change_days: float | None = None
    baseline_mean: float | None = None
    baseline_sd: float | None = None
    recent_mean: float | None = None
    recent_sd: float | None = None
    mean_change: float | None = None
    sd_change: float | None = None
    short_cycles: int | None = None
    long_cycles: int | None = None
    skipped_cycles: int | None = None
    consecutive_jumps: int | None = None
    mean_period_length: float | None = None
    flow_share: dict[str, float] | None = None
    events: list[CycleEvent] = []
