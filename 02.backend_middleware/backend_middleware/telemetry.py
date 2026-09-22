"""临时测点接入：线程安全、有界缓存；不声称具备数据库持久化。"""
import hashlib
import json
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from threading import Lock

from fastapi import HTTPException
from pydantic import AwareDatetime, Field, model_validator

from .common import Model


class Metric(StrEnum):
    TEMPERATURE = "TEMPERATURE"
    HUMIDITY = "HUMIDITY"
    PRESSURE = "PRESSURE"
    STRAIN = "STRAIN"


UNITS = {Metric.TEMPERATURE: "degC", Metric.HUMIDITY: "%", Metric.PRESSURE: "MPa", Metric.STRAIN: "ue"}


class Measurement(Model):
    metric: Metric
    value: float = Field(allow_inf_nan=False)
    unit: str

    @model_validator(mode="after")
    def validate_unit(self):
        if self.unit != UNITS[self.metric]:
            raise ValueError("测点单位与 metric 不匹配")
        if self.metric == Metric.HUMIDITY and not 0 <= self.value <= 100:
            raise ValueError("湿度必须在 0–100 范围内")
        return self


class TelemetryReport(Model):
    message_id: str = Field(min_length=1, max_length=128)
    device_id: str = Field(min_length=1, max_length=64)
    project_code: str | None = Field(default=None, min_length=1, max_length=64)
    beam_code: str = Field(min_length=1, max_length=64)
    observed_at: AwareDatetime
    measurements: list[Measurement] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_report(self):
        self.observed_at = self.observed_at.astimezone(timezone.utc)
        metrics = [item.metric for item in self.measurements]
        if len(metrics) != len(set(metrics)):
            raise ValueError("同一报文不得重复 metric")
        if self.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("测点时间超出允许的 5 分钟时钟偏差")
        return self


class TelemetryStore:
    def __init__(self, capacity=2000, ttl=3600):
        self.capacity, self.ttl = capacity, ttl
        self._records = OrderedDict()
        self._lock = Lock()

    def _expire(self):
        now = time.monotonic()
        for key in list(self._records):
            if now - self._records[key][0] >= self.ttl:
                del self._records[key]

    def put(self, report):
        canonical = report.model_dump(mode="json")
        canonical["measurements"].sort(key=lambda m: m["metric"])
        digest = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
        key = (report.project_code, report.device_id, report.message_id)
        with self._lock:
            self._expire()
            if key in self._records:
                if self._records[key][1] != digest:
                    raise HTTPException(409, "message_id_conflict")
                return {"message_id": report.message_id, "duplicate": True, "persisted": False}
            self._records[key] = (time.monotonic(), digest, report.model_copy(deep=True))
            while len(self._records) > self.capacity:
                self._records.popitem(last=False)
        return {"message_id": report.message_id, "duplicate": False, "persisted": False}

    def latest(self, project_code, beam_code=None, device_id=None, limit=100):
        with self._lock:
            self._expire()
            latest = {}
            for _, _, report in self._records.values():
                if report.project_code != project_code or (beam_code and report.beam_code != beam_code) or (device_id and report.device_id != device_id):
                    continue
                key = (report.device_id, report.beam_code)
                if key not in latest or latest[key].observed_at <= report.observed_at:
                    latest[key] = report
            rows = sorted(latest.values(), key=lambda r: (r.observed_at, r.device_id), reverse=True)
            return {"items": [r.model_copy(deep=True) for r in rows[:limit]], "has_more": len(rows) > limit, "persisted": False}
