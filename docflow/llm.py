"""Small DeepSeek client. Secrets stay in memory, outside the project."""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_KEY_FILE = r"D:\deepseek\api.txt"


def settings():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        path = Path(os.environ.get("DEEPSEEK_KEY_FILE", DEFAULT_KEY_FILE))
        if path.is_file():
            content = path.read_text(encoding="utf-8-sig").strip()
            found = re.search(r"sk-[A-Za-z0-9_-]+", content)
            if found:
                key = found.group(0)
    return key, os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"), \
        os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")


def public_config():
    key, base, model = settings()
    return {"configured": bool(key), "provider": "DeepSeek", "model": model,
            "default_mode": "ai" if key else "offline"}


def complete(system, data, json_output=False, with_metadata=False):
    key, base, model = settings()
    if not key:
        raise ValueError("未找到 DeepSeek API Key，请配置 DEEPSEEK_API_KEY 或 DEEPSEEK_KEY_FILE。")
    if not base.startswith("https://") and not base.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise ValueError("DeepSeek 服务地址需使用 HTTPS 或本机 HTTP。")
    body = {"model": model, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(data, ensure_ascii=False)}
    ], "stream": False, "max_tokens": 6000, "thinking": {"type": "disabled"}}
    request = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.loads(response.read(2 * 1024 * 1024))
        message = result["choices"][0]["message"]["content"]
        if not isinstance(message, str) or not message.strip():
            raise ValueError("DeepSeek 返回空内容")
        if result["choices"][0].get("finish_reason") == "length":
            raise ValueError("DeepSeek 输出达到长度上限，请减少源码长度后重试。")
        if json_output:
            cleaned = message.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
            message = json.loads(cleaned)
        metadata = {"provider": "DeepSeek", "model": result.get("model", model),
                    "request_id": result.get("id"), "usage": result.get("usage", {}),
                    "finish_reason": result["choices"][0].get("finish_reason")}
        return (message, metadata) if with_metadata else message
    except urllib.error.HTTPError as exc:
        hints = {401: "密钥无效", 402: "余额不足", 429: "请求过于频繁", 400: "请求参数或模型名不被接受"}
        raise RuntimeError(f"DeepSeek HTTP {exc.code}：{hints.get(exc.code, '服务请求失败')}。") from None
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        raise RuntimeError("DeepSeek 服务不可用或响应格式不符合要求，可点击恢复重试。") from None
