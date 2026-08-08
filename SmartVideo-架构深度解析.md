# SmartVideo 架构深度解析

> 四个核心命题：节点与状态机 / 消息事件策略 / Human-in-the-Loop / 关键迭代

---

## 一、项目有哪些节点，状态机是什么样子的

### 1.1 流水线节点（7 阶段，4 暂停点）

SmartVideo 的生产流水线由 7 个阶段组成，通过 YAML 文件定义，形成一条有向无环图（DAG）：

```
requirement ────► storyboard ────► asset_prep ────► scene_gen
    [HITL #1]       [HITL #2]       [HITL #3]
                                                         │
                                                         ▼
   publish ◄──── stitch ◄──────── video_gen ◄───────────┘
             [自动]          [HITL #4]          [自动]
```

| 阶段 | ID | 驱动者 | 暂停审批 | 做什么 |
|------|-----|--------|:---:|------|
| 需求理解 | `requirement` | LeadAgent | ✅ | 将用户 brief 解析为结构化的 VideoSpec（时长/风格/品牌/平台/卖点/受众） |
| 分镜脚本 | `storyboard` | LeadAgent | ✅ | 从 VideoSpec 生成完整分镜（场景→镜头→运镜→prompt→口播文案） |
| 资产准备 | `asset_prep` | LeadAgent | ✅ | 提取角色/配音/品牌建议 + 注入合规约束，展示用户上传素材 |
| 场景生成 | `scene_gen` | LeadAgent | ✗ | 将分镜拆解为 SceneList（每 shot 含英文文生视频 prompt） |
| 视频生成 | `video_gen` | Kling 2.5 Turbo | ✅ | 逐 shot 调用 Kling 生成视频片段，轮询下载 clip |
| 合成拼接 | `stitch` | FFmpeg + TTS + 字幕 | ✗ | 配音→字幕→BGM混音→FFmpeg渲染→输出 final.mp4 |
| 发布导出 | `publish` | LocalPublisher | ✗ | 复制成片到 outputs/publish/ 目录 |

**阶段间的执行策略：**
- **自动级联**：`scene_gen` 执行完毕后自动进入 `video_gen`（无暂停），`stitch` 完成后自动进入 `publish`
- **HITL 暂停**：`requirement` / `storyboard` / `asset_prep` / `video_gen` 四个节点执行完毕后暂停，等待人工审批
- **跳过策略**：审批被驳回（无反馈）时终止流水线；驳回带反馈时走 `partial_revision` 路径局部重写

### 1.2 两层状态机架构

SmartVideo 有两层状态机，分别服务于不同抽象层级：

#### 第一层：通用 DAG 状态机（`runtime/state_machine.py`）

这是底层通用的工作流引擎，与业务无关：

```
StageState 枚举（6 种状态）：
  PENDING  ──start()──►  RUNNING  ──complete()──►  COMPLETED
     │                      │
     │                   pause()                    fail()
     │                      │                        │
     │                      ▼                        ▼
     │                    PAUSED                   FAILED
     │                      │
     │                   resume()
     │                      │
     └──────────────────────┘

  SKIPPED：stage 被标记跳过（未来条件分支用）
```

**核心数据结构 `WorkflowStateMachine`**：
- `stages: dict[str, StageNode]` — 所有阶段的注册表
- `edges: dict[str, list[str]]` — 有向边（`requirement → storyboard → asset_prep → ...`）
- `current_stage_id` — 当前活跃阶段
- 关键方法：`get_first_stage()`（DFS 找入度为 0 的节点作为起点）、`get_next_stages(id)`（读 edges）、`get_ordered_stages()`（DFS 拓扑排序）
- 全局判断：`is_completed()`（所有阶段 completed/skipped）、`is_paused()`（任意阶段 paused）

#### 第二层：业务状态机（`runtime/workflow.py` 的 `WorkflowRuntime`）

这是面向视频生产业务的编排层，包含：

