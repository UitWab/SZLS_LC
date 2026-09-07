# A→B 数据访问接口接入说明

## 1. 文档信息

- 数据契约版本：2.0.0
- Python：3.11 及以上
- 数据库：MySQL 8.0
- A 模块包名：`backend_db`
- B 模块唯一组合入口：`backend_db.interfaces.create_database_services`
- 当前数据库迁移版本：`e5c1a7b3d902`

本说明定义 A 数据库模块向 B 后端中间件模块提供的 Python 调用契约。B 只依赖公开接口、DTO、枚举和异常，不直接依赖 ORM、CRUD、Session 或表结构实现。

## 2. 安装方式

在包含 `01.backend_db` 与 `02.backend_middleware` 的项目根目录中，先激活 B 自己的 Python 3.11+ 虚拟环境，再执行：

```powershell
python -m pip install -e .\01.backend_db
```

不得依赖系统 Python 或直接复用 A 的 `.venv`；A、B 应各自维护虚拟环境和依赖。开发安装会使 B 直接使用当前 A 模块源码。联调或发布时应固定 Git 提交号或版本标签，避免契约变化未被感知。

A 模块读取以下环境变量：

```text
DB_HOST
DB_PORT
DB_USER
DB_PASSWORD
DB_NAME
```

变量示例见 A 模块的 `.env.example`。不得向仓库提交真实密码，也不应向 B 提供 MySQL 管理员账号。数据库账号应按部署环境配置最小必要权限。

## 3. 允许和禁止的依赖边界

B 可以导入：

```python
from backend_db.interfaces import create_database_services
from backend_db.schemas import BeamCreate, BeamFilter, PageRequest
from backend_db.exceptions import BackendDBError
```

B 禁止导入或使用：

- `backend_db.models`：SQLAlchemy ORM 模型；
- `backend_db.crud`：A 模块内部数据访问实现；
- `backend_db.database`：Session、Engine 和 Unit of Work；
- `backend_db.services` 中的具体实现类；
- SQLAlchemy 查询对象、数据库表对象或原生 SQL。

公开返回值均为 Pydantic DTO，不包含 ORM 对象。B 不应根据数据库表字段自行构造业务逻辑，而应以本接口和 DTO 为准。

## 4. 初始化与调用方式

```python
from backend_db.interfaces import create_database_services

database_services = create_database_services()
```

返回的服务集合包含：

| 属性 | 用途 |
| --- | --- |
| `projects` | 项目档案维护与查询 |
| `processes` | 通用或项目级工序基础资料配置 |
| `users` | 用户资料、认证记录和密码散列存储 |
| `access_control` | 角色、权限、项目成员与有效权限查询 |
| `beam_types` | 梁型资料维护与查询 |
| `yard_areas` | 梁场区域维护、查询和树形结构读取 |
| `beam_positions` | 梁位维护与占用状态查询 |
| `beams` | 梁资料、状态和当前梁位管理 |

服务方法为同步 Python 调用。服务集合可以由 B 在应用启动时创建并复用；每次方法调用都会在 A 模块内部创建和关闭数据库 Session。

如果 B 使用异步 Web 框架，应由 B 在其应用层安排同步数据库调用的执行方式。A 不提供 FastAPI 路由、HTTP 响应、鉴权、Redis、MQTT 或 WebSocket 实现。

密码明文校验、密码散列生成、登录会话、JWT 和接口鉴权均属于 B。A 只保存 B 提供的密码散列，并通过独立的认证记录 DTO 向 B 提供登录校验所需数据。

## 5. 事务语义

- 每次 Service 方法调用是一个独立事务边界。
- 写方法成功后由 A 模块提交，失败时回滚。
- 读方法结束后由 A 模块关闭 Session。
- B 不提交、不回滚，也不持有 Session。
- B 不应假设连续多个 Service 调用属于同一个原子事务。
- 梁位分配、移动、释放及相关占用检查在 A 内部完成并发保护。

如果未来出现必须跨多个操作保持原子性的业务，应由双方先增加新的 A 层用例接口，而不是让 B 直接控制数据库事务。

## 6. 公共 DTO 与序列化

DTO 从 `backend_db.schemas` 导入，使用 Pydantic 2。常用操作：

```python
payload = result.model_dump(mode="json")
```

