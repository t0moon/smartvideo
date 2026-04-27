# smartvideo

[English](README.md) | **简体中文**

## 示例成片

本示例对应本机一次运行中 **staged 成片**（`final.staged.mp4`，路径：`outputs/20260427_195844/final.staged.mp4`），已复制到仓库 `docs/assets/` 供浏览与下载。

<video src="https://raw.githubusercontent.com/t0moon/smartvideo/main/docs/assets/demo_final_staged_20260427.mp4" controls width="100%"></video>

[直接打开 / 下载 MP4](docs/assets/demo_final_staged_20260427.mp4)

## 项目概述

**smartvideo** 是一套面向**品牌广告视频**的自动化管线。用户只需提供一段**品牌 / 产品 brief**（纯文本），系统会串联多步大模型与媒体处理，在流程末尾输出**最终成片在磁盘上的路径**；中间产物与成片默认写入 `outputs/`（可用环境变量 `SMARTVIDEO_ARTIFACTS_DIR` 调整根目录）。

**主要能力：**

1. **分镜与叙事规划**  
   结合项目内 **`skills/` 下的 SKILL.md**（分镜模板、世界观约束等），由 LLM 将 brief 落为结构化分镜、场景与镜头级描述，为视频与旁白提供依据。

2. **品牌信息**  
   从 brief 中抽取 / 整理**品牌画像**；在配置允许时，还可进行**联网调研**（具体策略与工具由 `BRAND_RESEARCH_STRATEGY` 等环境变量与代码路径控制），使内容更贴品牌与事实。

3. **视频片段生成**  
   按场景调用**可插拔的视频提供方**（如占位、OpenAI 兼容的异步视频 API、或自定义 HTTP 网关），生成各段视频素材；重试、超时与回退等由 `VIDEO_*` 及实现代码共同约束。

4. **音画后期**  
   可选**旁白 TTS**、分镜**音效（SFX）**、成片**BGM** 与响度 / ducking 等，在拼接前为单段与全片配好音轨或做基础母带感处理，详见 `.env.example` 中的 `AUDIO_*`。

5. **成片输出**  
   使用本机 **FFmpeg** 将多段视频与音轨**拼接 / 合成**为最终文件；全链路成功时，命令行在**标准输出**中打印**最终视频路径**。

6. **复跑与增量**  
   在已有 `scenes.json` 等产物时，可用 **`smartvideo-remake`** 只重跑**视频 → 音频 → 拼接**，避免从头重跑大模型各节点，便于更换视频后端或调参。

**使用方式（摘要）：** 配置好 `.env`（至少 `OPENAI_API_KEY` 等，见下节）后，通过 `smartvideo "你的 brief"` 或 `python -m app.run` 一次跑完全链路；需要时用 `smartvideo-remake` 做局部重算。完整命令与说明见后文「使用」。

## 功能概览（速查）

- **工作流**（`app/graph/graph.py`）：加载技能 → 品牌画像 → 分镜与约束（LLM + skills）→ 场景列表 → 视频 → 音频 → 拼接成片。
- **视频提供方**：`placeholder`（占位）、`openai_videos`（OpenAI 兼容异步视频 API）、`http`（通用 HTTP 网关），见环境变量 `VIDEO_*`。
- **音频**：TTS 旁白、分镜 SFX、最终 BGM 与响度/ducking 等，见 `.env.example` 中 `AUDIO_*`。
- **复跑片段**（不重复跑 LLM）：`smartvideo-remake` 从已保存的 `scenes.json` 或某次 `outputs/<run_id>` 仅重跑视频/音频/拼接。

## 环境要求

- **Python** ≥ 3.11
- **FFmpeg**：拼接与音画处理需要本机可执行 `ffmpeg`；仓库内附带 Windows 用 `.tools/ffmpeg-*` 可选作本地路径（若你在代码里指向该 bin）。

## 安装

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

pip install -e ".[dev]"
```

从项目根复制环境变量模板并编辑：

```bash
copy .env.example .env
# 或: cp .env.example .env
```

至少设置 **`OPENAI_API_KEY`**；若使用非官方 OpenAI 端点，设置 **`OPENAI_BASE_URL`**（通常含 `/v1`）及 **`OPENAI_MODEL`**。其余变量见 `.env.example` 内注释（视频、音频、技能目录、产物目录等）。

## 使用

**命令行入口**（`pyproject.toml` 中已注册）：

```bash
smartvideo "你的品牌与产品描述（brief）"
```

或：

```bash
python -m app.run "你的品牌与产品描述"
```

也可通过 **stdin** 传入 brief；成功时标准输出为最终成片路径。

**仅根据已有分镜重跑视频/音画/合成**（示例）：

```bash
smartvideo-remake path/to/scenes.json
# 或指向某次 run 目录（内含 scenes.json）
smartvideo-remake outputs/<run_id>
```

具体参数以 `smartvideo-remake --help` 为准。

## 技能与配置

- 默认可从环境变量 **`SMARTVIDEO_SKILLS_ROOT`** 指定技能根目录（默认项目下 `skills/`），内含分镜模板、世界观约束等 **SKILL.md**。
- 品牌联网调研相关可通过 **`BRAND_RESEARCH_STRATEGY`** 等调整（见 `app/config.py`）。

## 开发与测试

```bash
pytest
```

可选使用 **ruff** 做风格检查（见 `pyproject.toml` 中 `[tool.ruff]`）。

## 项目结构（简要）

| 路径 | 说明 |
| --- | --- |
| `app/graph/` | LangGraph 状态与各节点（品牌、分镜、场景、视频、音频、拼接） |
| `app/providers/` | 视频提供方实现 |
| `app/media/` | FFmpeg 等媒体封装 |
| `skills/` | 外部 SKILL 提示与模板 |
| `tests/` | 单元与冒烟测试 |
| `outputs/` | 运行产物（默认，可通过 `SMARTVIDEO_ARTIFACTS_DIR` 改） |

## 许可证

本仓库未附带许可证文件时，使用与分发前请自行补充并遵守相应条款。
