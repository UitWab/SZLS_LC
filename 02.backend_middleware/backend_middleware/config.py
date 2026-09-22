import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    admin_key: str = ""
    read_key: str = ""
    plc_key: str = ""
    project_code: str | None = None
    telemetry_capacity: int = 2000
    telemetry_ttl_seconds: int = 3600

    def __post_init__(self):
        keys = [key for key in (self.admin_key, self.read_key, self.plc_key) if key]
        if any(len(key) < 16 for key in keys) or len(keys) != len(set(keys)):
            raise ValueError("访问密钥必须不同且至少 16 字符")
        if self.telemetry_capacity < 1 or self.telemetry_ttl_seconds < 1:
            raise ValueError("缓存容量和 TTL 必须为正数")
        if self.project_code is not None and not 1 <= len(self.project_code) <= 64:
            raise ValueError("项目编码长度必须为 1–64")

    @classmethod
    def from_env(cls):
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        return cls(
            admin_key=os.getenv("MW_ADMIN_KEY", ""),
            read_key=os.getenv("MW_READ_KEY", ""),
            plc_key=os.getenv("MW_PLC_KEY", ""),
            project_code=os.getenv("MW_PROJECT_CODE", "").strip() or None,
            telemetry_capacity=int(os.getenv("MW_TELEMETRY_CAPACITY", "2000")),
            telemetry_ttl_seconds=int(os.getenv("MW_TELEMETRY_TTL_SECONDS", "3600")),
        )
