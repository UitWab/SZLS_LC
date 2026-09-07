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

V1 梁场基础域已经冻结；V2 项目与权限基础域已经完成开发，等待审查与版本冻结。

核心实体：

-   project（V2）
-   app_user、user_credential（V2）
-   auth_role、auth_permission（V2）
-   auth_role_permission、auth_user_role（V2）
-   project_member、project_member_role（V2）
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

### 数据库迁移

Alembic 已配置。

当前开发数据库版本：

e5c1a7b3d902

检查：

alembic current

应显示：

e5c1a7b3d902 (head)

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

V2 候选交付版本为 `2.0.0`。冻结的 V1 基线为 Git 标签
`backend-db-v1.0.0`，其数据契约版本保持 `1.0.0`。

下一阶段可根据实际业务需要增加生命周期历史、增量同步和运行期审计事件。

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
