from __future__ import annotations

import argparse
import os
import sys

from langchain_core.messages import HumanMessage

from app.artifacts import new_artifact_run_id
from app.graph.graph import build_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="品牌广告分镜 Agent（LangGraph）")
    parser.add_argument(
        "brief",
        nargs="?",
        default="",
        help="品牌 / 产品 brief 文本；也可通过 stdin 传入",
    )
    args = parser.parse_args()
    brief = args.brief
    if not brief.strip() and not sys.stdin.isatty():
        brief = sys.stdin.read()
    brief = brief.strip()
    if not brief:
        print("请提供 brief：python -m app.run \"你的品牌与产品描述\"", file=sys.stderr)
        raise SystemExit(2)
    if not os.getenv("OPENAI_API_KEY"):
        print("缺少环境变量 OPENAI_API_KEY。", file=sys.stderr)
        raise SystemExit(2)

    graph = build_graph()
    result = graph.invoke(
        {
            "messages": [HumanMessage(content=brief)],
            "artifact_run_id": new_artifact_run_id(),
        }
    )
    if result.get("errors"):
        print("运行结束（含错误）：", result["errors"], file=sys.stderr)
        raise SystemExit(1)
    print(result.get("final_video_path", ""))


if __name__ == "__main__":
    main()