| 组件 | 职责 |
|------|------|
| `WorkflowState` (Pydantic) | 持久化的流水线运行时状态：`project_id` / `current_stage` / `video_spec` / `storyboard` / `scenes` / `clips` / `final_video_path` / `errors` / `paused` / `meta` |
| `ProjectStage` 枚举 | 项目级生命周期：CREATED → REQUIREMENT → STORYBOARD → ASSET_PREP → SCENE_GEN → VIDEO_PROD → REVIEW → PUBLISH → DONE → ARCHIVED |
| YAML 驱动路由 | `run_pipeline_v2()` 读 `workflows/*.yaml`，按 `next` 边推进；`resume()` 复用同一 `_route_next_stage()` 继续执行 |
| 7 个 `_exec_*` handler | 每阶段一个执行函数，内部调 LeadAgent / VideoProvider / FFmpeg 等，完成后判断是否暂停 |
| v1 硬编码回退 | `run_pipeline()` 保留完整，Web API / 飞书调用方零改动 |

**`resume()` 的决策树**（HITL 恢复的核心路由）：

```
resume(project_id, review_id)
    │
    ├─ review 不存在或未 resolved → 返回空
    │
    ├─ rejected（纯拒绝，无反馈）→ advance_stage(REVIEW)，终止
    │
    ├─ partial_revision + storyboard + 有 feedback
    │      → _revise_storyboard()  用 feedback 局部重写分镜，重新暂停
    │
    └─ approved / partial_revision(非分镜)
           │
           ├─ 读 state.meta.pause_stage 获取上次暂停点
           ├─ _route_next_stage(pause_stage, workflow_name)
           │     ├─ 优先读 YAML edges
           │     └─ 缺失时走硬编码 fallback map
           │
           └─ 执行下一阶段的 _exec_* handler
                  ├─ 若下一阶段 pause_for_review=true → 暂停
                  └─ 否则级联到下一个不暂停的阶段为止
```

### 1.3 三层状态持久化

```
SQLite (ProjectModel)         文件系统 (workflow_state.json)        文件系统 (project.json)
─────────────────────         ────────────────────────────          ──────────────────────
project.stage (ProjectStage)   state.paused / meta.pause_stage       project.json.stage
ID / name / brief / 时间戳      video_spec / storyboard / scenes     (advance_stage 更新)
                                 clips / final_video_path / errors
```

**已知问题**：三层状态不完全同步——`workflow_state.current_stage` 从不更新（始终为 `created`），`project.json.stage` 和 DB `stage` 分别由不同代码路径更新，排查时需对照三处。

---

## 二、消息、事件策略是怎么管理的

### 2.1 事件总线（EventBus）架构

SmartVideo 使用 **发布-订阅模式** 解耦流水线逻辑与通知逻辑：

```
EventBus (全局单例)
    │
    ├─ publish(event) ──► _history 追加
    │                     ├─ 遍历 _subscribers[event_type] 逐个调用
    │                     └─ 遍历 _subscribers['*'] 通配符订阅者
    │
    ├─ subscribe(event_type, handler)
    ├─ unsubscribe(event_type, handler)
    └─ get_history(event_type, limit)
```

**10 种事件类型**（`events/bus.py`）：

| 事件常量 | 触发时机 | 携带数据 |
|---------|---------|---------|
| `project.created` | 创建项目 | project_id |
| `project.updated` | 更新项目 | project_id |
| `project.deleted` | 删除项目 | project_id |
| `pipeline.started` | 流水线启动 | project_id |
| `pipeline.paused` | 流水线暂停（HITL 节点） | project_id + review_id + stage |
| `pipeline.completed` | 流水线完成 | project_id |
| `pipeline.error` | 流水线异常 | project_id + error |
| `review.created` | 审批节点创建 | project_id + review_id + stage |
| `review.resolved` | 审批节点被解决 | project_id + stage + status |
| `guardrail.violation` | 合规检查违规 | project_id + violation |

**Event 对象**：每个事件有唯一 `event_id`（12 位 hex）、`event_type`、`data` dict、`priority`（LOW/NORMAL/HIGH）、`source`、`created_at`。

### 2.2 事件订阅与通知链路