`mode="json"` 会将日期、时间、Decimal 和枚举转换为适合 B 继续生成 JSON 响应的值。B 不应修改返回 DTO 后将其作为 ORM 对象保存。

部分更新 DTO 使用“是否提交字段”区分未修改和显式置空。B 构造更新 DTO 时，只传用户实际提交的字段；不要先用完整默认对象覆盖缺失字段。

## 7. 分页、筛选与排序

所有列表查询均采用 `PageRequest`：

| 字段 | 默认值 | 约束 | 含义 |
| --- | ---: | --- | --- |
| `page` | 1 | 大于等于 1 | 页码 |
| `page_size` | 20 | 1～100 | 每页数量 |
| `include_total` | `True` | 布尔值 | 是否计算总数 |

返回 `PageResult`：

| 字段 | 含义 |
| --- | --- |
| `items` | 当前页 DTO 列表 |
| `page` | 当前页码 |
| `page_size` | 每页数量 |
| `total` | 总数；`include_total=False` 时为 `None` |
| `has_next` | 是否还有下一页 |
| `has_previous` | 是否存在上一页 |

调用示例：

```python
from backend_db.schemas import (
    BeamFilter,
    BeamSortField,
    BeamStatus,
    PageRequest,
    SortOrder,
)

result = database_services.beams.list(
    filters=BeamFilter(
        project_code="P001",
        statuses=[BeamStatus.STORED, BeamStatus.READY_TO_SHIP],
        is_positioned=True,
    ),
    page_request=PageRequest(page=1, page_size=20),
    sort_by=BeamSortField.UPDATED_AT,
    sort_order=SortOrder.DESC,
)
```

筛选字段：

| 对象 | 支持的筛选 |
| --- | --- |
| 梁型 | 项目编码、是否包含全局数据、编码、启停状态、关键词、长宽高和重量范围 |
| 区域 | 项目编码、是否包含全局数据、编码、类型、父区域编码、启停状态、关键词 |
| 梁位 | 项目编码、是否包含全局数据、编码、区域编码、启停状态、占用状态、关键词 |
| 梁 | 项目编码、是否包含全局数据、编码、梁型、多个状态、当前梁位、区域、是否在梁位、生产日期范围、创建/更新时间范围、关键词 |

排序字段必须使用对应的 `*SortField` 枚举，顺序使用 `SortOrder.ASC` 或 `SortOrder.DESC`，不接受 B 传入任意数据库字段名。

当前公开列表使用页码分页。`CursorPageRequest` 和 `CursorPageResult` 只是为后续数字孪生增量同步预留的数据结构，当前 Service 尚未提供游标查询方法。

梁型、区域、梁位、梁和工序同时遵循项目作用域规则：

- `project_code=None` 只访问 V1 全局数据，即 `project_id IS NULL`；
- 传入 `project_code` 时只访问该项目的数据；
- 列表筛选同时设置 `include_global=True` 时，返回指定项目数据和 V1 全局数据；
- 项目级资源按 ID 或业务编码读取、更新、启停、状态修改和梁位操作时，也必须传入匹配的 `project_code`；
- 梁、梁型、区域和梁位之间的关联必须属于同一项目，跨项目关联会被拒绝。

因此 B 不得先读取全局列表再自行按项目猜测归属，也不得省略项目路由中的 `project_code`。上述规则保留了 V1 全局数据兼容性，同时防止完成项目归属回填后出现跨项目读取或修改。

## 8. Service 方法清单

### 8.1 梁型 `database_services.beam_types`

| 方法 | 输入 | 返回 |
| --- | --- | --- |
| `create(data)` | `BeamTypeCreate`，可含 `project_code` | `BeamTypeRead` |
| `get(beam_type_id, project_code=...)` | 整数 ID、项目作用域 | `BeamTypeRead` |
| `get_by_code(type_code, project_code=...)` | 梁型编码、项目作用域 | `BeamTypeRead` |
| `list(filters, page_request, sort_by, sort_order)` | `BeamTypeFilter` 等 | `PageResult[BeamTypeSummary]` |
| `update(beam_type_id, data, project_code=...)` | ID、`BeamTypeUpdate`、项目作用域 | `BeamTypeRead` |
| `set_active(beam_type_id, is_active=..., project_code=...)` | ID、启停值、项目作用域 | `BeamTypeRead` |

梁型不提供物理删除，通过 `set_active` 控制是否可继续用于新建或修改梁。

