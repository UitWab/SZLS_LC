# 智慧梁场 FastAPI 中介服务

本交付位于仓库根目录 `02.backend_middleware`，针对 A 的 `backend_db 8.0.0`。
A 源码位于相邻目录 `../01.backend_db`；原始本地交付副本位于 `F:\backend_middleware`。
数据库唯一入口为 `backend_db.interfaces.create_database_services()`；代码和测试均不导入 ORM、CRUD、Session、具体 Service 实现或数据库驱动。

## 已实现

- 梁型、区域、梁位、梁、工序：创建、详情、分页、筛选、部分更新；适用资源支持启停。
- 梁状态显式修改；梁位变更统一使用入位/移位/出位工单的开始、完成、取消接口。
- 工序执行、质量检查、运输交接：记录、查询、受控作废；保留 A 的幂等语义。
- 生命周期事件只读查询和游标增量同步。
- 写操作后的独立审计、统一错误码、请求 ID、访问密钥角色和固定项目隔离。
- PLC 温湿度/压力/应变模拟上报；已结束工序结果通过 A Service 持久化。
- UE5 预留合同、查询、事件增量与测点读取接口；OpenAPI/JSON/枚举文档。

## 启动

首次使用先安装依赖并生成本地配置。在仓库根目录打开 PowerShell：

```powershell
cd .\02.backend_middleware
.\setup.ps1
.\start.ps1
```

默认地址：`http://127.0.0.1:8000`，交互文档：`http://127.0.0.1:8000/docs`。
点击 Swagger 的 Authorize，填写 `.env` 内对应密钥（仅填写值，不加 Bearer）。

新机器安装（要求 Python 3.11+ 和 uv）：

```powershell
.\setup.ps1
```

`setup.ps1` 将生成含随机 ADMIN/READ/PLC 密钥的 `.env`，该文件被 `.gitignore` 排除；脚本不会覆盖已有配置。
在 `.env` 填写 A 提供的 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME`，取消对应注释并重启服务。
`MW_PROJECT_CODE` 必须设为实际项目编码；留空仅访问 A 的 V1 全局数据，不代表全部项目。
A 负责 MySQL 8 建库及迁移至 `f8c2d4e6a709`；B 不自动建库、不迁移、不灌入样例数据。

## 当前联调限制

交付时本机 MySQL80 停止运行，未提供数据库连接配置。HTTP、公开契约模拟和网络启动测试可运行；真实数据库端到端读写仍须配置数据库后完成。
`/health/live` 表示进程存活；`/health/ready` 实际调用公开 Service，数据库不可达时返回 503。
本机已知数据库状态不等于代码测试失败，不应将 liveness 当作数据库就绪。

PLC 时序测点仅保存在单进程内存：默认 2000 条、3600 秒 TTL，重启丢失。
本版必须单 worker，不能直接多进程/多副本部署。后续待 A 提供测点存储契约再接持久化。
UE5 尚未完成真实蓝图联调；坐标轴、原点、单位转换由双方确认，当前仅输出原始毫米坐标。
本版采用项目级服务密钥。不是用户登录/RBAC系统，不将传入 actor_name 当作已认证用户身份。
管理员可显式修正已知梁状态；暂不擅自规定工序审批、质量放行或梁状态迁移顺序。

## 验证与模拟

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/network_smoke.py
.\.venv\Scripts\python.exe -m simulator.plc --beam DEMO-B001 --count 1
```

模拟器默认打印报文。数据库存在对应梁后，设置环境变量 `MW_PLC_KEY`，添加 `--send` 才发送。
项目级部署还需加 `--project 实际项目编码`，或设置环境变量 `MW_PROJECT_CODE`。

```powershell
.\.venv\Scripts\python.exe -m simulator.plc --beam 实际梁编码 --project 实际项目编码 --count 5 --send
.\.venv\Scripts\python.exe -m simulator.plc --beam 实际梁编码 --project 实际项目编码 --mode process --process 实际工序编码 --count 1 --send
```

第二条命令会记录真实的模拟工序事实，仅在约定的测试项目使用。
UE5 替代客户端：设置 `MW_READ_KEY` 后运行 `python -m simulator.ue5_probe`。

## 目录及回仓库位置

| 交付目录 | 用途 | 以后合入仓库的位置 |
|---|---|---|
| backend_middleware/ | Python 应用 | 02.backend_middleware/backend_middleware/ |
| simulator/ | PLC、UE5 探针 | 03.simulator/ |
| docs/ | 接口、JSON、枚举、测试记录 | 00.docs/接口文档/middleware/ |
| tests/、scripts/、启动及包配置 | 测试与运行 | 02.backend_middleware/ |

本次按用户要求将完整交付（含 simulator、docs 和 tests）一起保存在仓库的 `02.backend_middleware` 内，当前可直接安装运行。上表描述以后拆分至公共目录的映射；若拆分需同步调整包发现路径和文档导出位置。
详见 [接口说明](docs/API.md)、[UE5接入](docs/UE5.md)、[测试记录](docs/VERIFICATION.md)。