```
_continue_requirement()
    │
    ├─ 创建 review → bus.publish(Event(EVENT_REVIEW_CREATED, {...}))
    ├─ 暂停流水线 → bus.publish(Event(EVENT_PIPELINE_PAUSED, {...}))
    │
    └─► ChannelManager 订阅者
           │
           └─ on_pipeline_paused(event)
                  └─ _fire_notification(channel, project_id, review_id, stage)
                         │
                         └─► FeishuChannel.notify_review()
                                 │
                                 ├─ 1. 发送 AI 产出内容文本（format_review_content）
                                 ├─ 2. 发送审批提示文本 + ConversationRouter.register()
                                 │
                                 └─► 飞书 WS → 用户手机/客户端
```

**通知降级链**：
1. FeishuChannel 可用 → 推送飞书消息
2. Feishu 未配置 → 回落 WebhookChannel
3. 通知发送失败 → 捕获异常打印日志，不中断流水线

### 2.3 飞书消息策略（三条路线）

#### 路线 A：流水线事件驱动的自动通知

```
pipeline 暂停 → EventBus publish → ChannelManager 订阅者 → FeishuChannel.notify_review()
    │
    ├─ 目标接收人：FEISHU_REVIEWER_OPEN_ID（.env 配置的固定审批人）
    ├─ 消息格式：
    │     📌 [需求分析] 结果如下：
    │     视频时长：10秒
    │     风格：极简
    │     品牌：瑞幸
    │     ...
    │     【当前阶段：需求分析 — 待审批】
    │     请回复「批准」继续，「驳回」（加修改意见）重新生成。
    └─ 注册到 ConversationRouter，等待用户响应
```

#### 路线 B：飞书 WS 消息驱动的交互

```
用户在飞书给机器人发消息
    │
    ├─ 机器人 on_im_message 回调
    │     ├─ msg_type != "text" → 静默忽略（语音/图片不回不报）
    │     ├─ message_id 去重检查（TTL 10min）→ 已处理过的忽略
    │     └─ brief 短期去重（5s 窗口）→ 相同 brief 回复"正在处理中"
    │
    ├─ ConversationRouter.route(user_id, message_id, text)
    │     ├─ user_id 不在 _states 中 → 返回 "new_project"
    │     │     → _run_pipeline_and_notify() 创建项目+跑流水线
    │     │
    │     └─ user_id 在 _states 中 → 走审批路由
    │           ├─ IntentParser.parse_intent(text)
    │           │     ├─ "批准" / "同意" / "通过" → approve
    │           │     ├─ "驳回 改成暖色调" → reject_feedback (feedback="改成暖色调")
    │           │     ├─ "驳回" / "拒绝" → reject (无反馈)
    │           │     ├─ "什么意思" / "再说一遍" → clarify
    │           │     └─ 其余 → unrelated
    │           │
    │           ├─ approve → ReviewService.approve() + 后台线程 resume()
    │           ├─ reject_feedback → add_comment + partial_revision + resume()
    │           ├─ reject(无 feedback) → ReviewService.reject() + 不 resume
    │           └─ clarify / unrelated → 重发提示文本
    │
    └─ 回复用户 ack 消息：
          "已批准 分镜脚本，继续执行..."
          "已驳回 需求分析，将根据意见重新生成..."
          "当前有一个待审批的 素材准备，请先回复「批准」或「驳回」"
```

#### 路线 C：ConversationRouter 排队与超时

```
用户 A 有活跃审批 → 新审批到达
    │
    └─→ 不覆盖，进入 _queues 队列
        用户 A 完成当前审批 → release() → 自动升级队列头部

超时机制（check_timeouts()，后台定时调用）：
    ├─ 30 min 无响应 → 飞书重提醒 "[提醒 1/3] 还有一个待审批的需求分析..."
    ├─ 60 min → "[提醒 2/3]..."
    ├─ 90 min → "[提醒 3/3]..."
    └─ 120 min → 放弃，通知用户"审批已超时，请重新发起"
```

### 2.4 消息内容生成策略（每阶段差异化）

