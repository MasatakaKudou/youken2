"""LLMの応答時間を測る。使い方：source .env && python3 bench_llm.py [並列数]"""
import time
import llm
from prompts import CONVERT_V12, JUDGE

import sys
from concurrent.futures import ThreadPoolExecutor
print(f"backend={llm.BACKEND} model={llm.MODEL}")
par = int(sys.argv[1]) if len(sys.argv) > 1 else 1
if par > 1:
    def one(i):
        t0 = time.time(); out = llm.convert(CONVERT_V12, "ここバグってる"); t1 = time.time(); ok = llm.judge(JUDGE, out)
        return f"{i+1}: 変換 {t1-t0:.2f}s / 判定 {time.time()-t1:.2f}s  {'褒め' if ok else '褒めていない'}  {out[:30]}"
    t0 = time.time()
    with ThreadPoolExecutor(par) as ex:
        for line in ex.map(one, range(par * 2)): print(line)
    print(f"{par * 2}件を並列{par}で {time.time()-t0:.1f}s"); sys.exit()
for i in range(5):
    t0 = time.time(); out = llm.convert(CONVERT_V12, "ここバグってる"); t1 = time.time()
    ok = llm.judge(JUDGE, out); t2 = time.time()
    print(f"{i+1}: 変換 {t1-t0:.2f}s / 判定 {t2-t1:.2f}s  {'褒め' if ok else '褒めていない'}  {out[:30]}")
    time.sleep(8 if llm.BACKEND == 'gemini' else 0)  # Gemini の無料枠は回数制限があるので間を空ける
