 # SmartVideo —— 企业级 AI 视频生产平台

 SmartVideo 是一个面向企业的 AI 视频生产平台，通过 AI Agent 驱动视频创作全流程，并嵌入人工审核节点（Human in the Loop）保证内容质量。平台支持从需求理解、分镜生成、资产准备、场景生成、视频合成到审核发布的完整闭环，同时沉淀企业创意资产供后续复用。

 ## 核心流程

 ```
 需求理解 → 分镜生成 → 资产准备 → 场景生成 → 视频合成 → 人工审核 → 发布 → 资产沉淀
    │                      │                        │                  │
    └─ 人工确认 ───────────┘                        └─ 人工审核 ───────┘
 ```

 系统在 **需求确认**、**分镜确认**、**资产确认**、**视频审核** 四个关键节点支持人工审批（Web + 飞书/企业微信/Slack），审批通过后流程自动恢复执行。

 ## 系统架构

 ```
          HTTP / WebSocket / IM
                    │
                    ▼
              API Gateway
                    │
                    ▼
           Workflow Config（YAML 定义）
                    │
                    ▼
           Workflow Runtime（执行器 + 调度器 + 状态机）
                    │
                    ▼
           Middleware 链（tracing / guardrails / approval / audit / retry）
                    │
                    ▼
              Context Builder
               ▲          ▲
               │          │
           Workspace    Asset Library
               │
               ▼
           Lead Agent → Skill Chain → Subagents（并行）
               │
               ▼
          Model Router → Tools → Providers（LLM / 视频 / TTS / 图片）
               │
               ▼
          Pipeline Hooks（保存工作区 / 沉淀资产 / 发布事件 / 链路追踪 / 暂停审批）
 ```

 ## 项目结构

 ```
 smartvideo-main/
 ├── backend/                      # 后端服务（Python / FastAPI）
 │   ├── app/                      # FastAPI 应用入口
 │   │   ├── main.py               # 应用启动、生命周期管理
 │   │   ├── config.py             # 全局配置
 │   │   ├── dependency.py         # 依赖注入
 │   │   ├── api/                  # REST API 端点
 │   │   │   ├── project.py        # 项目管理
 │   │   │   ├── workspace.py      # 工作区管理
 │   │   │   ├── review.py         # 审核管理
 │   │   │   ├── asset.py          # 资产管理
 │   │   │   └── webhook.py        # Webhook 回调
 │   │   └── websocket/            # WebSocket 实时推送
 │   │
 │   ├── workflows/                # 工作流定义（YAML）
 │   │   ├── product_ad_v1.yaml    # 产品广告
 │   │   ├── douyin_short_v1.yaml  # 抖音短视频
 │   │   └── digital_human_v1.yaml # 数字人口播
 │   │
 │   ├── runtime/                  # 工作流运行时
 │   │   ├── executor.py           # 节点执行器
 │   │   ├── scheduler.py          # 调度器
 │   │   ├── planner.py            # 动态规划器
 │   │   ├── state_machine.py      # 状态机
 │   │   ├── checkpoint.py         # 检查点（pause/resume）
 │   │   └── workflow_engine.py    # 工作流解释引擎
 │   │
 │   ├── agents/                   # AI Agent 系统
 │   │   ├── lead_agent.py         # 通用决策 Agent（按阶段装配不同 skill）
 │   │   └── prompts/              # 各阶段 System Prompt
 │   │
 │   ├── skills/                   # 可复用业务能力
 │   │   ├── storyboard_template/  # 分镜模板
 │   │   └── world_constraints/    # 世界观约束
 │   │
 │   ├── subagents/                # 子代理系统（并行场景生成）
 │   ├── middleware/               # 中间件链
 │   │   ├── base.py               # AgentMiddleware 抽象基类
 │   │   ├── registry.py           # 链装配
 │   │   ├── tracing.py            # 链路追踪
 │   │   ├── tool_guard.py         # 工具调用安全守卫
 │   │   ├── approval.py           # Human in the Loop 审批
 │   │   ├── audit.py              # 操作审计
 │   │   ├── retry.py              # 自动重试
 │   │   ├── cache.py              # 结果缓存
 │   │   └── model_router.py       # 模型路由选择
 │   │
 │   ├── guardrails/               # 合规检查
 │   │   ├── ad_law.py             # 广告法合规（禁用词、绝对化用语）
 │   │   ├── brand_taboo.py        # 品牌禁忌检查
 │   │   └── content_safety.py     # 内容安全（暴力/色情/政治敏感）
 │   │
 │   ├── context/                  # Context Center
 │   │   └── providers/            # workspace / asset / review / project 数据提供者
 │   │
 │   ├── workspace/                # 当前项目工作区
 │   │   ├── manager.py            # 文件系统级工作区管理
 │   │   ├── snapshot.py           # 快照
 │   │   └── artifacts.py          # 产出物管理
 │   │
 │   ├── assets/                   # 长期资产中心
 │   │   ├── brand/                # 品牌资产
 │   │   ├── character/            # 人物资产
 │   │   ├── prompt/               # 创意资产
 │   │   ├── media/                # 媒体资产
 │   │   ├── subtitle/             # 字幕资产
 │   │   └── voice/                # 语音资产
 │   │
 │   ├── review/                   # Human in the Loop 审核
 │   │   ├── service.py            # 审核服务
 │   │   ├── queue.py              # 审核队列
 │   │   ├── comment.py            # 批注
 │   │   ├── history.py            # 历史记录
 │   │   └── approval.py           # 审批操作
 │   │
 │   ├── project/                  # 项目生命周期
 │   │   ├── service.py            # 项目服务
 │   │   ├── repository.py         # 数据访问
 │   │   ├── models.py             # 数据模型
 │   │   └── stages.py             # 阶段管理
 │   │
 │   ├── tools/                    # 领域工具
 │   │   ├── ffmpeg/               # 视频剪辑（拼接、转场、渲染）
 │   │   ├── tts/                  # 语音合成
 │   │   ├── subtitle/             # 字幕生成
 │   │   ├── video/                # 视频生成
 │   │   ├── publish/              # 多平台发布（TikTok / YouTube / 小红书）
 │   │   └── storage/              # 存储工具
 │   │
 │   ├── providers/                # 第三方服务适配
 │   │   ├── llm/                  # 大语言模型（OpenAI 兼容）
 │   │   ├── video/                # 视频生成（placeholder / OpenAI Sora / Kling）
 │   │   ├── image/                # 图片生成
 │   │   ├── tts/                  # 语音合成
 │   │   └── storage/              # 对象存储
 │   │
 │   ├── channels/                 # IM 渠道适配
 │   │   ├── feishu/               # 飞书（WebSocket + Webhook 双模式）
 │   │   ├── wecom/                # 企业微信
 │   │   ├── slack/                # Slack
 │   │   └── webhook/              # 通用 Webhook
 │   │
 │   ├── events/                   # 事件总线
 │   ├── observability/            # 可观测性（tracing / metrics / logging / Langfuse 导出）
 │   ├── storage/                  # 数据持久化（SQLite / MySQL / Redis / 向量数据库）
 │   ├── shared/                   # 公共模块（枚举、Schema、常量、异常、工具函数）
 │   └── tests/                    # 测试（unit / integration / e2e）
 │
 ├── frontend/                     # 前端（React 19 + TypeScript + Vite）
 │   ├── src/
 │   │   ├── main.tsx              # 应用入口
 │   │   ├── App.tsx               # 路由配置
 │   │   ├── api.ts                # API 调用封装
 │   │   ├── pages/
 │   │   │   ├── ProjectList.tsx    # 项目列表页
 │   │   │   ├── ProjectDetail.tsx  # 项目详情页（进度 + 审核 + 结果查看）
 │   │   │   └── Assets.tsx         # 资产库页
 │   │   └── components/
 │   │       └── ReviewCard.tsx     # 审核卡片组件
 │   └── package.json
 │
 ├── docker-compose.yml            # Docker 编排（backend + frontend）
 ├── DEPLOY.md                     # 部署文档
 └── prd.txt                       # 产品需求文档
 ```

 ## 核心模块说明

 ### 工作流（Workflow）

 工作流以 YAML 文件定义，描述从需求到成片的完整流水线。每个阶段通过 `agent` + `skill` 组合执行，`pause_for_review` 控制是否触发人工审批。当前提供 3 套预设工作流：

 | 工作流 | 文件 | 适用场景 |
 |--------|------|----------|
 | 产品广告 | `product_ad_v1.yaml` | 品牌产品宣传视频 |
 | 抖音短视频 | `douyin_short_v1.yaml` | 短视频平台内容 |
 | 数字人口播 | `digital_human_v1.yaml` | 数字人播报视频 |

 ### Lead Agent + Skill（智能体系统）

 采用「一个通用 Agent + 按阶段装配不同 Skill」的设计模式。Agent 根据当前工作流阶段自动加载对应的 system prompt、tools 和 skill，无需为每个阶段创建独立 Agent，大幅降低维护成本。

 ### Human in the Loop（人工审核）

 系统在 4 个关键审批节点自动暂停工作流，等待人工介入：

 1. 需求确认 —— Video Specification
 2. 分镜确认 —— Storyboard
 3. 资产确认 —— 数字人 / 声音 / 首尾帧
 4. 视频审核 —— 最终成片

 审批操作支持 approve / reject / comment / partial revision，同时适配 Web 端和飞书/企业微信/Slack 通知推送。

 ### 资产沉淀（Asset Library）

 每个项目结束后自动将以下资产归档至资产库，后续项目可直接复用，避免重复构建：

 - **品牌资产**：logo、tone、品牌 prompt
 - **人物资产**：数字人形象、声音
 - **创意资产**：分镜模板、场景 prompt、运镜风格
 - **媒体资产**：生成的图片、视频片段、字幕

 ### 合规检查（Guardrails）

 Agent 输出后自动进行三层合规检查：广告法禁用词检测、品牌禁忌匹配、内容安全审查，确保产出符合企业规范。

 ## 快速开始

 ### 环境要求

 - Python >= 3.11
 - Node.js >= 20
 - pnpm >= 8
 - FFmpeg（视频渲染，可选；placeholder 模式下不需要）
 - OpenAI API Key

 ### Docker 部署（推荐）

 ```bash
 # 1. 配置环境变量
 cp backend/.env.example backend/.env
 # 编辑 backend/.env，填入 OPENAI_API_KEY 等必填项

 # 2. 构建并启动所有服务
 docker-compose build
 docker-compose up -d

 # 3. 验证后端健康状态
 curl http://localhost:8765/api/v1/health
 # → {"status":"ok","version":"0.3.0"}

 # 前端访问
 # 浏览器打开 http://localhost
 ```

 ### 本地开发

 后端：

 ```bash
 cd backend
 python -m venv .venv
 .venv\Scripts\activate              # Windows
 # source .venv/bin/activate         # macOS / Linux
 pip install -e ".[all]"
 cp .env.example .env                # 编辑填入 API Key
 uvicorn app.main:app --reload --port 8765
 ```

 前端：

 ```bash
 cd frontend
 pnpm install
 pnpm dev                             # 开发服务器，API 自动代理到 localhost:8765
 ```

 ### CLI 使用

 ```bash
# 从命令行创建视频项目
 smartvideo run "30秒 Apple 产品广告" --name "新品发布"

 # 查看所有项目
 smartvideo project list

 # 查看项目详情
 smartvideo project get <project_id>
 ```

 ## 配置说明

 在 `backend/.env` 中配置以下环境变量：

 | 变量 | 默认值 | 说明 |
 |------|--------|------|
 | `OPENAI_API_KEY` | — | **必填**，OpenAI API 密钥 |
 | `OPENAI_BASE_URL` | — | OpenAI 兼容 API 地址（可选） |
 | `OPENAI_MODEL` | gpt-4o-mini | LLM 模型名称 |
 | `VIDEO_PROVIDER` | placeholder | 视频生成服务：`placeholder`（模拟）/ `openai_videos` / `kling` |
 | `VIDEO_API_BASE_URL` | — | 视频生成 API 地址 |
 | `AUDIO_ENABLE` | 1 | 是否启用音频处理（TTS + 背景音乐） |

 ## API 端点

 | 方法 | 路径 | 说明 |
 |------|------|------|
 | GET | `/api/v1/health` | 健康检查 |
 | GET | `/api/v1/projects/` | 获取项目列表 |
 | POST | `/api/v1/projects/` | 创建新项目 |
 | GET | `/api/v1/projects/{id}` | 获取项目详情 |
 | PATCH | `/api/v1/projects/{id}` | 更新项目信息 |
 | DELETE | `/api/v1/projects/{id}` | 删除项目 |
 | POST | `/api/v1/workspace/run/{id}` | 触发工作流执行 |
 | GET | `/api/v1/reviews/` | 获取审核列表 |
 | POST | `/api/v1/reviews/{id}/approve` | 批准审核 |
 | POST | `/api/v1/reviews/{id}/reject` | 驳回审核 |
 | GET | `/api/v1/assets/` | 获取资产列表 |
 | GET | `/api/v1/assets/search?q=` | 搜索资产 |
 | POST | `/api/v1/publish/{id}` | 发布视频到平台 |
 | WS | `/api/v1/ws/{project_id}` | WebSocket 实时状态推送 |

 ## 开发路线

 项目按 6 个阶段分步推进，当前处于 **Phase 1（核心引擎 MVP）**：

 - **Phase 1** —— 核心引擎：从 brief 到成片闭环，CLI 可运行
 - **Phase 2** —— Web 平台：浏览器中创建项目、填写需求、查看进度
 - **Phase 3** —— Human in the Loop：Web 端审批界面，工作流暂停/恢复
 - **Phase 4** —— 资产库：资产沉淀与复用，YAML 可配置工作流
 - **Phase 5** —— IM 集成：飞书/企微审批，合规检查，可观测性
 - **Phase 6** —— 多平台发布：TikTok/YouTube/小红书分发，E2E 测试

 ## 运行测试

 ```bash
 cd backend
 pip install -e ".[dev]"
 pytest
 ```

 ## 技术栈

 | 层 | 技术 |
 |----|------|
 | 后端框架 | Python 3.11+ / FastAPI / Uvicorn |
 | 数据存储 | SQLAlchemy / SQLite（可切换 MySQL） |
 | 实时通信 | WebSocket |
 | 前端 | React 19 / TypeScript / Vite 6 / React Router 7 |
 | AI | OpenAI API（LLM + 视频生成） |
 | 可观测性 | Langfuse |
 | 部署 | Docker / Docker Compose |
