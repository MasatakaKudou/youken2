"""#2 実測キットのセットアップ（1回だけ実行）

やること：
  1. GitHubのトークンとGeminiのAPIキーを聞いて .env に保存（画面には表示しない）
  2. smee.io のチャンネルを作る
  3. テスト用リポジトリに Webhook を登録する
  4. テスト用の Issue と、SQLインジェクションを含む PR を作る
  5. Gemini と GitHub に接続できるか確認する

使い方：python3 setup.py
"""
import getpass, json, os, secrets, sys, base64, urllib.request, urllib.error

API = "https://api.github.com"


def ask(label, secret=False, default=""):
    p = f"{label}{f' [{default}]' if default else ''}: "
    v = (getpass.getpass(p) if secret else input(p)).strip()
    return v or default


def gh(method, path, token, body=None, accept="application/vnd.github+json"):
    r = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                               method=method, headers={"Authorization": f"Bearer {token}", "Accept": accept,
                                                       "X-GitHub-Api-Version": "2022-11-28",
                                                       "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=20) as res:
            t = res.read()
            return json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        print(f"\nGitHub API エラー {e.code} {method} {path}\n{e.read().decode()[:400]}")
        sys.exit(1)


def main():
    print("== #2 実測キットのセットアップ ==\n")
    env = {}
    if os.path.exists(".env"):
        for line in open(".env"):
            if line.startswith("export ") and "=" in line:
                k, v = line[7:].strip().split("=", 1); env[k] = v
        print(".env が見つかったので、未入力の項目だけ聞きます。\n")

    env.setdefault("GITHUB_REPO", ask("テスト用リポジトリ（例：kudo/youken02-test）"))
    if "GITHUB_TOKEN" not in env:
        env["GITHUB_TOKEN"] = ask("GitHubのトークン（入力は表示されません）", secret=True)
    if "GEMINI_API_KEY" not in env:
        env["GEMINI_API_KEY"] = ask("GeminiのAPIキー（入力は表示されません）", secret=True)
    env.setdefault("GEMINI_MODEL", ask("Geminiのモデル名（AI Studioで確認）", default="gemini-flash-lite-latest"))
    env.setdefault("WEBHOOK_SECRET", secrets.token_hex(24))
    tok, repo = env["GITHUB_TOKEN"], env["GITHUB_REPO"]

    # 1. GitHub 接続確認
    info = gh("GET", f"/repos/{repo}", tok)
    base = info["default_branch"]
    print(f"\n[OK] GitHub：{repo}（デフォルトブランチ {base}）")

    # 2. smee チャンネル
    if "SMEE_URL" not in env:
        with urllib.request.urlopen("https://smee.io/new", timeout=20) as r:
            env["SMEE_URL"] = r.geturl()
    print(f"[OK] smee：{env['SMEE_URL']}")

    # 3. Webhook 登録（同じ smee URL のものがなければ作る）
    hooks = gh("GET", f"/repos/{repo}/hooks", tok)
    if not any(h.get("config", {}).get("url") == env["SMEE_URL"] for h in hooks):
        gh("POST", f"/repos/{repo}/hooks", tok, {
            "name": "web", "active": True, "events": ["issue_comment", "pull_request_review_comment"],
            "config": {"url": env["SMEE_URL"], "content_type": "json", "secret": env["WEBHOOK_SECRET"]}})
    print("[OK] Webhook を登録しました（Issue comments / Pull request review comments）")

    # 4. テスト用 Issue と PR
    if "ISSUE_NUMBER" not in env:
        iss = gh("POST", f"/repos/{repo}/issues", tok, {"title": "レビューコメント変換テスト",
                                                       "body": "手元デモと表示時間の計測に使うIssueです。"})
        env["ISSUE_NUMBER"] = str(iss["number"])
    print(f"[OK] テスト用 Issue：#{env['ISSUE_NUMBER']}")
    if "PR_NUMBER" not in env:
        sha = gh("GET", f"/repos/{repo}/git/ref/heads/{base}", tok)["object"]["sha"]
        branch = "feature/user-search"
        gh("POST", f"/repos/{repo}/git/refs", tok, {"ref": f"refs/heads/{branch}", "sha": sha})
        code = ('// ユーザー検索API\n'
                'app.get("/users/search", async (req, res) => {\n'
                '  const sql = "SELECT * FROM users WHERE name = \'" + req.query.name + "\'";\n'
                '  const rows = await db.query(sql);\n'
                '  res.json(rows);\n'
                '});\n')
        gh("PUT", f"/repos/{repo}/contents/src/userSearch.js", tok, {
            "message": "ユーザー検索APIを追加", "branch": branch, "content": base64.b64encode(code.encode()).decode()})
        pr = gh("POST", f"/repos/{repo}/pulls", tok, {"title": "ユーザー検索APIを追加", "head": branch, "base": base,
                                                     "body": "名前でユーザーを検索するAPIを追加しました。"})
        env["PR_NUMBER"] = str(pr["number"])
    print(f"[OK] テスト用 PR：#{env['PR_NUMBER']}（SQLインジェクションを含む）")

    # .env 保存（自分だけが読める権限）
    with open(".env", "w") as f:
        for k, v in env.items():
            f.write(f"export {k}={v}\n")
    os.chmod(".env", 0o600)
    print("[OK] .env を保存しました（権限 600）")

    # 5. Gemini 接続確認
    os.environ.update(env)
    import llm_gemini as llm
    from prompts import CONVERT_V12, JUDGE
    out = llm.convert(CONVERT_V12, "ここバグってる")
    print(f"[OK] Gemini：「ここバグってる」→「{out}」（判定：{'褒め' if llm.judge(JUDGE, out) else '褒めていない'}）")
    print("\nセットアップ完了。次は ./start.sh でサーバーを起動してください。")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
