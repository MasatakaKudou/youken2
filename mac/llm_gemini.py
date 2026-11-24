"""Gemini API（無料枠）で変換と判定をする。標準ライブラリだけで動く。"""
import json, os, time, urllib.request, urllib.error

API_KEY = os.environ["GEMINI_API_KEY"]
# 無料枠で使えるモデル名は Google AI Studio で確認して、環境変数で指定する
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
TIMEOUT = float(os.environ.get("GEMINI_TIMEOUT", "10"))
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def _call(system, text, json_mode=False, temperature=0.7, retries=3):
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {"temperature": temperature},
    }
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                d = json.load(r)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and i < retries - 1:  # 回数制限・混雑。少し待って再試行
                wait = 5 * (i + 1)
                print(f"  [Gemini] {e.code}（{'回数制限' if e.code == 429 else '混雑'}）→ {wait}秒待って再試行", flush=True)
                time.sleep(wait); continue
            raise
        except (TimeoutError, OSError) as e:  # 応答が返ってこない。すぐ再試行
            if i < retries - 1:
                print(f"  [Gemini] {TIMEOUT}秒応答なし → 再試行", flush=True); continue
            raise


def convert(system, text):
    return _call(system, text)


def judge(system, text):
    out = _call(system, text, json_mode=True, temperature=0)
    try:
        return bool(json.loads(out)["praise"])
    except Exception:
        return False  # 判定できないものは「褒めていない」扱い（安全側）