| 审批阶段 | 发送内容 | 格式化器 |
|---------|---------|---------|
| requirement | 视频时长/风格/品牌/产品名/广告诉求/目标受众/平台/真人出镜/语气语调/核心卖点/竞争参考 | `_format_requirement()` |
| storyboard | 优先展示 `readable_text`（人类可读故事板全文）；fallback 场景列表摘要 | `_format_storyboard()` |
| asset_prep | 建议角色（真人/数字人+描述）/建议配音/品牌/平台/风格备注 + 用户已上传素材清单 | `_format_asset_prep()` |
| video_review | 片段数量（"视频已生成（3个片段），请确认后继续"） | `_format_video_review()` |

### 2.5 跨线程异步执行策略

飞书 WS 回调 + 流水线 resume 涉及多线程和 async 混用，这曾是最棘手的 bug 来源。解决策略：

```
全局专用 asyncio 事件循环（async_executor.py）
    │
    ├─ _loop_thread: 后台 daemon 线程，运行唯一的事件循环
    ├─ run_async(coro): 所有 FeishuClient 调用统一走此入口
    │     └─ asyncio.run_coroutine_threadsafe(coro, _loop)
    │
    ├─ 健康检查：ensure_loop() 检测线程 alive + loop 未 closed
    │     失效时自动重建线程+循环
    │
    └─ 使用方：
          ├─ ws_listener.py（飞书消息回调，WS 线程内）
          ├─ ChannelManager（pipeline 事件回调，后台线程内）
          └─ ConversationRouter（审批路由，后台线程内）
```

**关键原则**：所有 FeishuClient 的异步调用聚集到同一个 loop，避免"Event loop is closed"和跨线程 httpx.AsyncClient 绑定错误。

---

## 三、Human-in-the-Loop 设计

### 3.1 为什么是 4 个审批节点

选择这些节点而非其他，对应视频生产团队的真实决策流程：

| 审批点 | 对应真实角色 | 决策内容 | 错误代价 |
|--------|------------|---------|---------|
| requirement | 创意总监/客户 | "这个需求理解对吗？方向对吗？" | 方向错了，后续全白做 |
| storyboard | 导演/编导 | "分镜脚本符合品牌调性吗？节奏对吗？" | 分镜是创意的最后防线 |
| asset_prep | 美术指导/制片 | "角色/配音/品牌素材选对了吗？" | 资产选错影响全片一致性 |
| video_review | 客户/终审 | "成片片段过吗？可以合成吗？" | 合成后返工成本高 |

### 3.2 Review 生命周期

```
ReviewService.create_*_review()
    │
    ▼
ReviewRecord(status=PENDING)
    │
    ├─ approve(reviewer, comment)
    │     → status=APPROVED + resolved_at + EVENT_REVIEW_RESOLVED
    │     → pipeline resume（自动推进到下一阶段）
    │
    ├─ reject(reviewer, comment)
    │     → status=REJECTED + resolved_at + EVENT_REVIEW_RESOLVED
    │     → pipeline 终止（不 resume）
    │
    ├─ partial_revision(reviewer, feedback)
    │     → status=PARTIAL_REVISION + resolved_at + EVENT_REVIEW_RESOLVED
    │     → pipeline resume（feedback 回流给 LLM 做局部重写）
    │
    └─ add_comment(review_id, text, reviewer)
          → 追加评论到 comments 数组（不改变 status）
```

**Review 持久化**：SQLite 存储，`ReviewService` 通过 SQLAlchemy `ReviewModel` CRUD，跨后端重启不丢失。

**is_project_blocked()**：检查项目下是否有任何 PENDING 状态的 review，用于前端展示阻塞状态。

### 3.3 Feedback 回流 LLM（"驳回 改成暖色调" 如何生效）

这是 HITL 闭环的关键——用户的修改意见不只是被记录，而是真正改变 AI 的生成结果：

