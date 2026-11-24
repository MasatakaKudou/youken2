"""Gemini の応答時間を測る（変換と判定を5回ずつ）。使い方：source .env && python3 bench_gemini.py"""
import time
import llm_gemini as llm
from prompts import CONVERT_V12, JUDGE

print(f"model={llm.MODEL}")
for i in range(5):
    t0 = time.time(); out = llm.convert(CONVERT_V12, "ここバグってる"); t1 = time.time()
    ok = llm.judge(JUDGE, out); t2 = time.time()
    print(f"{i+1}: 変換 {t1-t0:.2f}s / 判定 {t2-t1:.2f}s  {'褒め' if ok else '褒めていない'}  {out[:30]}")
    time.sleep(8)  # 無料枠の1分あたりの回数制限に当たらないよう間を空ける
