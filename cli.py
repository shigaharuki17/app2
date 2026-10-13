"""Command-line workflow runner and exporter."""
import argparse
import json
from pathlib import Path
from docflow.store import StateStore
from docflow.workflow import WorkflowEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--mode", choices=["ai", "offline"], default="ai")
    parser.add_argument("--output", type=Path, default=Path("generated"))
    args = parser.parse_args()
    engine = WorkflowEngine(StateStore(Path(__file__).parent / "data" / "runs"))
    state = engine.create(args.source.name, args.source.read_text(encoding="utf-8-sig"), args.mode)
    engine.run(state)
    args.output.mkdir(parents=True, exist_ok=True)
    if state.outputs.get("writer"):
        (args.output / "documentation.md").write_text(state.outputs["writer"]["document"], encoding="utf-8")
    (args.output / "trace.json").write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"status={state.status}, id={state.id}, output={args.output}")
    if state.error:
        print(state.error)
    return 0 if state.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