```
用户在飞书回复："驳回 改成暖色调"
    │
    ▼
IntentParser.parse_intent("驳回 改成暖色调")
    → ("reject_feedback", "改成暖色调")
    │
    ▼
ConversationRouter._do_reject()
    ├─ ReviewService.add_comment(review_id, "改成暖色调")
    ├─ ReviewService.partial_revision(review_id, feedback="改成暖色调")
    └─ threading.Thread → WorkflowRuntime.resume(project_id, review_id)
    │
    ▼
WorkflowRuntime.resume() 检测到 partial_revision + storyboard + 有 feedback
    │
    ▼
_revise_storyboard(project_id, state, feedback="改成暖色调")
    │
    ▼
LeadAgent.generate_storyboard(
    spec=state.video_spec,
    feedback="改成暖色调",                    ← 用户原话注入
    previous_storyboard=state.storyboard      ← 上一轮完整输出
)
    │
    ▼
_build_system('storyboard') 构造 system prompt（SKILL.md 全文）
    │
    构造 messages:
    [
      {"role": "system", "content": SKILL.md},
      {"role": "user", "content": "根据以下需求生成分镜..."},
      {"role": "assistant", "content": previous_storyboard_json},  ← 让 LLM 看到自己上轮输出
      {"role": "user", "content": "请根据以下反馈修改：改成暖色调"}  ← 增量修改指令
    ]
    │
    ▼
ModelRouter.chat_structured() → 新版 Storyboard（暖色调调整，其余保留）
    │
    ▼
重新创建 storyboard review，再次暂停（让用户确认修改结果）
```

**为什么是"局部重写"而非"从零来"？** 因为把 `previous_output` 作为 assistant message 注入，LLM 能「看到自己上一轮说了什么」，只需要修改用户指出的部分。这比推倒重来更省 token、更快，且避免了重新生成时其他部分意外走样。

### 3.4 两种审批交互模式对比

| 维度 | 旧版（交互式卡片） | 新版（纯文本对话） |
|------|------------------|------------------|
| 交互方式 | 飞书卡片 + 批准/驳回按钮 | 聊天文字「批准」「驳回 改成XX」 |
| 部署门槛 | 需飞书后台开启 `card.action.trigger` 事件订阅 | **零配置** |
| 用户学习成本 | 需理解按钮概念 | 跟同事聊天一样 |
| 依赖 | 飞书服务器推送卡片事件到后端 | 仅依赖 WS 文本消息事件 |
| 失败表现 | 点按钮没反应，用户困惑 | 文字识别不匹配时机器人提示正确格式 |
| 审批反馈 | 只能纯批准/驳回 | 驳回时可带任意自然语言修改意见 |

**改版的原因**（来自 08-01 的真实教训）：旧版卡片按钮点击后依赖飞书服务器把 `card.action.trigger` 事件推送给后端。但这个事件的订阅需要在飞书开放平台后台手动开启——很多用户（甚至管理员）不知道这个步骤，导致按钮点击后「没有任何反应」，体验灾难。改为纯文本后，用户唯一需要做的就是打字，没有任何后台配置依赖。

---

## 四、关键迭代

### 4.1 迭代全景时间线

```
07-27  Phase 1 核心引擎            媒体工具链 + Workflow 重构 + 飞书 WS 修复
       ├─ TTS / SRT / FFmpeg 三工具链
       ├─ _continue_scenes / _continue_stitch / resume 三方法从死代码到接通
       └─ 飞书 SDK 直连 v2 WS 端点

07-28  Kling 2.5 Turbo 正式接入    第一个真实视频生成 Provider
       ├─ 适配新 API 格式（beijing 节点 / 2.5-turbo / audio=off）
       └─ 飞书端到端 5+ bug 修复（event loop / 重复卡片 / 轮询 / Mock LLM）

07-29  分镜头改造 + DeepSeek 切换    true shot-by-shot 生成 + 成本优化
       ├─ 每 shot 独立 Kling 生成 → 拼接（修复 demuxer unlink 沙箱 bug）
       ├─ DeepSeek v4 flash 接入（json_schema→json_object 适配）
       └─ prompt 模板修复（强制非空字段，解决 LLM "偷懒留空"）

07-31  三连补齐 + YAML 引擎         从空壳到真实运转 + 从硬编码到可配置
       ├─ Phase 1.1: Skill 加载器（SKILL.md 自动注入）
       ├─ Phase 1.2: ASSET_PREP HITL #3
       ├─ Phase 1.3: PUBLISH 接入
       └─ Phase 2: YAML 引擎接主干（v1/v2 双轨 + 3 套模板）

08-01  产品打磨日                  从"能跑"到"好用"
       ├─ Prompt 架构简化（SKILL.md = 完整 system prompt）
       ├─ requirement_analysis skill（广告行业知识注入）
       ├─ 飞书审批改版（卡片→文本，ConversationRouter）
       ├─ HITL 内容可见性（每节点推送 AI 产出全文）
       ├─ 素材上传闭环（上传→资产登记→BGM→stitch→参考图→Kling）
       ├─ 三需求修正全部落地
       └─ 飞书事件幂等 + 时长对齐 + 启动死锁修复
```

