import uvicorn

if __name__ == "__main__":
    # 内存测点缓存只支持单 worker；局域网部署由命令行显式指定 host。
    uvicorn.run("backend_middleware.app:create_app", factory=True, host="127.0.0.1", port=8000, workers=1)
