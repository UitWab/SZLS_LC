# 验证记录

日期：2026-09-22。交付位置：`F:\backend_middleware`。

## 已通过

- 独立 Python 3.11.15 虚拟环境安装：成功；A 包8.0.0可导入。
- `python -m pytest`：58 passed，2条第三方依赖弃用提示（Starlette/httpx及anyio），无失败。
- `python scripts/network_smoke.py`：PASS。启动真实 Uvicorn 子进程，以实际 HTTP 验证存活、未认证401、UE5合同、枚举和OpenAPI，随后结束测试进程。
- OpenAPI导出：53个路径（部分含多个HTTP方法），包含A公开DTO定义。
- PLC模拟脚本：成功生成温度和湿度JSON；默认模式不写库。
- AST架构检查：应用与模拟器没有导入 backend_db.models/crud/database/services、SQLAlchemy或数据库驱动。
- 原始 SZLS_LC 工作区未修改；未提交或推送Git。

## 自动测试范围

公开Protocol的autospec替身校验调用签名。覆盖10组资源列表、筛选和详情，创建、部分更新、启停、工单动作、记录作废、枚举和游标。
覆盖认证缺失/角色限制/未配置时拒绝、固定项目隔离、禁止include_global与跨项目null、DTO错误、错误状态映射、响应敏感文本清理、UTC及Decimal序列化。
覆盖PLC缓存幂等/冲突、未知梁拒绝、单位与时间校验、乱序处理、线程并发、容量淘汰、TTL、模拟器重试复用消息与409不重试。
验证工单完成只调用一次A公开完成方法，写后审计失败返回成功及warning，不伪装业务回滚。

## 真实数据库验证结果

实际调用 `create_database_services()`，没有使用替身：

| 检查 | 结果 |
|---|---|
| GET /health/live | 200 |
| GET /health/ready | 503 database_unavailable |
| GET /api/v1/beams | 503 database_unavailable |
| GET /api/v1/beam-positions | 503 database_unavailable |

环境检查：A源码根目录无 `.env`；当前进程无DB连接环境变量；本机MySQL80服务Stopped。
因此没有进行真实数据库新增/修改，也没有声称完成真实数据库端到端验证。
后续填写联调库连接并由A准备V8迁移，重启本服务，确认ready=200后，在测试项目执行创建梁型→区域→梁位→梁→工单→PLC工序→质量→运输→UE5查询联调。
上述数据库Service内部幂等、并发事务正确性仍依赖A的既有测试，不由Mock测试证明。

## 仍待双方联调

UE5真实蓝图/插件、模型编码、毫米到厘米转换、坐标原点与轴向、断线恢复和画面刷新需C确认。
PLC时序持久化和跨进程消息交付未实现；当前缓存会在重启或过期时丢失。
项目服务密钥不是完整用户登录/RBAC，生产权限、设备身份与审批流程需明确业务规则后扩展。
