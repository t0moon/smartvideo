 # SmartVideo —— 企业级 AI 视频生产平台

 SmartVideo 是一个面向企业的 AI 视频生产平台，通过 AI Agent 驱动视频创作全流程，并嵌入人工审核节点（Human in the Loop）保证内容质量。平台支持从需求理解、分镜生成、资产准备、场景生成、视频合成到审核发布的完整闭环，同时沉淀企业创意资产供后续复用。

 ## 核心流程

 ```
 需求理解 → 分镜生成 → 资产准备 → 场景生成 → 视频合成 → 人工审核 → 发布 → 资产沉淀
    │                      │                        │                  │
    └─ 人工确认 ───────────┘                        └─ 人工审核 ───────┘
 ```

 系统在 **需求确认**、**分镜确认**、**资产确认**、**视频审核** 四个关键节点支持人工审批（Web + 飞书/企业微信/Slack），审批通过后流程自动恢复执行。

 ## 演示 Demo

> 以下为 SmartVideo 端到端产出示例：输入「15 秒京阿尼风格瑞幸生椰拿铁广告」，经需求理解 → 分镜 → 资产准备 → 场景生成（MiniMax H3）→ 合成配音（SiliconFlow CosyVoice2 温柔女声 `claire`）→ 字幕烧录，最终成片。

![SmartVideo 演示](samples/demo.gif)

*GIF 为静音预览，点击下载带语音完整版：* [🎬 final_with_audio.mp4](samples/final_with_audio.mp4)

- 视频原生配乐（MiniMax H3 生成）与女声配音已**混音**共存，而非相互替换
- 字幕由系统自动生成并烧录进画面
- 完整工程产物位于 `backend/data/projects/`（运行时生成，未纳入版本库）

 ## 产品设计思路

#### 行业现状：通用视频生成 ≠ 广告视频生产

市面上绝大多数"广告素材生成"产品，本质仍是**通用视频生成工具**——它们把"能生成一段视频"当作终点。但品牌广告真正需要的，是从需求理解、分镜、资产准备、场景生成、合成到审核发布的一条完整流水线。现有产品普遍只覆盖流水线的某一个环节，并集中暴露出六大共性痛点。

#### 竞品格局：两类玩家，都没能解决完整痛点

| 类别 | 代表产品 | 强项 | 结构性短板 |
|---|---|---|---|
| **模型厂商自带产品** | 即梦（字节）、可灵（快手）、通义万相（阿里）| 模型能力强、生成质量高 | 为卖自家算力而生，流程 / 资产 / 合规 / 跨模型能力弱，且深度绑定自家模型 |
| **稍自由的创作产品** | MiniMax Design 等 | 自由度略高、支持一定自定义 | 仍未解决资产沉淀、广告法审核、Skills 融入 Agent、多端创作等生产侧问题 |

> 此外还有剪映这类剪辑工具（模板化批量生产）与智谱清影 / 混元这类 To C 生成模型，但它们要么 AI 生成依赖第三方、要么无企业协作场景，同样只满足单一环节。

这些产品的共同结论是：**能生成视频，不能生产视频**。

#### 六大未被满足的痛点

1. **价格过贵**：锁定单一高价模型，按生成次数高价计费，重复生成零复用。
2. **无中间产物沉淀**：只交付成片，图片资产、视觉分镜等中间产物随会话消失，无法复用。
3. **缺广告法审核**：无合规校验，违规风险靠人工事后发现，品牌合规风险高。
4. **模型锁定不灵活**：绑定自家模型，想换模型就得换工具。
5. **仅限电脑创作**：只能在 Web / 桌面端操作，离开电脑流程就停摆。
6. **Skills 无法融入 Agent**：业务 know-how 写死在提示词里，无法沉淀为 Agent 可复用的技能。

#### 为什么大多数产品只满足一两个痛点？

模型厂商的目标是**消耗自家算力、卖 token**；剪辑 / 工具厂商的目标是**卖编辑功能**。没有任何一方有动机去建设"流程 + 资产 + 合规 + 多模型 + 多端 + Agent 技能"这套完整基础设施——因为它既不直接卖算力、也不直接卖编辑。这正是 SmartVideo 瞄准的定位空白。

#### SmartVideo 的解法：唯一覆盖全部六大痛点的生产管线

不是更好的视频生成工具，而是 **AI Agent 驱动、可插拔、可沉淀、可合规的品牌视频生产管线**。

| 行业痛点 | 通用视频生成产品的现状 | SmartVideo 的解法 |
|---|---|---|
| 价格过贵 | 锁定单一高价模型，按次高价计费 | Provider 插座化，视频 / LLM / TTS 可插拔，按场景选性价比模型；资产复用摊薄单次成本 |
| 无中间产物沉淀 | 只输出成片，图片资产 / 视觉分镜随会话消失 | 图片资产、视觉分镜、配音、品牌设定全部自动归档，新项目一键复用 |
| 缺广告法审核 | 无合规校验，违规靠人工发现 | 内置广告法合规校验节点（guardrails），生成前 / 后双重把关 |
| 模型锁定不灵活 | 绑定自家模型，换模型要换工具 | 供应商可插拔，改配置即切换，不绑定任何一家 |
| 仅限电脑创作 | 只能在 Web / 桌面端操作 | 飞书内对话式创建 + 审批，移动端也能推进全流程 |
| Skills 无法融入 Agent | 能力写死，业务知识无法复用 | Skill 体系接入 LeadAgent，行业 know-how 沉淀为可调用 skill |

