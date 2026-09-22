# 中介接口 v1

准确字段和模型以 `openapi.json`、在线 `/docs` 为准；枚举从 A 公开 DTO 导出到 `enums.json`。
执行 `python scripts/export_contract.py` 可重新生成，两份文件均不含密钥。

## 认证和项目

业务路径前缀 `/api/v1`。请求头 `Authorization: Bearer <密钥>`。
ADMIN 可读写业务；READ 只读（含 POST /search）；PLC 只能调用 `/plc/*`。
未配置任何密钥返回 503；无效密钥 401；角色或项目不匹配 403。
每个实例由 `MW_PROJECT_CODE` 固定一个项目，所有查询及写入强制使用该作用域。
报文省略 project_code 自动填入当前项目；显式 project_code（含 null）必须匹配。
include_global=true 被拒绝。跨项目部署应分实例/密钥，不能让前端随意改项目。
项目需由 A 或已有管理流程预置；B 仅提供 `/projects/current`，不公开用户凭据或权限管理。

## 通用资源接口

以下每类均有 GET `/资源` 分页、POST `/资源/search` 筛选、GET `/资源/{key}` 详情。
GET 分页参数 page 默认1、page_size默认20、上限100；复杂筛选使用 search JSON。

| 资源 | key | 创建 POST /资源 | PATCH /资源/{key} | 特殊操作 |
|---|---|---|---|---|
| beam-types | 数字ID | 是 | 是 | POST /{key}/active |
| yard-areas | 数字ID | 是 | 是 | active、GET /yard-tree |
| beam-positions | 数字ID | 是 | 是 | active |
| beams | 数字ID | 是 | 是 | GET /by-code/{beam_code}、POST /by-code/{beam_code}/status |
| processes | 数字ID | 是 | 是 | active |
| position-work-orders | 数字ID | 是 | 否 | POST /by-code/{work_order_code}/start、complete、cancel |
| beam-events | 数字ID | 否 | 否 | GET /ue5/events |
| process-records | execution_code | 是 | 否 | POST /{key}/void |
| quality-records | inspection_code | 是 | 否 | POST /{key}/void |
| transport-records | handover_code | 是 | 否 | POST /{key}/void |

启停体：`{"is_active": false}`。梁状态体：`{"status": "CURING"}`。
PATCH 未提交字段保持原值；允许清空的字段提交 null 才清空。
所有写入成功返回 200（包括 A 返回既有幂等记录），不要据此假设总是新增。
没有梁删除、事件写入、记录任意更新或物理删除接口。
工单 complete 只调用 A 的同名方法，由 A 在同一事务中完成工单与梁位变更。
记录工序、质量和运输事实不自动改变梁状态。

## PLC

POST `/plc/telemetry`：`examples/plc_telemetry.json`。
必须存在对应项目的梁；observed_at 必须含时区，最多允许超前服务器5分钟。
支持 TEMPERATURE/degC、HUMIDITY/%、PRESSURE/MPa、STRAIN/ue（微应变），拒绝 NaN/Infinity。
同报文 metric 不重复，湿度0–100。最多32测点。
幂等键为 project_code + device_id + message_id：缓存内同内容返回 duplicate=true，不同内容409。
缓存 TTL 或容量淘汰后不再保证去重。响应 persisted=false 明确声明无持久化。
乱序报文不覆盖较新 observed_at；latest 默认最多100个设备/梁组合，可按 beam_code、device_id 筛选。

POST `/plc/process-records`：`examples/process_record.json`。
强制 source=DEVICE，external_record_id 必填；A 以 source+external_record_id 幂等。
不同设备必须命名空间化 external_record_id，例如 PLC001-process-000001。
actor_name 为设备提供的事实快照，不是用户认证证据；审计身份由密钥角色生成。

## JSON 约定

成功：`{"data": ..., "request_id": "服务器生成ID", "warnings": []}`。
失败：`{"error":{"code":"beam_not_found","details":[]},"request_id":"..."}`。
每个响应带 X-Request-ID，客户端重试将获得新 request_id；它不是幂等键。
日期 YYYY-MM-DD；时间统一输出 UTC ISO8601/Z（A 的无时区时间按 UTC 解释）。
Decimal 输出字符串以保留精度；ID 为整数，UE5 客户端须支持 int64，不能经 float32 中转。
枚举使用英文代码；中文标签仅用于显示，不按数组下标解释状态。

| HTTP | 含义 |
|---|---|
| 401/403 | 认证失败/无权限或跨项目 |
| 404 | A 资源不存在或不在当前项目 |
| 409 | 唯一编码、状态、占位或报文幂等冲突 |
| 422 | DTO、枚举、范围、关联业务参数无效 |
| 503 | 数据库不可用或认证未配置 |
| 500 | 未分类内部错误（不返回内部异常文本） |

## 审计和事务

业务写成功后通过 audit_logs.record 追加审计，查询为管理员 GET `/audit-logs`。
只保存动作名、项目、密钥角色、结果和 request_id；不写请求体、密钥、密码。
业务与审计是两次独立 A 调用，不具备跨调用原子性；审计失败返回业务成功并带 warnings=["audit_not_recorded"]。
不要因该警告盲目重放非幂等写入；需要强事务审计时应由 A 新增组合用例。
拒绝、参数错误、PLC临时测点和纯查询当前不写持久化审计。

## 后续生产接入

服务密钥用于封闭联调/可信服务间调用。正式多用户端需补用户登录、密钥轮换、用户与项目权限映射。
网络部署用 HTTPS 反向代理，默认启动仅监听127.0.0.1。
UE5 原生 HTTP 不依赖 CORS；浏览器前端接入时应配置明确的来源白名单。
PLC 数据持久化、消息队列、设备身份绑定、报警规则、用户业务审批未纳入 A 当前契约。
