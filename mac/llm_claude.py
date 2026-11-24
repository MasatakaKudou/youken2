"""Claude Code のヘッドレスモード（claude -p）で変換と判定をする。

工藤さんの Claude のプランの範囲で動くので、APIキーも追加の料金も要らない。
（プランの利用上限には数えられる）
並列で呼べるよう、1回ごとに別プロセスで起動する。
"""
import json, os, re, subprocess, tempfile, time

MODEL = os.environ.get("CLAUDE_MODEL", "haiku")
TIMEOUT = float(os.environ.get("CLAUDE_TIMEOUT", "60"))
_cwd = tempfile.mkdtemp(prefix="youken2-llm-")  # リポジトリのファイルを読みに行かないよう、空のフォルダで動かす
stats = {"requests": 0, "errors": 0}


def _call(system, text):
    stats["requests"] += 1
    cmd = ["claude", "-p", "--model", MODEL, "--max-turns", "1", "--system-prompt", system, text]
    for i in range(2):
        r = subprocess.run(cmd, cwd=_cwd, capture_output=True, text=True, timeout=TIMEOUT)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
        stats["errors"] += 1
        print(f"  [Claude] 失敗（終了コード {r.returncode}）：{(r.stderr or r.stdout).strip()[:200]}", flush=True)
        time.sleep(3)
    raise RuntimeError("claude -p が失敗しました")


def convert(system, text):
    return _call(system, text)


def judge(system, text):
    out = _call(system, text)
    m = re.search(r"\{.*?\}", out, re.S)
    try:
        return bool(json.loads(m.group(0))["praise"])
    except Exception:
        return False  # 判定できないものは「褒めていない」扱い（安全側）