### 8.2 区域 `database_services.yard_areas`

| 方法 | 输入 | 返回 |
| --- | --- | --- |
| `create(data)` | `YardAreaCreate`，可含 `project_code` | `YardAreaRead` |
| `get(area_id, project_code=...)` | 整数 ID、项目作用域 | `YardAreaRead` |
| `get_by_code(area_code, project_code=...)` | 区域编码、项目作用域 | `YardAreaRead` |
| `list(filters, page_request, sort_by, sort_order)` | `YardAreaFilter` 等 | `PageResult[YardAreaSummary]` |
| `tree(is_active=..., project_code=..., include_global=...)` | 启停状态、项目作用域 | `list[YardAreaTreeNode]` |
| `update(area_id, data, project_code=...)` | ID、`YardAreaUpdate`、项目作用域 | `YardAreaRead` |
| `set_active(area_id, is_active=..., project_code=...)` | ID、启停值、项目作用域 | `YardAreaRead` |

区域层级循环、无效父区域和停用约束由 A 校验。区域不提供物理删除。

### 8.3 梁位 `database_services.beam_positions`

| 方法 | 输入 | 返回 |
| --- | --- | --- |
| `create(data)` | `BeamPositionCreate`，可含 `project_code` | `BeamPositionRead` |
| `get(position_id, project_code=...)` | 整数 ID、项目作用域 | `BeamPositionRead` |
| `get_by_code(position_code, project_code=...)` | 梁位编码、项目作用域 | `BeamPositionRead` |
| `list(filters, page_request, sort_by, sort_order)` | `BeamPositionFilter` 等 | `PageResult[BeamPositionSummary]` |
| `update(position_id, data, project_code=...)` | ID、`BeamPositionUpdate`、项目作用域 | `BeamPositionRead` |
| `set_active(position_id, is_active=..., project_code=...)` | ID、启停值、项目作用域 | `BeamPositionRead` |

被梁占用的梁位不能停用。梁位不提供物理删除。

### 8.4 梁 `database_services.beams`

| 方法 | 输入 | 返回 |
| --- | --- | --- |
| `create(data)` | `BeamCreate`，可含 `project_code` | `BeamRead` |
| `get(beam_id, project_code=...)` | 整数 ID、项目作用域 | `BeamRead` |
| `get_by_code(beam_code, project_code=...)` | 梁编码、项目作用域 | `BeamRead` |
| `list(filters, page_request, sort_by, sort_order)` | `BeamFilter` 等 | `PageResult[BeamSummary]` |
| `update(beam_id, data, project_code=...)` | ID、`BeamUpdate`、项目作用域 | `BeamRead` |
| `change_status(beam_code, data, project_code=...)` | 梁编码、`BeamStatusChange`、项目作用域 | `BeamRead` |
| `assign_position(beam_code, data, project_code=...)` | 梁编码、`BeamPositionCommand`、项目作用域 | `BeamRead` |
| `move_beam(beam_code, data, project_code=...)` | 梁编码、`BeamPositionCommand`、项目作用域 | `BeamRead` |
| `release_position(beam_code, project_code=...)` | 梁编码、项目作用域 | `BeamRead` |

`assign_position` 只用于当前没有梁位的梁；已有梁位时应调用 `move_beam`。重复移动到当前梁位、重复释放空梁位按幂等成功处理。

当前明确不提供删除梁接口。`current_position_*` 只表示梁场内当前物理梁位，不表示运输、到场或架设阶段的全局位置。

### 8.5 项目 `database_services.projects`

| 方法 | 输入 | 返回 |
| --- | --- | --- |
| `create(data)` | `ProjectCreate` | `ProjectRead` |
| `get(project_id)` | 项目 ID | `ProjectRead` |
| `get_by_code(project_code)` | 项目编码 | `ProjectRead` |
| `list(filters, page_request, sort_by, sort_order)` | `ProjectFilter` 等 | `PageResult[ProjectSummary]` |
| `update(project_id, data)` | ID、`ProjectUpdate` | `ProjectRead` |
| `set_active(project_id, is_active=...)` | ID、启停值 | `ProjectRead` |

V2 不生成默认项目。既有梁场数据的 `project_id` 暂时允许为空，待真实项目编码和数据归属确认后再制定回填与非空迁移。新建项目级梁场数据时必须提供 `project_code`；省略时创建的是兼容 V1 的全局数据。

