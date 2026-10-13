import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from app import make_server


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = make_server(0, Path(cls.temp.name))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, body=None, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        request = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=5) as response:
            return response.status, response.read(), response.headers

    def wait_run(self, run_id):
        for _ in range(100):
            state = json.loads(self.request("/api/runs/" + run_id)[1])
            if state["status"] not in ("pending", "running"):
                return state
            time.sleep(0.02)
        self.fail("任务未在期限内结束")

    def test_api_end_to_end_and_exports(self):
        sample = json.loads(self.request("/api/sample")[1])
        code, body, _ = self.request("/api/runs", {**sample, "mode": "offline"})
        self.assertEqual(code, 202)
        run_id = json.loads(body)["id"]
        state = self.wait_run(run_id)
        self.assertEqual(state["status"], "completed")
        _, doc, headers = self.request(f"/api/runs/{run_id}/document")
        self.assertIn("calculate_total", doc.decode())
        self.assertIn("attachment", headers["Content-Disposition"])
        trace = json.loads(self.request(f"/api/runs/{run_id}/trace")[1])
        self.assertEqual(len(trace["messages"]), 3)

    def test_invalid_request_and_cross_origin_block(self):
        for body in ([1], {"filename": "bad.txt", "source": "a=1"}, {"filename": "x.py", "source": 4}):
            with self.assertRaises(urllib.error.HTTPError) as exc:
                self.request("/api/runs", body)
            self.assertEqual(exc.exception.code, 400)
        with self.assertRaises(urllib.error.HTTPError) as exc:
            self.request("/api/runs", {"source": "a=1"}, origin="https://example.org")
        self.assertEqual(exc.exception.code, 403)

    def test_failed_run_resume_endpoint(self):
        run_id = json.loads(self.request("/api/runs", {"filename": "bad.py", "source": "def broken(:"})[1])["id"]
        self.assertEqual(self.wait_run(run_id)["status"], "failed")
        self.assertEqual(self.request(f"/api/runs/{run_id}/resume", {})[0], 202)
        # An unchanged syntax error is correctly still a failure, not fake recovery.
        state = self.wait_run(run_id)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["attempts"]["analyzer"], 2)

    def test_static_page_and_config_does_not_expose_secret(self):
        page = self.request("/")[1].decode()
        self.assertIn("DocFlow", page)
        config = json.loads(self.request("/api/config")[1])
        self.assertEqual(set(config), {"configured", "provider", "model", "default_mode"})


if __name__ == "__main__":
    unittest.main()
