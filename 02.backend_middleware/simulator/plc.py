import argparse
import json
import os
import random
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx


def send(client, path, payload, retries=3):
    """仅重试连接错误、429、5xx；所有重试复用同一报文/幂等键。"""
    for attempt in range(retries + 1):
        try:
            response = client.post(path, json=payload)
            if response.status_code != 429 and response.status_code < 500:
                response.raise_for_status()
                return response.json()
            response.raise_for_status()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code == 429 or exc.response.status_code >= 500
            if not retryable or attempt == retries:
                raise
            time.sleep(min(2 ** attempt, 8))


def telemetry(beam, device, project=None):
    return {"message_id": str(uuid4()), "device_id": device, "project_code": project,
        "beam_code": beam, "observed_at": datetime.now(timezone.utc).isoformat(),
        "measurements": [{"metric": "TEMPERATURE", "value": round(random.uniform(20, 35), 2), "unit": "degC"},
                         {"metric": "HUMIDITY", "value": round(random.uniform(60, 95), 2), "unit": "%"}]}


def execution(beam, device, process, project=None):
    now = datetime.now(timezone.utc)
    event_id = str(uuid4())
    return {"execution_code": "SIM-" + event_id, "project_code": project, "beam_code": beam,
        "process_code": process, "result_code": "SUCCESS", "started_at": (now - timedelta(minutes=1)).isoformat(),
        "finished_at": now.isoformat(), "actor_name": device, "source": "DEVICE",
        "external_record_id": device + ":" + event_id}


def main():
    parser = argparse.ArgumentParser(description="PLC 模拟器：默认只打印报文；--send 才发送")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--beam", required=True)
    parser.add_argument("--device", default="PLC-SIM-001")
    parser.add_argument("--project", default=os.getenv("MW_PROJECT_CODE") or None)
    parser.add_argument("--mode", choices=["telemetry", "process"], default="telemetry")
    parser.add_argument("--process", help="process 模式必填：A 已配置的工序编码")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    if args.count < 1 or args.interval < 0 or len(args.device) > 64:
        parser.error("count >= 1，interval >= 0，device 长度 <= 64")
    if args.mode == "process" and not args.process:
        parser.error("process 模式需要 --process")
    token = os.getenv("MW_PLC_KEY", "")
    if args.send and not token:
        parser.error("发送前设置环境变量 MW_PLC_KEY")
    path = "/api/v1/plc/telemetry" if args.mode == "telemetry" else "/api/v1/plc/process-records"
    with httpx.Client(base_url=args.url, headers={"Authorization": "Bearer " + token}, timeout=15) as client:
        for index in range(args.count):
            payload = telemetry(args.beam, args.device, args.project) if args.mode == "telemetry" else execution(args.beam, args.device, args.process, args.project)
            if args.send:
                try:
                    print(json.dumps(send(client, path, payload), ensure_ascii=False))
                except httpx.HTTPError as exc:
                    code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else "network_error"
                    parser.exit(1, f"发送失败: {code}\n")
            else:
                print(json.dumps(payload, ensure_ascii=False))
            if index + 1 < args.count:
                time.sleep(args.interval)


if __name__ == "__main__":
    main()
