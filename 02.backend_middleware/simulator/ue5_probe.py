"""替代尚未更新的 UE5 客户端，验证合同和增量拉取协议。"""
import argparse
import json
import os

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--cursor")
    args = parser.parse_args()
    token = os.getenv("MW_READ_KEY", "")
    if not token:
        parser.error("请设置 MW_READ_KEY")
    with httpx.Client(base_url=args.url, headers={"Authorization": "Bearer " + token}, timeout=15) as client:
        for path, params in [("/api/v1/ue5/contract", {}),
                             ("/api/v1/ue5/events", {"cursor": args.cursor} if args.cursor else {}),
                             ("/api/v1/ue5/telemetry/latest", {})]:
            response = client.get(path, params=params)
            response.raise_for_status()
            print(json.dumps(response.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
