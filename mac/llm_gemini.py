"""Gemini API（無料枠）で変換と判定をする。標準ライブラリだけで動く。

無料枠は応答が不安定（たまに10秒以上返ってこない、503で混雑）なので、
「ヘッジリクエスト」を使う：一定時間（HEDGE_AFTER秒）返ってこなければ、同じリクエストをもう1本送り、
先に返ってきたほうを使う。503 / 429 は少し待ってから送り直す。
"""
import json, os, time, urllib.request, urllib.error
from prompts import wrap
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
HEDGE_AFTER = float(os.environ.get("GEMINI_HEDGE_AFTER", "5"))  # この秒数で返ってこなければ2本目を送る
MAX_REQUESTS = int(os.environ.get("GEMINI_MAX_REQUESTS", "3"))     # 1回の呼び出しで送る最大本数
DEADLINE = float(os.environ.get("GEMINI_DEADLINE", "40"))         # 全体の打ち切り（秒）
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
_pool = ThreadPoolExecutor(16)
stats = {"requests": 0, "hedged": 0, "errors": 0}  # 計測用


def _once(body):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY})
    with urllib.request.urlopen(req, timeout=DEADLINE) as r:
        d = json.load(r)
    return d["candidates"][0]["content"]["parts"][0]["text"].strip()


def _call(system, text, json_mode=False, temperature=0.7):
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": wrap(text)}]}],
        "generationConfig": {"temperature": temperature},
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    t_end = time.time() + DEADLINE
    pending, sent, last_err = set(), 0, None

    def send():
        nonlocal sent
        pending.add(_pool.submit(_once, body)); sent += 1; stats["requests"] += 1

    send()
    while pending and time.time() < t_end:
        done, _ = wait(pending, timeout=HEDGE_AFTER, return_when=FIRST_COMPLETED)
        had_err = False
        for f in done:
            pending.discard(f)
            try:
                return f.result()
            except urllib.error.HTTPError as e:
                last_err = e; stats["errors"] += 1; had_err = True
                if e.code == 429:  # 回数制限：指定された秒数（なければ10秒）待つ
                    w = float(e.headers.get("Retry-After") or 10)
                    print(f"  [Gemini] 429（回数制限）→ {w:.0f}秒待って送り直し", flush=True); time.sleep(w)
                elif e.code in (500, 503):
                    print(f"  [Gemini] {e.code}（混雑）→ 2秒待って送り直し", flush=True); time.sleep(2)
                else:
                    raise
                if not pending:
                    t_end = max(t_end, time.time() + 15)  # 待った分、打ち切りを延ばす
            except Exception as e:  # タイムアウトや通信エラー
                last_err = e; stats["errors"] += 1; had_err = True
        if sent < MAX_REQUESTS and (not done or had_err):
            if not done:
                stats["hedged"] += 1
                print(f"  [Gemini] {HEDGE_AFTER}秒応答なし → ヘッジ（{sent + 1}本目）", flush=True)
            send()
    raise last_err or TimeoutError(f"Gemini: {DEADLINE}秒以内に応答がありませんでした")


def convert(system, text):
    return _call(system, text)


def judge(system, text):
    out = _call(system, text, json_mode=True, temperature=0)
    try:
        return bool(json.loads(out)["praise"])
    except Exception:
        return False  # 判定できないものは「褒めていない」扱い（安全側）
