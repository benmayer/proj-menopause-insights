"""Dataset store behind a tiny interface. MVP: in memory only, nothing written to disk.

To persist later (accounts, consent, retention), replace this class with a Supabase-backed one
that has the same put/get methods; nothing else in the app changes.
"""
import time
import uuid
from collections import OrderedDict

import pandas as pd

MAX_DATASETS = 20
TTL_SECONDS = 60 * 60  # uploads vanish after an hour


class DatasetNotFound(KeyError):
    pass


class MemoryStore:
    def __init__(self):
        self._data: OrderedDict[str, tuple[float, pd.DataFrame, bool]] = OrderedDict()

    def put(self, df: pd.DataFrame, dataset_id: str | None = None, permanent: bool = False) -> str:
        self._expire()
        dataset_id = dataset_id or uuid.uuid4().hex[:12]
        self._data[dataset_id] = (time.time(), df, permanent)
        while sum(1 for v in self._data.values() if not v[2]) > MAX_DATASETS:
            oldest = next(k for k, v in self._data.items() if not v[2])
            del self._data[oldest]
        return dataset_id

    def get(self, dataset_id: str) -> pd.DataFrame:
        self._expire()
        if dataset_id not in self._data:
            raise DatasetNotFound(dataset_id)
        return self._data[dataset_id][1]

    def ids(self, prefix: str = "") -> list[str]:
        self._expire()
        return [k for k in self._data if k.startswith(prefix)]

    def delete(self, dataset_id: str) -> None:
        self._data.pop(dataset_id, None)

    def _expire(self):
        now = time.time()
        for k in [k for k, (t, _, perm) in self._data.items() if not perm and now - t > TTL_SECONDS]:
            del self._data[k]


class LabsNotFound(KeyError):
    pass


class LabStore:
    """Parsed lab draws per labs_id, in memory only, same TTL as datasets. Holds values, never the PDF."""
    def __init__(self):
        self._data: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()

    def put(self, draws: list[dict], labs_id: str | None = None) -> str:
        self._expire()
        labs_id = labs_id or uuid.uuid4().hex[:12]
        self._data[labs_id] = (time.time(), sorted(draws, key=lambda d: d["draw_date"]))
        while len(self._data) > MAX_DATASETS:
            self._data.popitem(last=False)
        return labs_id

    def get(self, labs_id: str) -> list[dict]:
        self._expire()
        if labs_id not in self._data:
            raise LabsNotFound(labs_id)
        return self._data[labs_id][1]

    def delete(self, labs_id: str) -> None:
        self._data.pop(labs_id, None)

    def _expire(self):
        now = time.time()
        for k in [k for k, (t, _) in self._data.items() if now - t > TTL_SECONDS]:
            del self._data[k]


store = MemoryStore()
lab_store = LabStore()