### 8.6 工序 `database_services.processes`

| 方法 | 输入 | 返回 |
| --- | --- | --- |
| `create(data)` | `ProcessDefinitionCreate` | `ProcessDefinitionRead` |
| `get(process_definition_id, project_code=...)` | 工序 ID、项目作用域 | `ProcessDefinitionRead` |
| `get_by_code(process_code, project_code=...)` | 工序编码、项目作用域 | `ProcessDefinitionRead` |
| `list(filters, page_request, sort_by, sort_order)` | `ProcessDefinitionFilter` 等 | `PageResult[ProcessDefinitionSummary]` |
| `update(process_definition_id, data, project_code=...)` | ID、`ProcessDefinitionUpdate`、当前项目作用域 | `ProcessDefinitionRead` |
| `set_active(process_definition_id, is_active=..., project_code=...)` | ID、启停值、项目作用域 | `ProcessDefinitionRead` |

工序可以是平台通用工序，也可以通过可空 `project_code` 归属于具体项目。`include_global=True` 可以在查询项目工序时同时包含通用工序。该 Service 只管理工序基础资料，不实现工序流转、状态机或生产任务编排。

### 8.7 用户 `database_services.users`

| 方法 | 输入 | 返回 |
| --- | --- | --- |
| `create(data)` | `UserCreate`，其中密码只能是散列值 | `UserRead` |
| `get(user_id)` | 用户 ID | `UserRead` |
| `get_auth_record(username)` | 用户名 | `UserAuthRecord` |
| `list(filters, page_request, sort_by, sort_order)` | `UserFilter` 等 | `PageResult[UserRead]` |
| `update(user_id, data)` | ID、`UserUpdate` | `UserRead` |
| `set_active(user_id, is_active=...)` | ID、启停值 | `UserRead` |
| `update_password_hash(user_id, data)` | ID、`PasswordHashUpdate` | `None` |

普通用户 DTO 永远不包含密码散列。`UserAuthRecord` 只供 B 的登录校验流程使用，不应作为普通 HTTP 响应返回。

### 8.8 角色与权限 `database_services.access_control`

角色和权限目录：

| 方法 | 说明 |
| --- | --- |
| `create_role`、`get_role`、`list_roles`、`update_role`、`set_role_active` | 角色资料管理 |
| `create_permission`、`get_permission`、`list_permission_catalog`、`update_permission`、`set_permission_active` | 权限代码目录管理 |
| `assign_permission`、`revoke_permission`、`list_permissions` | 为角色授权、撤权和查询角色权限 |

系统角色和项目成员：

| 方法 | 说明 |
| --- | --- |
| `assign_system_role`、`revoke_system_role`、`list_system_role_codes` | 用户系统级角色管理 |
| `add_project_member`、`list_project_members`、`set_project_member_active` | 项目成员管理 |
| `assign_project_role`、`revoke_project_role` | 项目成员角色管理 |
| `get_effective_permissions` | 合并用户启用的系统角色权限和指定项目内的启用角色权限 |

角色分为 `SYSTEM` 和 `PROJECT` 两种范围。A 会拒绝把项目角色分配为系统角色，也会拒绝把系统角色分配给项目成员。分配和撤销操作均为幂等操作。停用成员仍允许撤销已有项目角色；撤销后的角色不会在成员重新启用时恢复。停用角色、权限或项目成员后，有效权限查询会自动排除对应权限。

## 9. 梁状态契约

梁状态从 `backend_db.schemas.BeamStatus` 导入。当前 14 个稳定编码为：

```text
UNPRODUCED
REBAR_BINDING
REBAR_CHECK
FORMWORK_CHECK
CONCRETE_CASTING
CURING
TENSION_GROUTING
QUALITY_ACCEPTED
STORED
READY_TO_SHIP
TRANSPORTING
ARRIVED
ERECTING
COMPLETED
```

B 保存、传输和判断时必须使用英文编码，中文标签只用于显示。状态集合后续可能新增或废弃，B 不应使用数组下标、固定数量或数据库枚举定义来判断状态。

当前 A 只校验状态是否属于已知编码，不执行状态机顺序校验，也不记录状态变更历史；相关业务规则需要双方后续确认后扩展 A 的数据契约。

## 10. 异常契约

