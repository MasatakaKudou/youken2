"""「変換前のコメントが見えている時間」を実測する。

コメントを API で投稿した時刻から、本文が書き換わったのを確認できた時刻までを測る。
使い方：python3 measure_display.py owner/repo 1 20   （リポジトリ、Issue/PR番号、回数）
結果：logs/display.jsonl と、p50 / p99 を表示
"""
import json, os, sys, time, urllib.request

TOKEN = os.environ["GITHUB_TOKEN"]
repo, number, n = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 20
API = "https://api.github.com"
H = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json",
     "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"}
SAMPLES = ["ここバグってる", "この変数名わかりにくい", "テストがない", "ここ重複してる", "このループ遅い"]


def req(method, url, body=None):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, method=method, headers=H)
    with urllib.request.urlopen(r, timeout=15) as res:
        return json.load(res)


os.makedirs("logs", exist_ok=True)
results = []
for i in range(n):
    text = SAMPLES[i % len(SAMPLES)]
    t0 = time.time()
    c = req("POST", f"{API}/repos/{repo}/issues/{number}/comments", {"body": text})
    while True:
        time.sleep(0.1)
        if req("GET", c["url"])["body"] != text:
            break
        if time.time() - t0 > 60:
            print("timeout"); break
    sec = round(time.time() - t0, 3)
    results.append(sec)
    with open("logs/display.jsonl", "a") as f:
        f.write(json.dumps({"i": i, "original": text, "visible_sec": sec}, ensure_ascii=False) + "\n")
    print(f"{i+1}/{n}  {text}  {sec}s")
    time.sleep(10)  # 無料枠の1分あたりの回数制限に当たらないよう間を空ける

s = sorted(results)
p = lambda q: s[min(len(s) - 1, int(round(q * (len(s) - 1))))]
print(f"\n変換前コメントの表示時間  p50={p(0.5)}s  p99={p(0.99)}s  （n={len(s)}）")
print("※ポーリング間隔0.1秒とAPIの往復時間を含む")
