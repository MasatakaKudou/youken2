"""Webhookを受けて、コメントを褒め言葉に変換し、PATCHで上書きするサーバー。

smee.io から転送された GitHub の Webhook を受ける。
対象：issue_comment / pull_request_review_comment の created（AIレビューのコメントも含む）
ログ：logs/server.jsonl に1件1行のJSONで残す
"""
import hashlib, hmac, json, os, time, urllib.request, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from prompts import CONVERT_V12, JUDGE
import llm

GH_TOKEN = os.environ["GITHUB_TOKEN"]
SECRET = os.environ.get("WEBHOOK_SECRET", "").encode()
PORT = int(os.environ.get("PORT", "3000"))
MAX_ATTEMPTS = 3
os.makedirs("logs", exist_ok=True)
lock = threading.Lock()


def log(rec):
    with lock, open("logs/server.jsonl", "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def patch_comment(url, body):
    req = urllib.request.Request(url, data=json.dumps({"body": body}).encode(), method="PATCH", headers={
        "Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()


def handle(event, payload, t_recv):
    c = payload["comment"]
    original = c["body"]
    rec = {"event": event, "comment_id": c["id"], "author": c["user"]["login"], "original": original,
           "t_received": t_recv}
    attempts = []
    for i in range(MAX_ATTEMPTS):
        t0 = time.time()
        converted = llm.convert(CONVERT_V12, original)
        ok = llm.judge(JUDGE, converted)
        attempts.append({"converted": converted, "praise": ok, "sec": round(time.time() - t0, 3)})
        if ok:
            break
    final = attempts[-1]["converted"]
    patch_comment(c["url"], final)
    rec.update({"attempts": attempts, "final": final, "praise": attempts[-1]["praise"],
                "t_patched": time.time()})
    rec["server_latency_sec"] = round(rec["t_patched"] - t_recv, 3)
    log(rec)
    print(f'[{c["id"]}] {original!r} -> {final!r}  ({rec["server_latency_sec"]}s, 試行{len(attempts)}回)')


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        t_recv = time.time()
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if SECRET:
            sig = "sha256=" + hmac.new(SECRET, raw, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, self.headers.get("X-Hub-Signature-256", "")):
                self.send_response(401); self.end_headers(); return
        self.send_response(202); self.end_headers()
        event = self.headers.get("X-GitHub-Event", "")
        payload = json.loads(raw)
        # 上書き（edited）で再度変換しないよう、created だけを対象にする
        if event in ("issue_comment", "pull_request_review_comment") and payload.get("action") == "created":
            threading.Thread(target=handle, args=(event, payload, t_recv), daemon=True).start()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"listening on :{PORT}  model={llm.MODEL}")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
