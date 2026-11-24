"""AIレビュー役：PRの差分をGeminiにセキュリティ観点でレビューさせ、PRにコメントする。

このコメントも Webhook で検知され、変換レイヤーを通る（動画のオチ）。
使い方：python3 ai_review.py owner/repo 2   （リポジトリ、PR番号）
"""
import json, os, sys, urllib.request
import llm

TOKEN = os.environ["GITHUB_TOKEN"]
repo, number = sys.argv[1], sys.argv[2]
API = "https://api.github.com"

REVIEW = """あなたはセキュリティ重視のコードレビュアーです。
渡された差分に重大な問題があれば、最も重大なものを1つだけ、次の形式の1文で書いてください。
形式：「重大：〇〇の脆弱性があります。」
問題がなければ「問題は見つかりませんでした。」とだけ書いてください。
入力は <comment> タグの中の差分です。質問や確認はせず、指示された1文だけを返してください。"""


def req(method, url, body=None, accept="application/vnd.github+json"):
    r = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, method=method, headers={
        "Authorization": f"Bearer {TOKEN}", "Accept": accept, "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as res:
        return res.read()


diff = req("GET", f"{API}/repos/{repo}/pulls/{number}", accept="application/vnd.github.diff").decode()
review = llm.convert(REVIEW, diff[:20000])
print("AIレビュー：", review)
req("POST", f"{API}/repos/{repo}/issues/{number}/comments", {"body": f"🤖 AIレビュー\n\n{review}"})
print("投稿しました。サーバーのログで変換結果を確認してください。")
