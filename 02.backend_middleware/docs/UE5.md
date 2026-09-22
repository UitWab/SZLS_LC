# UE5 预留接口（PROVISIONAL）

本版本不需要 UE5 工程。协议已可用，但还没有与 C 的蓝图/插件做真实联调。
开始调用 GET `/api/v1/ue5/contract`；Authorization 使用 READ 密钥。

## 初始化及持续同步

1. 固定当前项目。读取 `/meta/enums` 和 `/yard-tree`。
2. 分页读取 `/beams`、`/beam-positions`；需要详细坐标时按梁位ID读取详情，列表 Summary 不保证带坐标。
3. 对 `/ue5/events` 从空游标开始，按响应 next_cursor 继续；has_more=true 时继续拉取。
4. 收到事件后按 beam_code 重新读取 `/beams/by-code/{beam_code}`，刷新该梁和相关梁位。
5. 当前批次全部处理成功后保存 next_cursor；处理失败保留旧游标重试，使用事件ID去重。
6. has_more=false 后保留游标，以1–2秒间隔继续轮询。参数和项目不能随意切换。

空游标从 A 的事件流起点开始，并非只取最新一条。将游标视为不透明字符串，禁止自行加一或解析。
事件流与多页快照不构成原子快照。先读取对象再从事件流起点重放并重新读取对象，避免初始化期间遗漏状态变化。
A 的生命周期事件不涵盖普通资料 PATCH、工序/质量/运输记录新增。因此定期刷新列表和详情，或由 UI 打开时查询；不要将该事件流当成通用 CDC。
重连使用已处理完成的游标；服务不提供消费确认、exactly-once 或 WebSocket 推送。

## 模型、坐标和测点

业务唯一标识使用 beam_code；模型资产与梁型 type_code 的映射由 C 确认。
原始 x_mm/y_mm/z_mm 为毫米和可空 Decimal 字符串。UE 默认厘米，但轴向、原点、旋转待确认；当前接口不做隐式缩放、旋转或补零。
GET `/ue5/telemetry/latest?beam_code=...` 返回仍在内存 TTL 内的最新设备/梁报文。
以 observed_at 判断新鲜度；超时或无数据应显示“无数据/离线”，不得继续显示成实时值。
时间 UTC/Z；本地显示可转换为北京时间；ID需 int64，坐标按 Decimal 字符串转 double。
使用通用 `/process-records/search`、`/quality-records/search`、`/transport-records/search`，filters.beam_code 可获取单梁履历。

## 无 UE5 时验证

启动服务，配置数据库和 READ 密钥后运行：

```powershell
.\.venv\Scripts\python.exe -m simulator.ue5_probe
```

该探针读取合同、首批事件和最新测点，不替代 C 对坐标、材质、蓝图动画与并发场景的验收。
