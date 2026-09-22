"""从实际应用生成 OpenAPI 与枚举文件，避免文档手写漂移。"""
import json
from enum import Enum
from pathlib import Path

from backend_db import schemas as s
from backend_middleware.app import create_app
from backend_middleware.config import Settings
from backend_middleware.telemetry import Metric, UNITS

root = Path(__file__).resolve().parents[1] / "docs"
root.mkdir(exist_ok=True)
document = create_app(settings=Settings()).openapi()
(root / "openapi.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
enums = {name: [item.value for item in cls] for name in s.__all__
         if isinstance((cls := getattr(s, name)), type) and issubclass(cls, Enum)}
enums["Metric"] = list(Metric)
(root / "enums.json").write_text(json.dumps({"database_contract": "8.0.0", "enums": enums,
    "beam_status_labels": s.BEAM_STATUS_LABELS, "units": UNITS}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"已导出 {len(document['paths'])} 个路径的 OpenAPI 和枚举字典。")