B 应捕获 `BackendDBError` 及其子类，并在 B 层转换为 HTTP 或消息协议响应。异常对象的 `code` 是稳定机器码，异常文本用于日志和调试，不建议直接作为长期稳定的前端判断条件。

| 异常 | `code` | 含义 |
| --- | --- | --- |
| `ResourceNotFoundError` | `resource_not_found` | 资源不存在的公共父类 |
| `BeamNotFoundError` | `beam_not_found` | 梁不存在 |
| `BeamTypeNotFoundError` | `beam_type_not_found` | 梁型不存在 |
| `BeamPositionNotFoundError` | `beam_position_not_found` | 梁位不存在 |
| `YardAreaNotFoundError` | `yard_area_not_found` | 区域不存在 |
| `ProjectNotFoundError` | `project_not_found` | 项目不存在 |
| `UserNotFoundError` | `user_not_found` | 用户不存在 |
| `UserCredentialNotFoundError` | `user_credential_not_found` | 用户认证凭据不存在 |
| `RoleNotFoundError` | `role_not_found` | 角色不存在 |
| `PermissionNotFoundError` | `permission_not_found` | 权限不存在 |
| `ProcessDefinitionNotFoundError` | `process_definition_not_found` | 工序定义不存在 |
| `ResourceConflictError` | `resource_conflict` | 资源状态冲突的公共父类 |
| `ResourceAlreadyExistsError` | `resource_already_exists` | 唯一编码已存在 |
| `PositionOccupiedError` | `position_occupied` | 目标梁位被占用 |
| `BeamAlreadyPositionedError` | `beam_already_positioned` | 梁已有梁位却调用首次分配 |
| `InvalidAreaHierarchyError` | `invalid_area_hierarchy` | 区域层级不合法 |
| `InvalidDataError` | `invalid_data` | 数据不满足规则的公共父类 |
| `InvalidBeamStatusError` | `invalid_beam_status` | 梁状态不合法 |
| `InactiveResourceError` | `inactive_resource` | 引用的区域、梁位或梁型未启用 |
| `DatabaseUnavailableError` | `database_unavailable` | 数据库访问失败 |

DTO 构造阶段还可能抛出 Pydantic 的 `ValidationError`。该错误属于 B 接收和转换输入时需要处理的参数校验错误。

建议 B 按异常类别映射，而不是依赖中文文本：

- `ResourceNotFoundError`：资源不存在；
- `ResourceConflictError`：资源冲突；
- `InvalidDataError`、`ValidationError`：请求参数或业务数据无效；
- `DatabaseUnavailableError`：数据库暂时不可用；
- 其他 `BackendDBError`：数据库模块未分类错误。

具体 HTTP 状态码和响应体属于 B 的职责，本契约不作实现限定。

## 11. B 开发时可以先做的工作

B 现在可以基于本契约开发：

- FastAPI 应用结构、路由和依赖组织；
- 梁型、区域、梁位、梁的 HTTP 接口；
- DTO 到 HTTP 请求/响应的适配；
- A 模块异常到 HTTP 错误的转换；
- 对本契约 Protocol 的 Mock 测试；
- Redis、MQTT、WebSocket 等 B 自身基础设施。

B 可以基于 V2 契约继续开发登录、用户管理、角色权限管理和项目成员管理的 HTTP 层。B 负责密码散列算法、登录验证流程、JWT/会话、岗位到页面或接口的授权适配以及 HTTP 错误映射。

B 不应假设当前已经具备以下数据能力：工序流转与任务编排、二维码/RFID 独立身份、工单、质量记录、状态历史、运输记录、设备、告警、审计事件和增量同步。这些能力需要业务口径确认后再扩展 A 的模型与契约。

## 12. 联调与版本规则

每次 A 向 B 交付至少附带：

- 数据契约版本；
- Git 分支和完整提交号；
- Alembic 迁移版本；
- 变更说明；
- 自动测试结果；
- 是否存在需要 B 配合修改的不兼容项。

版本约定：

- 修复内部问题且公开契约不变：补丁版本；
- 新增兼容字段、状态或方法：次版本；
- 删除、重命名或改变现有输入输出语义：主版本。

状态新增虽然通常属于兼容扩展，B 仍应通过契约变更说明确认显示文案和业务处理。未经版本说明，B 不应直接追踪 A 的未完成工作区代码。