#### 差异化定位一览

| 维度 | 即梦 / 可灵 | SmartVideo |
|---|---|---|
| 交互方式 | 画布 / Prompt 工具式操作 | 输入一句话，Agent 自动编排全流程 |
| 流程管控 | 无，全靠人工手动衔接 | 7 阶段管线，YAML 可配置 |
| 审核节点 | 无，出片后线下审 | 4 道 HITL + 广告法合规校验 |
| 资产沉淀 | 无，每次从零开始 | 品牌 / 人物 / 分镜 / 配音 / 图片资产自动归档复用 |
| 办公入口 | Web 端 | 飞书内创建 + 审批，移动端可推进 |
| 供应商切换 | 锁定单一模型 | 视频 / LLM / TTS 可插拔，改配置一键切换 |
| Agent 技能 | 无 | Skill 体系接入 LeadAgent，业务知识可复用 |

#### 目标用户

- **品牌市场部**：一周 3-5 条产品广告，需要快速出片 + 品牌一致性
- **新媒体运营**：日更短视频，需要可复用的分镜模板和配音资产
- **AI 视频代理商 / MCN**：多客户并行，需要项目隔离和资产归属管理

#### 完整用户旅程

在飞书输入 15秒京阿尼风格瑞幸咖啡视频，主打生椰拿铁，抖音竖屏

[AI 自动理解需求] 解析出长度/风格/品牌/平台/目标人群/卖点
 飞书推送：需求分析完成，请确认 回复 批准

[AI 自动生成分镜] 3 场景 x 6 镜头，含运镜/音效/旁白
 飞书推送：分镜脚本如下，请确认 回复 批准

[AI 自动准备素材] 角色设定/配音风格/品牌色/参考图
 飞书推送：素材建议如下，请确认 回复 批准

[AI 生成全部视频 clip] MiniMax/Kling 批量生成

[自动拼接 + 配音 + 字幕 + BGM] 渲染成品
 飞书推送：视频已生成，请审核 回复 批准

[发布] MP4 输出，品牌资产自动归档入库

全程用户操作：输入一句话 + 在飞书回复 4 次批准，不需要打开任何其他工具。

## 项目关键迭代

#### 1. 多 Agent 到单一 Lead Agent

**一开始**：每个阶段配独立 AI 角色——需求分析师、分镜师、素材师、剪辑师，各有一套 prompt 和工具。

**踩的坑**：七个 Agent 读同一份项目信息，理解出来的还不完全一样。新增 Agent 要写全套 prompt 模板、工具注册、状态传递，维护成本高。

**现在的做法**：只保留一个 LeadAgent 作为核心大脑。不区分 我是分镜师还是剪辑师——只有一个身份：我是这个视频项目的导演。遇到需求分析阶段加载需求分析的技能包，遇到分镜阶段换分镜的技能包。

```
一个 LeadAgent
    requirement  加载 skill: [requirement]     + prompt: requirement.txt
    storyboard   加载 skill: [storyboard]      + prompt: storyboard.txt
    asset_prep   加载 skill: [asset, world]    + prompt: asset.txt
    scene_gen    加载 skill: [scene]           + prompt: scene.txt
    video_gen    调用 provider.generate_clip()
```

项目状态统一存在 WorkflowState 里，不存在 Agent 之间传话丢信息的问题。

#### 2. Provider 插座化

**一开始**：代码里硬编码调用 Kling API，generate_clip() 直接写死在视频生成逻辑里。

**踩的坑**：Kling 端点不稳定想换 MiniMax——要改 5 个文件，改完不确定有没有漏。三方供应商接口格式千差万别。

**现在的做法**：所有视频供应商遵守同一个三段式接口：

```
BaseVideoProvider:
  generate_clip(prompt, **kwargs) -> task_id    # 提交任务
  poll_status(task_id) -> status                 # 轮询状态
  download_result(task_id, path) -> file         # 下载结果
```

不管是 Kling、MiniMax 还是将来的 Sora、Runway，都实现这三个方法。换供应商只需改 .env 一行：

```
VIDEO_PROVIDER=minimax   # 切到 MiniMax
VIDEO_PROVIDER=kling     # 切回 Kling
```

新增供应商工作量：写 200 行适配文件 + 工厂函数里注册一行。LLM/TTS/发布层都是同样的抽象设计。

#### 3. 对话状态机（项目会话管理）

**一开始**：系统生成分镜后给飞书发审批卡片，用户点击卡片跳转 Web 点通过刷新等结果。

**踩的坑**：操作路径长；飞书卡片手机端排版烂，企微不支持卡片；最致命——同时跑 3 个项目，回复一句 批准 系统不知道批准哪个。

**现在的做法**：抛弃卡片，改用纯文本对话状态机。

```
用户说 批准 -> parse_intent 识别为 approve 指令
          -> 查状态表：用户 A 当前待审项目 X 的 storyboard
          -> WorkflowRuntime.resume(project_X) 管线继续执行
          -> release 状态，队列中下一个待审项目出队
```

核心机制：
- **状态绑定**：每个用户同一时刻只绑定一个待审批节点
- **意图解析**：识别 批准/驳回/驳回+修改意见 三种指令
- **多项目排队**：已有待审项目时新审批自动入队
- **超时提醒**：30 分钟无响应自动重推送，最多 3 次后过期

用户全程只在飞书聊天框打几个字，不用跳转到任何其他地方。

系统架构

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