### 4.2 里程碑级迭代详解

#### 迭代一：从"骨架"到"能跑"（07-27，Phase 1 Core Engine）

**背景**：项目有 LLM Provider + Web API + 前端 UI，但核心视频生产链路是死的——`_continue_scenes` 的代码是 `raise NotImplementedError`，`_continue_stitch` 只有裸 concat。

**做了什么**：
- 从零实现了媒体工具链：TTS 配音、SRT 字幕自动时间轴、FFmpeg 七合一渲染工具
- 把 workflow.py 的三个空方法变成完整实现，端到端 3 clips → 8.64s 成品验证通过
- 飞书 WS 从废弃端点迁移到官方 SDK，打通 IM 交互通道

**产品意义**：系统第一次有了完整的「视频生产」能力，不再是一个 Demo 壳。

#### 迭代二：从"模拟"到"真生成"（07-28，Kling 2.5 Turbo）

**背景**：之前的视频 Provider 是 placeholder / mock，生成的视频是静态黑屏或简单合成，不具备实用价值。

**做了什么**：
- 接入 Kling 官方 API（beijing 节点），文生视频 + 图生视频
- 完整异步流程：提交任务→轮询状态→下载结果
- 5s 视频约 40-50s 生成时间，1.5 video unit

**产品意义**：从玩具变成能产出真实广告视频的工具。这条迭代是产品价值的「从 0 到 1」。

#### 迭代三：从"合并 prompt"到"逐镜头生成"（07-29，分镜头改造）

**背景**：之前多个 shot 的 prompt 被合并成一条，Kling 一次调用生成一个 clip。比如「咖啡研磨 + 倒入杯中」两个镜头被揉在一起，失去了分镜头的意义。

**做了什么**：
- 改为每个 shot 独立调 Kling → 每条 clip 独立配音 → 按 shot 顺序拼接
- 每个 shot 有独立的 prompt（英文、含运镜/灯光/空间参数）和 narration（中文口播）
- 修复了 2+ clip 拼接时 `list_file.unlink()` 被沙箱拦截的隐藏 bug

**产品意义**：从「伪分镜头」变成「真分镜头」，视频叙事结构由 LLM 决定而非被 API 限制框住。

#### 迭代四：从"硬编码"到"可配置"（07-31，Phase 2 YAML 引擎）

**背景**：流水线阶段是写死在 Python if/elif 里的。新增一种视频类型（如品牌大片）需要改代码、改测试、改部署。

**做了什么**：
- 7 阶段流水线从 Python 代码迁移到 YAML 文件
- `resume()` 路由从硬编码 map 改为读 YAML `next` 边
- 3 套模板就绪：product_ad（7 阶段 4 暂停）/ douyin_short（5 阶段 3 暂停）/ digital_human（6 阶段 4 暂停）
- v1 完整保留作 fallback

**产品意义**：改一条 YAML = 改流水线。这是从「项目级代码」到「平台级产品」的架构跃迁。

#### 迭代五：从"不知道 AI 做了什么"到"可见可决策"（08-01，HITL 内容可见性）

**背景**：之前的审批提示只有「项目需要在需求分析阶段审批」，用户完全不知道 AI 产出了什么就要做决策。

**做了什么**：
- 每个 HITL 节点先推送 AI 产出全文（飞书 markdown 格式化）
- requirement → 视频时长/风格/品牌/产品名/广告诉求/目标受众/平台等
- storyboard → 优先展示人类可读的故事板全文
- asset_prep → 角色建议/配音建议/品牌/平台/风格备注 + 用户上传素材清单

