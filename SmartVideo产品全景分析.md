# SmartVideo 产品全景分析

> 撰写视角：AI 产品经理 | 版本：v0.3.0 | 日期：2026-08-02

---

## 目录

1. [用户交互链路](#一用户交互链路)
2. [底层 Agent 架构](#二底层agent架构)
3. [产品优点](#三产品优点)
4. [关键迭代](#四关键迭代)

---

## 一、用户交互链路

SmartVideo 支持 **双入口**：飞书 IM（对话式）和 Web 平台（表单式），共享同一条后端流水线。

### 1.1 飞书 IM 链路（主力交互通道）

```
用户在飞书给机器人发消息
        │
        ▼
「生成一个 10s 的瑞幸咖啡广告」
        │
        ▼
┌── bot 创建项目 (project_id) ──────────────────────┐
│ 消息去重：message_id TTL 10分钟 / brief 5秒窗口     │
│ 回复："项目已创建，正在分析需求..."                 │
└──────────────────────────────────────────────────┘
        │
        ▼
   ╔══════════════════════════════════════════════╗
   ║          HITL #1 — Requirement              ║
   ║  bot 推送需求分析结果（自然语言）             ║
   ║  "视频时长10s | 风格极简 | 品牌瑞幸 | ..."   ║
   ║  用户回复「批准」→ 继续                      ║
   ║  用户回复「驳回 改成15秒」→ 局部重写         ║
   ╚══════════════════════════════════════════════╝
        │
        ▼
   ╔══════════════════════════════════════════════╗
   ║          HITL #2 — Storyboard               ║
   ║  bot 推送分镜脚本（可读故事板文本）          ║
   ║  "镜头1: 咖啡豆落入研磨机特写..."            ║
   ║  用户回复「批准」→ 继续                      ║
   ║  用户回复「驳回 换暖色调」→ 局部重写         ║
   ╚══════════════════════════════════════════════╝
        │
        ▼
   ╔══════════════════════════════════════════════╗
   ║          HITL #3 — Asset Prep               ║
   ║  bot 推送资产建议+已上传素材清单             ║
   ║  "建议角色: 真人男声 | 风格: 极简 | ..."     ║
   ║  用户回复「批准」→ 继续                      ║
   ╚══════════════════════════════════════════════╝
        │
        ▼
   [自动执行：Scene Generation]
   每个 shot 独立调用 Kling 2.5 Turbo 生成视频片段
        │
        ▼
   [自动执行：Video Generation]
   逐 shot 轮询 Kling 任务→下载 clip
        │
        ▼
   ╔══════════════════════════════════════════════╗
   ║          HITL #4 — Video Review             ║
   ║  bot 推送"视频片段已生成（3个片段）"         ║
   ║  用户回复「批准」→ 合成+发布                 ║
   ║  用户回复「驳回」→ 标记失败                   ║
   ╚══════════════════════════════════════════════╝
        │
        ▼
   [自动执行：Stitch 合成]
   配音(TTS) → 字幕(SRT) → BGM混音 → FFmpeg渲染 → 本地发布
        │
        ▼
   bot 推送：「项目已完成，final.mp4 已生成」
```

**关键交互特性：**
- **纯文本对话审批**（v0.3.0 改版）：不用卡片按钮，只用自然语言「批准/驳回/驳回+修改意见」，降低飞书后台配置门槛
- **ConversationRouter 状态机**：每人同一时间只能处理一个活跃审批，多余的排队等待；30 分钟无响应自动重提醒（最多 3 次）
- **驳回带反馈**：用户文字中的修改意见（"改成暖色调""加到 15 秒"）直接回流给 LLM，触发局部重写而非全盘重来

### 1.2 Web 平台链路

```
打开前端首页 → 项目列表
        │
        ▼
点击「新建项目」→ 填写名称+brief
        │
        ▼
进入项目详情 → 点击「Run Pipeline」
        │
        ▼
流水线自动执行，每个 HITL 节点在前端生成 Review Card
        │
        ▼
点击 Review Card → 查看 AI 产出 → Approve / Reject / Comment
        │
        ▼
状态横幅实时显示当前阶段 + 「继续项目」「新建项目」按钮
        │
        ▼
项目 DONE → 查看/下载 final.mp4
```

**前端功能覆盖：**
- 项目列表页（创建/查看/状态）
- 项目详情页（流水线状态横幅 + Review Card 列表 + 素材上传区）
- ReviewCard 组件（支持 storyboard 可读文本展示、审批操作）
- 素材上传（图片/角色/配音/BGM，拖拽或选择文件）

---

## 二、底层 Agent 架构

### 2.1 总体架构（一张图）

```
HTTP/飞书 IM
    │
    ▼
API Gateway (FastAPI + WebSocket)
    │
    ▼
Workflow Runtime (v2 YAML 驱动 / v1 硬编码回退)
    │
    ├─ Middleware Chain (before)
    │   tracing → tool_guard → approval → audit → retry → cache → model_router
    │
    ├─ Context Builder ← Workspace + Asset Center
    │
    ├─ LeadAgent (单一通用 Agent)
    │   │
    │   ├─ Skill Loader → 按阶段匹配 SKILL.md = 完整 system prompt
    │   │   ├─ requirement_analysis (品牌解码+平台感知+反模式)
    │   │   ├─ storyboard_template (589行广告脚本生成方法论)
    │   │   └─ world_constraints (品牌合规硬约束)
    │   │
    │   ├─ understand_requirement() ─→ VideoSpec (结构化需求)
    │   ├─ generate_storyboard()   ─→ Storyboard (分镜脚本)
    │   └─ generate_scenes()       ─→ SceneList → shot.prompt (文生视频提示词)
    │
    ├─ Guardrails (after LLM output)
    │   广告法禁用词 / 品牌禁忌 / 内容安全
    │
    ├─ Providers
    │   ├─ LLM: DeepSeek v4 Flash (主力) / OpenAI / Mock
    │   ├─ Video: Kling 2.5 Turbo (文生视频 + 图生视频)
    │   └─ TTS: OpenAI TTS (或静音 fallback)
    │
    ├─ Tools (确定性执行，非 LLM 工具调用)
    │   ├─ ffmpeg (concat/mix/burn/render)
    │   ├─ tts (generate_narration)
    │   ├─ subtitle (generate_srt)
    │   └─ publish (local export)
    │
    ├─ Middleware Chain (after)
    │   save_workspace → save_assets → publish_event → trace → pause(review) → audit_log
    │
    └─ Event Bus → ChannelManager → 飞书/企微/Web 推送
```

### 2.2 核心设计决策

#### 2.2.1 不是多 Agent 协同，是单一 LeadAgent + 阶段化 Skill 注入

这是 SmartVideo 区别于 LangGraph/Coze 等竞品的关键架构差异：

| 维度 | SmartVideo | 典型多 Agent 方案 |
|------|-----------|------------------|
| Agent 数量 | **1 个** LeadAgent | 7+ 专用 Agent |
| 阶段切换方式 | 更换 system prompt (SKILL.md) | 切换 Agent 实例 |
| 上下文传递 | 同一 Agent 实例，自然连续 | 需序列化/反序列化 |
| 复杂度 | 低：一个类三个方法 | 高：Agent 间通信协议 |
| 调试 | 单点追踪 | 多跳追踪 |

**好处**：LeadAgent 的 `understand_requirement` / `generate_storyboard` / `generate_scenes` 三个方法共享同一个 `ModelRouter` 实例和 Langfuse trace，且支持多轮对话——驳回后把 `previous_output` 作为 assistant message 重新注入，LLM 看到自己上一轮输出后做局部修改，而非从零生成。

#### 2.2.2 两层 Prompt 架构（SKILL.md = 完整 system prompt）

```
YAML (wiring only)          SKILL.md (完整 system prompt)
─────────────────────       ─────────────────────────────
stage: requirement          品牌声调解码矩阵（6人格）
agent: lead                 平台格式感知（5平台，抖音/小红书等）
skill: requirement_analysis 品类反模式（7品类：咖啡不让苦味等）
tools: [search]             输出规范 + JSON格式要求
pause_for_review: true      违规红线清单
```

- **SKILL.md 是完整的、可直接用作 system message 的文本**，包含角色定义+方法论+规则+示例
- **YAML 只负责 wiring**：stage→skill 配对、tools 声明、暂停点标记
- **Pydantic schema 走 API 层的 `response_format`**，不进 prompt，避免 token 浪费和格式约束冲突

#### 2.2.3 Tools 是确定性过程调用，不是 LLM Function Calling

这是当前版本的一个**刻意简化**：

- `tools/ffmpeg`、`tools/tts`、`tools/subtitle` 等由 `runtime/workflow.py` 的 `_exec_*` handler 直接 import 调用
- LeadAgent 只管结构化输出（VideoSpec → Storyboard → SceneList），不感知工具清单
- 工具调用路径：`YAML tools 字段声明 → handler 确定性执行`，无 ReAct 循环

**为什么这样设计？** 视频生产流水线的工具调用顺序是固定的（生成→配音→字幕→合成），不需要 LLM 做工具选择决策。把工具执行与 LLM 推理分离，反而降低了延迟和不稳定性。

#### 2.2.4 双引擎并存（v1 硬编码 + v2 YAML 驱动）

```
Web API / 飞书
    │
    ├─ run_pipeline_v2()  ← 默认，读 workflows/*.yaml
    │   阶段路由：_route_next_stage() 读 YAML next 边
    │
    └─ run_pipeline()     ← fallback，硬编码状态机
        阶段路由：内置 if/elif 链
```

YAML 引擎带来的价值：
- 改一条 YAML 即可新增/调整/删除流水线阶段，零代码改动
- 已支持 3 套工作流模板：`product_ad`（7 阶段，4 暂停点）、`douyin_short`（5 阶段，3 暂停点）、`digital_human`（6 阶段，4 暂停点）
- 未来新增模板（ecommerce / brand_film）只需写 YAML + 配 SKILL.md

#### 2.2.5 ConversationRouter（对话状态机，替代审批卡片）

```
用户发消息
    │
    ▼
IntentParser.parse_intent(text)
    │
    ├─ "批准/同意/通过/approve" → approve + resume
    ├─ "驳回 改成暖色调"        → reject_feedback + resume(带 feedback)
    ├─ "驳回/拒绝/不通过"        → reject(不 resume)
    ├─ "这个是什么意思"          → clarify(提示当前审批内容)
    └─ 其他                     → 提醒"请先处理当前审批"
    │
    ▼
ConversationRouter
    ├─ 每人一个活跃审批槽位，多余排队
    ├─ 30min 超时自动重提醒（最多 3 次）
    └─ 审批完成后自动释放、升级队列中下一条
```

---

## 三、产品优点

### 3.1 端到端闭环，而非 Prompt 到视频的"黑盒"

| 竞品典型模式 | SmartVideo |
|------------|-----------|
| 用户写 prompt → 出视频 → 不满意重新写 | 用户写 brief → **需求理解** → **分镜脚本** → **资产准备** → **逐镜头生成** → **配音字幕合成** → 发布 |
| 单次生成，不可干预 | **4 个人工审批节点**，每阶段可驳回修改 |
| 无产物沉淀 | 项目结束后**自动沉淀资产库**（品牌/角色/prompt/素材） |

### 3.2 Human-in-the-Loop 贯穿全流程

4 个审批暂停点覆盖了视频生产的全部关键决策：

1. **Requirement** — 需求理解是否正确？方向偏了再往后跑都是浪费
2. **Storyboard** — 分镜脚本是否符合预期？这是创意质量的最后防线
3. **Asset Prep** — 角色/配音/品牌/风格确认，以及用户上传素材的审核
4. **Video Review** — 成品片段审核，合成前最后一次纠错

每个节点的驳回都支持**带反馈的局部修改**（"驳回 改成暖色调"），feedback 直接回流 LLM，不算重来而是"增量修改"。

### 3.3 飞书原生对话体验

- **零学习成本**：用户像跟同事聊天一样发需求、做审批，不需要打开另一个系统
- **纯文本交互**：不依赖飞书后台的 `card.action.trigger` 事件订阅（许多企业飞书管理员不开启此项），用「批准」「驳回 改成XX」就能完成全部交互
- **排队+超时机制**：每个用户同时只有一个活跃审批，30 分钟无响应自动提醒，避免审批遗漏

### 3.4 YAML 驱动的可配置流水线

- 视频生产流水线不是硬编码的 if/else，而是可读可改的 YAML 定义
- 新增视频类型（如品牌大片、电商带货）只需新增一个 YAML 文件 + 对应的 SKILL.md
- 阶段间的 next 边支持分支（未来可做条件路由，如"有数字人→走 digital_human 分支"）

### 3.5 广告领域深度

- **requirement_analysis Skill** 内置广告行业知识：6 种品牌人格解码、5 个平台格式感知、7 个品类反模式（如咖啡类不让用"苦"字）
- **storyboard_template Skill**（589 行）包含完整的爆款商业广告脚本生成方法论：合规审查→洞察拆解→视觉锚点→分镜扩写→AIGC 参数化，含导演风格库（Spike Jonze / Michel Gondry 等）
- **VideoSpec** 已扩展广告营销元数据字段：product_name / ad_appeal / target_audience / usp 等
- **搜索上下文注入**：requirement 阶段可接 Tavily 等搜索 API，自动收集品牌信息、竞品参考

### 3.6 素材沉淀与复用

- 项目结束后自动沉淀品牌资产、角色资产、创意资产、媒体资产
- 用户上传的素材（产品图 / 模特图 / 品牌 BGM）自动登记为资产，可在后续项目中引用
- 参考图已接入 Kling 图生视频链路，上传的模特图可直接作为首帧参考

### 3.7 可观测性完备

- Langfuse 自动追踪所有 LLM 调用（token / cost / latency）
- EventBus 发布 PAUSED / COMPLETED / ERROR 事件
- Middleware Chain 记录 audit log + tracing + retry
- 每个项目的 `workflow_state.json` 完整记录流水线状态和错误栈

---

## 四、关键迭代

### 迭代总览

| 时间 | 迭代 | 核心交付 | 产品意义 |
|------|------|---------|---------|
| 07-27 | Phase 1 Core Engine | 媒体工具链(TTS/字幕/FFmpeg) + Workflow 引擎重构 | **从骨架到可运行** |
| 07-27 | 飞书集成修复 | SDK 长连接 + 审批卡片推送 | **打通第一个交互通道** |
| 07-28 | Kling 2.5 Turbo 集成 | 真实视频生成 Provider | **从模拟到真视频** |
| 07-28 | 飞书端到端实测 | event loop / 重复卡片 / 轮询等 5+ bug 修复 | **飞书闭环首次跑通** |
| 07-29 | 分镜头改造 | 每个 shot 独立生成 Kling clip 再拼接 | **真正的分镜头，非合并 prompt** |
| 07-29 | DeepSeek 接入 | LLM 主力从 OpenAI 切换到 DeepSeek v4 flash | **成本控制 + 中文优化** |
| 07-31 | Phase 1.1 Skill 加载器 | SKILL.md 自动发现注入 LeadAgent | **从空壳到真实注入** |
| 07-31 | Phase 1.2 ASSET_PREP | 第 4 个 HITL 节点 | **资产审批闭环** |
| 07-31 | Phase 1.3 PUBLISH | 本地发布流水线 | **从生成到交付** |
| 07-31 | Phase 2 YAML 引擎 | YAML 驱动的主干流水线 | **从硬编码到可配置** |
| 08-01 | Prompt 架构简化 | SKILL.md = 完整 system prompt | **架构定论：两层设计** |
| 08-01 | requirement_analysis Skill | 96 行广告分析 Skill | **领域知识注入** |
| 08-01 | 飞书审批改版 | 卡片→纯文本对话 + ConversationRouter | **降低使用门槛** |
| 08-01 | 素材上传闭环 | 上传→资产登记→BGM 混入合成→参考图接 video_gen | **素材资产化** |
| 08-01 | HITL 内容可见性 | 每个审批节点推送 AI 产出全文 | **用户能看见 AI 做了什么** |
| 08-01 | 三需求修正落地 | HITL 增强+需求插槽+素材上传 | **完整产品闭环** |

### 4.1 Phase 1 — Core Engine（07-27 ~ 07-29）

**背景**：项目骨架已搭（LLM Provider + Web API + 前端），但三个核心缺口让系统无法真正跑通。

**关键决策与交付：**

1. **媒体工具链从零搭建**（1 天）
   - `tools/tts`：OpenAI TTS 配音 + 静音 fallback（无 API key 也能跑）
   - `tools/subtitle`：从 Scene/Shot narration 自动生成 SRT 时间轴
   - `tools/ffmpeg`：完整视频编辑工具链（concat→配音→BGM混音→字幕烧录→render_final 一键合成）
   - 端到端验证：3 clips → 8.64s 最终视频

2. **Workflow 引擎重构** — 解决了 3 块"死代码"
   - `_continue_scenes`：从"not yet implemented"到完整的逐场景 Kling 生成+暂停
   - `_continue_stitch`：从裸 concat 到 TTS→SRT→render_final 完整合成
   - `resume()` 分发：三个 continuation 方法全部接通

3. **飞书集成深度修复**（跨越 07-27 ~ 07-29，多次迭代）
   - WS 长连接从废弃端点迁移到官方 lark-oapi SDK 直连
   - event loop 冲突修复（跨线程 asyncio 执行器统一）
   - 重复审批卡片修复（ChannelManager 和 ws_listener 双订阅去重）
   - 文本审批兜底（识别「批准」「驳回」消息走 resume 逻辑）

4. **Kling 2.5 Turbo 正式接入**
   - 第一个真实视频生成 Provider，从"占位"到"真跑"
   - 单条 5s 视频约 40-50s 生成时间，消耗 1.5 video unit

5. **DeepSeek LLM 切换**
   - 发现 DeepSeek 不支持 `json_schema` 结构化输出，转而用 `json_object` + prompt 注入 schema
   - 修复 prompt 模板中的"偷懒留空"问题（强制所有字段推断默认值）
   - 从 OpenAI → DeepSeek v4 flash，成本显著下降，中文输出质量提升

6. **分镜头改造成 true shot-by-shot**
   - 之前多个 shot 合并为一条 prompt 一次 API 调用
   - 改为每个 shot 独立调 Kling，独立配音，再拼接
   - 发现并修复 demuxer `list_file.unlink()` 沙箱拦截 bug（2+ clip 拼接必发场景）

### 4.2 Phase 1.1 ~ 1.3 — 三连补齐（07-31）

**背景**：核查发现 Skill 体系是空壳（仅有 markdown 文档，LeadAgent 不引用），ASSET_PREP 和 PUBLISH 是孤儿节点。

**交付：**
- **Skill 加载器**（`skills/loader.py`）：按阶段名自动匹配 SKILL.md，零配置发现新 skill，storyboard system prompt 从 ~1400 chars → 19065 chars
- **ASSET_PREP HITL 节点**：storyboard 审批通过后先进入资产准备阶段（人物/配音/品牌建议+world_constraints 注入），暂停人工确认
- **PUBLISH 接入**：stitch 完成后自动走 `publish_local()` 导出到 outputs/publish/

此时完整 HITL 链成型：`requirement(1) → storyboard(2) → asset_prep(3) → video_review(4)`

### 4.3 Phase 2 — YAML 引擎接主干（07-31）

**背景**：`runtime/executor.py` 的 YAML 引擎早已实现但从未接入 API，是"孤儿实现"。

**交付：**
- `runtime/workflow.py` 重写：新增 `run_pipeline_v2()` 读 YAML，7 个细粒度 `_exec_*` handler
- `resume()` 改为 YAML 感知路由：优先读 YAML `next` 边，缺失回退硬编码 fallback
- v1 完整保留作 fallback，Web API/飞书调用方零改动
- 13 个单元测试全部通过
- 3 套工作流模板就绪

**产品意义**：从"改代码才能改流程"到"改 YAML 就能改流程"，为多模板扩展扫清障碍。

### 4.4 Phase 3 — 产品打磨（08-01）

**这是密度最高的一天，完成了从"能跑"到"好用"的跃升。**

#### 4.4.1 Prompt 架构定论

- **SKILL.md = 完整 system prompt**，YAML = wiring only
- 删掉了之前混在 SKILL.md 里的 Agent 衔接指令和 JSON Schema（各 100+ 行冗余）
- 明确了 Pydantic 走 API `response_format` 不进 prompt 的职责边界

#### 4.4.2 飞书体验改版（影响最大的一次 UX 迭代）

**之前**：用户在飞书收到交互式审批卡片，点"批准/驳回"按钮 → 依赖飞书后台 `card.action.trigger` 订阅 → 很多场景不生效 → 用户点按钮没反应 → 体验灾难。

**之后**：纯文本对话审批
- 用户只需回「批准」「驳回 改成暖色调」等自然语言
- 新增两个核心模块：
  - `IntentParser`：关键词规则解析（approve / reject / reject_feedback / clarify / unrelated）
  - `ConversationRouter`：每人单槽排队 + 30min 超时重提醒 + 自动释放
- 按钮回调逻辑完全删除（~85 行代码）

**这是一次"做减法"的产品决策**：砍掉了需要飞书后台配合的卡片交互，换成了零配置的对话式交互，大幅降低了部署门槛。

#### 4.4.3 HITL 内容可见性

**之前**：审批卡片只有"项目需要在 XX 阶段审批"一行，AI 产出（需求分析、故事板、资产建议）完全不可见，用户要在不知情的情况下做决策。

**之后**：每个 HITL 节点先发送 AI 产出全文（用飞书 markdown 格式化），再发送审批提示。用户看到完整内容后再决定批准还是驳回。

#### 4.4.4 素材上传闭环

- `POST /api/v1/assets/upload`：支持图片/角色/配音/BGM 上传，类型校验+大小限制
- BGM 上传后自动接入 `render_final(bgm_path=...)`
- 参考图（产品图/模特图）自动注入 Kling 图生视频
- asset_prep 审批卡片里展示已上传素材和系统建议的对比

#### 4.4.5 三需求修正完整落地

| 需求 | 状态 | 关键改动 |
|------|------|---------|
| HITL 增强（继续/新建按钮 + 产物 txt + 反馈回流 LLM） | ✅ 100% | 项目状态 API + 前端按钮 + ReviewCard 可读文本 + LeadAgent 多轮对话参数 |
| Requirement 插槽 + 搜索 | ✅ 100% | VideoSpec 扩展 product_name/ad_appeal/target_audience/usp + Tavily 搜索集成 + requirement_analysis SKILL.md 模板化 |
| 素材上传（上传+BGM→stitch+参考图→video_gen） | ✅ 100% | upload 端点 + 资产登记 + BGM 混入合成 + 参考图接入 Kling |

---

## 附录：当前完成度总览

| 阶段 | 完成度 | 说明 |
|------|--------|------|
| Phase 1 Core Engine | **95%** | Kling + 媒体工具链 + workflow 串联 + Skill 加载器 + prompt 架构简化 |
| Phase 2 Web Platform | **80%** | API + 前端基本就位，缺异步 Worker |
| Phase 3 Human in Loop | **100%** | 4 个 HITL 节点 + 纯对话审批 + feedback 回流 LLM |
| Phase 4 Asset + Workflow | **85%** | 资产存储 + YAML 引擎接主干 + tools 声明，无语义检索 |
| Phase 5 IM + Enterprise | **40%** | 飞书完整实现，guardrails/RBAC 缺失 |
| Phase 6 发布 | **100%** | LocalPublisher + PUBLISH stage 接入流水线 |

**剩余 P0 缺口**：异步 Worker（视频生成目前是同步阻塞）、RBAC 权限、语义化资产检索、非文字消息自动回复。这些是向企业级产品演进的关键路径。
