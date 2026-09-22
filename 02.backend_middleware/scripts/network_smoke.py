"""启动真实 Uvicorn 验证 HTTP。只读，不写数据库，运行后结束子进程。"""
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

root = Path(__file__).resolve().parents[1]
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
env = os.environ.copy()
token = secrets.token_urlsafe(32)
env["MW_ADMIN_KEY"] = token
process = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend_middleware.app:create_app", "--factory",
    "--host", "127.0.0.1", "--port", str(port)], cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
        deadline = time.monotonic() + 20
        while True:
            try:
                response = client.get("/health/live")
                if response.status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Uvicorn 启动失败")
            time.sleep(0.2)
        assert client.get("/api/v1/ue5/contract").status_code == 401
        headers = {"Authorization": "Bearer " + token}
        assert client.get("/api/v1/ue5/contract", headers=headers).status_code == 200
        assert client.get("/api/v1/meta/enums", headers=headers).status_code == 200
        schema = client.get("/openapi.json").json()
        print(json.dumps({"http_smoke": "PASS", "paths": len(schema["paths"]), "database_write": False}))
finally:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
