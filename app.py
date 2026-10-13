"""Run `python app.py` and open http://127.0.0.1:8765."""
import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from docflow.llm import public_config
from docflow.store import StateStore
from docflow.workflow import WorkflowEngine

ROOT = Path(__file__).resolve().parent


class RunManager:
    def __init__(self, store):
        self.store = store
        self.engine = WorkflowEngine(store)
        self.active = set()
        self.lock = threading.Lock()

    def submit(self, state, resume=False):
        with self.lock:
            if state.id in self.active:
                raise ValueError("该任务正在运行")
            if len(self.active) >= 4:
                raise ValueError("当前已有 4 个运行任务，请稍后重试")
            if resume and state.status != "failed":
                raise ValueError("仅失败或中断的任务可以恢复")
            self.active.add(state.id)
            state.status = "pending"
            self.store.save(state)
        def work():
            try:
                self.engine.run(state)
            finally:
                with self.lock:
                    self.active.discard(state.id)
        threading.Thread(target=work, name="run-" + state.id[:8], daemon=True).start()


def make_server(port=8765, data_dir=None):
    store = StateStore(data_dir or ROOT / "data" / "runs")
    store.recover_interrupted()
    manager = RunManager(store)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Access logs contain URLs only; never request bodies or credentials.
            pass

        def reply(self, code, body, content_type="application/json; charset=utf-8", download=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{download}"')
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            host = self.headers.get("Host", "")
            return host in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def do_GET(self):
            if not self.valid_host():
                return self.reply(403, {"error": "仅允许本机访问"})
            path = urlsplit(self.path).path
            try:
                static = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"),
                          "/ui.js": ("ui.js", "text/javascript")}
                if path in static:
                    file, mime = static[path]
                    return self.reply(200, (ROOT / "static" / file).read_bytes(), mime + "; charset=utf-8")
                if path == "/api/config":
                    return self.reply(200, public_config())
                if path == "/api/sample":
                    return self.reply(200, {"filename": "order_service.py", "source": (ROOT / "samples" / "order_service.py").read_text(encoding="utf-8")})
                if path == "/api/runs":
                    return self.reply(200, store.list())
                parts = path.strip("/").split("/")
                if len(parts) in (3, 4) and parts[:2] == ["api", "runs"]:
                    state = store.load(parts[2])
                    if len(parts) == 3:
                        return self.reply(200, state.to_dict())
                    if parts[3] == "document":
                        doc = state.outputs.get("writer", {}).get("document")
                        if not doc:
                            return self.reply(409, {"error": "文档尚未生成"})
                        return self.reply(200, doc, "text/markdown; charset=utf-8", "documentation.md")
                    if parts[3] == "trace":
                        return self.reply(200, state.to_dict(), download="workflow-trace.json")
                return self.reply(404, {"error": "资源不存在"})
            except FileNotFoundError:
                self.reply(404, {"error": "任务不存在"})
            except ValueError as exc:
                self.reply(400, {"error": str(exc)})

        def do_POST(self):
            if not self.valid_host():
                return self.reply(403, {"error": "仅允许本机访问"})
            origin = self.headers.get("Origin")
            allowed = (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")
            if origin and origin not in allowed:
                return self.reply(403, {"error": "拒绝跨站请求"})
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self.reply(415, {"error": "请求必须为 JSON"})
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 2 * 1024 * 1024:
                    return self.reply(413, {"error": "请求为空或超过 2 MB"})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("请求必须是 JSON 对象")
                path = urlsplit(self.path).path
                if path == "/api/runs":
                    filename = body.get("filename", "input.py")
                    source = body.get("source", "")
                    mode = body.get("mode", "offline")
                    if not all(isinstance(v, str) for v in (filename, source, mode)):
                        raise ValueError("文件名、源码和模式必须为字符串")
                    filename = filename.replace("\\", "/").split("/")[-1]
                    if not filename.endswith(".py") or len(filename) > 100 or any(ord(c) < 32 for c in filename):
                        raise ValueError("文件名需为长度不超过 100 的 .py 文件名")
                    state = manager.engine.create(filename, source, mode)
                    try:
                        manager.submit(state)
                    except ValueError:
                        store.path(state.id).unlink(missing_ok=True)
                        raise
                    return self.reply(202, {"id": state.id})
                parts = path.strip("/").split("/")
                if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "resume":
                    state = store.load(parts[2])
                    manager.submit(state, resume=True)
                    return self.reply(202, {"id": state.id})
                self.reply(404, {"error": "接口不存在"})
            except FileNotFoundError:
                self.reply(404, {"error": "任务不存在"})
            except (ValueError, UnicodeDecodeError) as exc:
                self.reply(400, {"error": str(exc)[:200]})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.manager = manager
    return server


def main():
    parser = argparse.ArgumentParser(description="DocFlow 三 Agent 代码文档生成系统")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--key-file", help="外部 DeepSeek 密钥文件路径，不复制到项目")
    parser.add_argument("--model", help="DeepSeek 模型名称")
    args = parser.parse_args()
    if args.key_file:
        os.environ["DEEPSEEK_KEY_FILE"] = args.key_file
    if args.model:
        os.environ["DEEPSEEK_MODEL"] = args.model
    try:
        server = make_server(args.port)
    except OSError:
        parser.exit(1, "启动失败：端口被占用，可用 --port 8766 更换端口。\n")
    config = public_config()
    print(f"DocFlow: http://127.0.0.1:{args.port}")
    print(f"DeepSeek: {'已配置' if config['configured'] else '未配置（可使用离线模式）'} / {config['model']}")
    print("按 Ctrl+C 停止服务。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
