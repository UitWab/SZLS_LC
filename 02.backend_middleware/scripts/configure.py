"""初始化本地密钥；不覆盖已有配置，不输出密钥。"""
from pathlib import Path
from secrets import token_urlsafe

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    print("已存在 .env，保留原配置。")
else:
    with path.open("x", encoding="utf-8") as handle:
        handle.write("# 本地敏感配置，禁止提交 Git\n")
        for role in ("ADMIN", "READ", "PLC"):
            handle.write(f"MW_{role}_KEY={token_urlsafe(32)}\n")
        handle.write("MW_PROJECT_CODE=\nMW_TELEMETRY_CAPACITY=2000\nMW_TELEMETRY_TTL_SECONDS=3600\n")
        handle.write("# 填写 A 提供的联调数据库配置，再取消下面各行注释。\n")
        handle.write("# DB_HOST=127.0.0.1\n# DB_PORT=3306\n# DB_USER=\n# DB_PASSWORD=\n# DB_NAME=\n")
    print("已生成 .env 和三种随机访问密钥；数据库配置仍待填写。")
