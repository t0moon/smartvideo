from __future__ import annotations

import argparse
import os
import sys

from runtime.workflow import WorkflowRuntime
from project.service import ProjectService
from channels.manager import init_channel_system


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartVideo Platform - Enterprise AI Video Production")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # run
    run_p = sub.add_parser("run", help="Run a video production pipeline")
    run_p.add_argument("brief", nargs="?", default="", help="Brand/product brief text")
    run_p.add_argument("--name", "-n", default="Untitled", help="Project name")
    run_p.add_argument("--project", "-p", default="", help="Existing project ID (resume)")
    run_p.add_argument("--engine", choices=["v1", "v2"], default="v2",
                        help="Pipeline engine: v1 = hardcoded, v2 = YAML-driven (default)")
    run_p.add_argument("--workflow", "-w", default="product_ad",
                        help="Workflow template name (v2 only), e.g. product_ad")

    # project
    proj_p = sub.add_parser("project", help="Project management")
    proj_p.add_argument("action", choices=["list", "get", "delete"])
    proj_p.add_argument("project_id", nargs="?", default="", help="Project ID")

    args = parser.parse_args()

    if args.command == "run":
        brief = args.brief
        if not brief.strip() and not sys.stdin.isatty():
            brief = sys.stdin.read()
        brief = brief.strip()
        if not brief:
            print("Error: provide a brief via argument or stdin", file=sys.stderr)
            sys.exit(2)
        if not os.getenv("OPENAI_API_KEY"):
            print("Error: OPENAI_API_KEY not set", file=sys.stderr)
            sys.exit(2)

        # Initialize channel system so pipeline pauses send IM notifications
        init_channel_system()

        svc = ProjectService()
        if args.project:
            project = svc.get_project(args.project)
            print(f"Resuming project: {project.name} ({project.project_id})")
        else:
            project = svc.create_project(name=args.name, brief=brief)
            print(f"Created project: {project.name} ({project.project_id})")

        runtime = WorkflowRuntime()
        if args.engine == "v2":
            final_path = runtime.run_pipeline_v2(project.project_id, brief, args.workflow)
        else:
            final_path = runtime.run_pipeline(project.project_id, brief)
        if final_path:
            print(f"\nFinal video: {final_path}")
        else:
            print("\nPipeline completed with errors", file=sys.stderr)
            sys.exit(1)

    elif args.command == "project":
        svc = ProjectService()
        if args.action == "list":
            for p in svc.list_projects():
                print(f"{p.project_id:30s} {p.stage.value:15s} {p.name}")
        elif args.action == "get":
            p = svc.get_project(args.project_id)
            print(f"ID:      {p.project_id}")
            print(f"Name:    {p.name}")
            print(f"Stage:   {p.stage.value}")
            print(f"Created: {p.created_at}")
        elif args.action == "delete":
            svc.delete_project(args.project_id)
            print(f"Deleted project: {args.project_id}")


if __name__ == "__main__":
    main()