**产品意义**：用户能在知情的情况下做决策，这是 HITL 的前提条件——否则审批就是盲批。

#### 迭代六：从"依赖后台配置"到"零门槛"（08-01，飞书审批改版）

**背景**：交互式卡片按钮依赖飞书开放平台的 `card.action.trigger` 事件订阅，很多场景不生效，用户点按钮没反应。

**做了什么**（改动最大的一次 UX 迭代）：
- 删除了所有卡片按钮逻辑（~85 行代码）
- 新增 `IntentParser`：关键词规则解析 5 种意图（approve/reject/reject_feedback/clarify/unrelated）
- 新增 `ConversationRouter`：每人单槽排队 + 30min 超时提醒 + 排队升级 + 超时放弃

**产品意义**：从"需要 IT 配合部署"到"开箱即用"。这是 B 端产品中"做减法"的经典案例。

### 4.3 迭代中解决的关键 bug 及其产品启示

| Bug | 现象 | 根因 | 产品启示 |
|-----|------|------|---------|
| event loop is closed | 第二次之后的通知全部静默失败 | `asyncio.run()` 在不同线程重复调用 | 多线程+async 混用需要统一的调度器 |
| 重复审批卡片 | 用户收到两张一样的卡片 | ChannelManager 和 ws_listener 双重订阅同一事件 | 发布-订阅需要避免重复注册 |
| Kling 400 | 非标准时长视频请求被拒 | shot.duration_sec=3/4s 对齐到 5/10s | 外部 API 的约束需要 Abstract 层做适配 |
| 沙箱拦截 unlink | 2+ clip 拼接报错 | `list_file.unlink()` 在沙箱安全模式下失败 | 不能在不确定的环境假设文件操作一定成功 |
| import 死锁 | uvicorn 启动卡死 25s+ | `lark_oapi` 和 `LeadAgent` 在模块顶层 import | 重量级 SDK 必须懒加载 |
| 静默吞异常 | 飞书卡片不发也没有报错 | EventBus publish 无 try/except + async_executor 线程死亡检测不足 | 事件通知失败必须有显式的错误日志 |

**贯穿迭代的产品工程原则**：
- **永远不静默失败**：通知/审批/合成任何环节失败必须有日志和 error 记录
- **外部依赖加抽象层**：Kling 的时长对齐、TTS 的静音 fallback、ffmpeg 的路径解析——都是抽象层消化外部不确定性
- **做减法优先于做加法**：卡片按钮做不好就砍掉换文字，不跟不稳定的依赖死磕

---

## 附录：关键代码路径速查

| 你要找什么 | 文件路径 |
|-----------|---------|
| 节点枚举定义 | `backend/shared/enums.py` (ProjectStage) |
| 通用状态机 | `backend/runtime/state_machine.py` (WorkflowStateMachine / StageNode / StageState) |
| 业务编排层 | `backend/runtime/workflow.py` (WorkflowRuntime / _exec_* / run_pipeline_v2 / resume) |
| 工作流定义 | `backend/workflows/product_ad_v1.yaml` (7 阶段 YAML) |
| 事件总线 | `backend/events/bus.py` (EventBus / Event / 10 种事件常量) |
| 通知管理 | `backend/channels/manager.py` (ChannelManager / 订阅注册) |
| 对话路由 | `backend/channels/feishu/conversation.py` (ConversationRouter / 排队 / 超时) |
| 意图解析 | `backend/channels/feishu/intent.py` (IntentParser / 5 种意图) |
| 审批内容格式化 | `backend/channels/feishu/review_content.py` (per-stage 格式化器) |
| Review 服务 | `backend/review/service.py` (ReviewService / 4 种创建 + approve/reject/partial_revision) |
| 跨线程执行器 | `backend/channels/feishu/async_executor.py` (全局 asyncio loop 线程) |
| LeadAgent | `backend/agents/lead_agent.py` (3 方法 + feedback 多轮参数) |
| Skill 加载器 | `backend/skills/loader.py` (按阶段匹配 SKILL.md) |
