# Smart Beam Twin - Database Module

## 1. 项目简介

本模块是智慧梁场数字孪生平台的数据底座模块。

负责： - 梁场基础数据管理 - 梁体生命周期数据存储 -
为后端中间件和数字孪生可视化模块提供数据库访问能力

当前负责人： A - Database Module

## 2. 技术栈

-   Python 3.11
-   MySQL 8.0
-   SQLAlchemy 2.x
-   Pydantic 2.x
-   Alembic
-   Pytest

整体架构：

Python Application \| SQLAlchemy ORM \| Alembic Migration \| MySQL
Database

## 3. 当前目录结构

01.backend_db/

-   backend_db/
    -   config.py
    -   database/
    -   models/
    -   schemas/
    -   crud/
    -   services/
    -   interfaces/
    -   mappers/
    -   tests/
    -   migrations/
-   alembic.ini
-   requirements.txt
-   pyproject.toml
-   docs/
-   .env.example
-   README.md

注意： backend_db 是 Python package，禁止修改名称。

## 4. 数据库设计状态

V1 梁场基础域、V2 项目与权限基础域、V3 操作审计日志、V4 梁位工单，以及 V5 梁生命周期事件、V6 梁工序执行记录和 V7 质量检查记录能力均已本地冻结。V7 冻结标签为 `backend-db-v7.0.0`，尚未推送。

核心实体：

-   project（V2）
-   app_user、user_credential（V2）
-   auth_role、auth_permission（V2）
-   auth_role_permission、auth_user_role（V2）
-   project_member、project_member_role（V2）
-   operation_audit_log（V3）
-   beam_position_work_order（V4）
-   beam_lifecycle_event（V5）
-   beam_process_execution（V6）
-   beam_quality_inspection、beam_quality_inspection_item（V7）
-   yard_area
-   beam_position
-   beam_type
-   beam

关系：

yard_area -\> beam_position

beam_type -\> beam

## 5. 已完成内容

### ORM模型

已完成：

-   Base模型
-   公共字段Mixin
-   梁场区域模型
-   梁位模型
-   梁型模型
-   梁实体模型
-   梁位工单模型
-   梁生命周期事件模型
-   梁工序执行记录模型
-   梁质量检查记录及检查项模型

### 数据库迁移

Alembic 已配置。

当前开发数据库版本：

e7b9c1d3f605

检查：

alembic current

应显示：

e7b9c1d3f605 (head)

### 自动测试

包含：

-   数据库连接测试
-   数据结构测试
-   数据约束测试
-   DTO与接口契约测试
-   CRUD与事务测试
-   Service业务规则测试
-   梁位并发占用测试

测试默认连接 `smart_beam_twin_test`，测试库名称必须以 `_test` 结尾。

运行：

pytest -v

## 6. 开发规范

数据库修改禁止直接修改 MySQL。

必须：

修改 ORM → 生成 Alembic migration → 检查 migration → upgrade 数据库

代码结构保持：

models \| schemas \| crud \| services \| interfaces

禁止：

-   所有代码写入一个 Python 文件
-   CRUD 中混入复杂业务逻辑
-   直接向外部模块返回 ORM 对象

## 7. 当前开发阶段

已完成：

-   数据库基础设施与Alembic迁移
-   独立测试库保护
-   Unit of Work事务边界
-   公共DTO、分页、排序和异常契约
-   梁场区域、梁型、梁位、梁的CRUD与Service
-   区域树和层级循环保护
-   梁位分配、释放、移动和并发占用保护
-   梁状态修改
-   供B模块调用的Python接口协议与组合工厂
-   V2项目档案、公开项目Service和兼容迁移
-   为梁型、区域和梁预留可空项目归属
-   梁型、区域、梁位、梁和工序的公开接口按 `project_code` 隔离；未传项目时仅访问 V1 全局数据
-   V2用户、密码凭据、角色、权限及角色权限关系的数据模型
-   普通用户DTO与登录验证用凭据DTO隔离
-   用户资料、认证记录和密码散列更新Service
-   角色、权限及角色授权/撤权Service
-   系统级用户角色与项目成员、项目角色关系
-   系统权限与项目权限合并查询Service
-   角色与权限目录的查询、更新、筛选、分页和启停Service
-   系统角色与项目角色的分配、撤销和查询Service
-   项目成员的分页查询、启用和停用Service
-   停用项目成员仍可撤销项目角色，重新启用不会恢复已撤销授权
-   通用或项目级工序基础资料的CRUD、分页筛选、排序和启停Service
-   只追加操作审计日志的写入、读取、分页筛选和稳定排序Service
-   审计记录的可空项目、可空操作用户及操作人名称快照
-   审计日志不提供更新、启停或删除接口
-   梁位入位、移位、出位工单的创建、读取、分页筛选和状态流转
-   梁位工单完成与梁当前位置变更处于同一事务
-   同一根梁最多存在一个待执行或执行中的梁位工单
-   梁位工单不提供任意更新或删除接口
-   梁创建、实际状态变化和梁位变化自动追加生命周期事件
-   梁位工单完成只追加一条关联工单的梁位变化事件
-   梁生命周期事件提供只读页码查询和按事件 ID 排序的游标增量查询
-   同一项目的事件写入按事务串行，不同项目可并行，避免并发提交导致增量游标漏读
-   生命周期事件与梁变化在同一事务提交或回滚，不提供公开写入、修改或删除接口
-   已结束梁工序执行事实的记录、读取、筛选、分页和受控作废
-   工序执行记录支持执行编码及外部来源幂等，纠错采用作废后新建
-   工序执行不校验流程顺序，不自动修改梁状态或追加生命周期事件
-   质量检查主记录和检查项原子写入、查询、筛选、分页和受控作废
-   质量记录支持复检、可选关联工序或 V6 执行记录，以及外部来源幂等
-   质量结果不触发审批、自动放行、梁状态或生命周期事件

调用入口：

```python
from backend_db.interfaces import create_database_services

services = create_database_services()
```

安装到B模块的Python环境：

```powershell
python -m pip install -e .\01.backend_db
```

完整的数据契约、公开方法、分页筛选、事务和异常说明见
[`docs/A-B接口接入说明.md`](docs/A-B接口接入说明.md)。

当前明确不提供梁删除接口。

V6 本地冻结版本为 `6.0.0`，包含 V5 梁生命周期事件和 V6 梁工序执行记录，目标迁移为 `d4a6f8b0c217`，标签为 `backend-db-v6.0.0`。V4 本地冻结版本为 `4.0.0`，目标迁移为 `a4d7e9f2c105`，标签为 `backend-db-v4.0.0`。V3 本地冻结基线为 `c5c260a`，标签为
`backend-db-v3.0.0`；V2 基线提交为 `cdd5d43`。冻结的 V1 基线为 Git 标签
`backend-db-v1.0.0`，其数据契约版本保持 `1.0.0`。

后续设备、告警、时序测点和通用数据同步仍需先确认业务口径；操作审计写入与梁位工单触发时机由 B 在业务流程中决定，A 只提供底层数据能力。V5 生命周期事件由 A 在梁变化事务中自动记录，B 只读取。

## 8. 后续目标

最终提供 Python 数据库访问包。

服务对象：

-   backend_middleware
-   simulator
-   UE5 数字孪生平台

## 9. 开发原则

1.  不随意重构已有目录。
2.  不修改 Python 包名 backend_db。
3.  所有数据库结构变化必须通过 Alembic 管理。
4.  新功能先设计讨论，再编码。
5.  保持低耦合和可维护性。
