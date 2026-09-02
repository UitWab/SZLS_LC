### 仓库整体目录结构

smart-beam-twin/

├─ docs/                     #公共文档目录，所有人都可修改

│   ├─接口文档

│   ├─数据库数据字典

│   ├─项目计划、bug记录

│

├─ backend\_db/               #A的工作目录（数据库层）

│   ├─建表SQL脚本

│   ├─SQLAlchemy ORM模型

│   └─基础CRUD封装代码

│

├─ backend\_middleware/       #B的工作目录（中介中间件）

│   └─FastAPI中介全部业务代码，调用backend\_db的CRUD模块

│

├─ simulator/                #B维护，PLC传感器模拟上报脚本

│

└─ ue5\_project/              #C的工作目录（UE5工程、蓝图）

&#x20;   ├─ \*.uproject

&#x20;   ├─ Config/

&#x20;   ├─ Plugins/

&#x20;   ├─ Content/（蓝图uasset、关卡umap、小贴图，由GitLFS管理）

&#x20;   ├─ .gitignore

&#x20;   └─ .gitattributes

###### 重要说明：大型 FBX 模型、高分辨率贴图不提交 GitHub，单独网盘分发；Binaries、Intermediate、DerivedDataCache、Saved 缓存文件全部被 gitignore 过滤不上传。

#### 2.3分支规则

Main：稳定主分支，禁止直接 push，全部通过 PR 合并进来

Dev-db：A 的开发分支，只修改backend\_db、docs 内数据字典

Dev-middleware：B 的开发分支，只修改backend\_middleware、simulator、docs 接口文档

Dev-ue5：C 的开发分支，只修改ue5\_project下工程蓝图、配置

#### 2.4每个人在仓库要做的事情

A（Dev-db 分支，数据库）

1.在backend\_db完成：建表脚本、ORM 模型、基础 CRUD 封装。

2.修改数据表 / ORM 时同步更新docs下的数据字典。

3.写完提交推送dev\_db，发起 PR；B 确认后合并入 main。

4.不写中介业务代码，不碰 ue5\_project。

B（Dev-middleware 分支，中介中间件）

1.在backend\_middleware写 FastAPI 中介代码，直接导入调用 A 写好的backend\_db的 CRUD 模块。

2.维护simulator下 PLC 模拟脚本；更新docs中的接口文档、JSON 报文、枚举。

1.提交推送dev\_middleware，发起 PR，A/C 核对后合并 main。

2.不修改数据库底层模型，不碰 ue5\_project。

C（Dev-ue5 分支，UE5 蓝图）

1.在ue5\_project内做全部UE5开发：蓝图、UI、关卡、像素流适配。

2.提交前关闭 UE5 编辑器，蓝图、关卡文件走 Git\_LFS 上传仓库。

3.严格按照B提供的接口文档编写蓝图通信逻辑。

4.提交推送devue5，发起 PR，A/B 确认后合并 main。

5.大模型资源不上 git，走网盘。

6.A、B 不需要打开、运行 UE5 工程。

#### 2.5协作硬性约定

1.任何人不直接向 main 分支提交代码，全部走 PR 合并。

2.A 改动表/ORM，B改动接口，都要同步更新docs文档，并通知另外两方。

3.禁止把账号密码、密钥提交进仓库，敏感配置放本地文件并加入忽略。

4.每个人定期拉取 main 最新代码，再继续自己分支开发，减少版本差距。

## 2.6后续扩展

后续第四人D开发手机/电脑管理端，只新增dev\_app分支，只调用B的中介接口，不改动A数据库、不改动C的UE5工程。

