"""一括の実測（Colab のノートブックと同じ実験を、Mac から Claude で並列に回す）

使い方：source .env && python3 batch.py 実験 [オプション]
  A        同じ指摘をスキル相当のプロンプトで変換し、褒め言葉になっていない回数を数える（既定100回）
  A2       実験Aの出力を「冷たい言い方か」で判定し直す（変換はやり直さない）
  B        判定LLMの精度（data/eval_candidates.csv の label 列を工藤さんが付けてから）
  C        負荷試験：褒め率、変換 p99、重複率（既定200件）
  D        カナリア：v13 を 5% に配信し、バーンレートで自動ロールバック
例：python3 batch.py A --n 100 --par 4
結果は results/ に JSON で保存する。
"""
import argparse, csv, json, os, random, threading, time
from concurrent.futures import ThreadPoolExecutor
import llm
from prompts import CONVERT_V12, CONVERT_V13, SOFTEN_SKILL, JUDGE, JUDGE_COLD

os.makedirs("results", exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))


def save(name, obj):
    obj = {"backend": llm.BACKEND, "model": llm.MODEL, **obj}
    json.dump(obj, open(f"results/{name}.json", "w"), ensure_ascii=False, indent=1)
    print(f"→ results/{name}.json に保存しました")


def pct(xs, q):
    s = sorted(xs); return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def convert_and_judge(text, prompt=CONVERT_V12, max_attempts=3):
    t0 = time.time(); tries = []
    for _ in range(max_attempts):
        out = llm.convert(prompt, text); ok = llm.judge(JUDGE, out); tries.append({"out": out, "praise": ok})
        if ok:
            break
    return {"input": text, "final": tries[-1]["out"], "praise": tries[-1]["praise"],
            "attempts": len(tries), "sec": time.time() - t0, "tries": tries}


TARGETS = ["ここ", "この関数", "この変数名", "このループ", "このSQL", "この例外処理", "このif文", "このテスト", "このコメント", "このクラス",
           "この定数", "このAPI呼び出し", "このマジックナンバー", "このnullチェック", "このログ出力", "この正規表現", "この依存関係",
           "このタイムアウト値", "このキャッシュ", "このリトライ処理"]
PROBLEMS = ["バグってる", "意味がわからない", "重複してる", "遅い", "読みにくい", "名前が微妙", "テストがない", "不要では", "責務が多すぎる",
            "エラーを握りつぶしてる", "型が違う", "境界値が漏れてる", "N+1になってる", "競合しそう", "メモリリークしそう", "命名規則と違う",
            "ハードコードされてる", "副作用がある", "戻り値を見てない", "ネストが深い", "古い書き方", "セキュリティ的に危ない", "ログが多すぎる",
            "コメントと実装が違う", "直して"]
POOL = [f"{t}、{p}{s}" for t in TARGETS for p in PROBLEMS for s in ["", "。", "。直して", "？"]]


def exp_a(n, par):
    t0 = time.time(); done = [0]
    def one(i):
        out = llm.convert(SOFTEN_SKILL, "ここバグってる"); r = {"i": i, "out": out, "praise": llm.judge(JUDGE, out)}
        done[0] += 1
        if done[0] % 10 == 0:
            print(f"  {done[0]}/{n}回  経過 {time.time() - t0:.0f}s", flush=True)
        return r
    with ThreadPoolExecutor(par) as ex:
        outs = list(ex.map(one, range(n)))
    cold = [o for o in outs if not o["praise"]]
    print(f"冷たい言い方（褒めていない）：{len(cold)} / {n} 回")
    for o in cold[:10]:
        print("  ", o["i"], o["out"])
    save("A_variance", {"n": n, "cold": len(cold), "outs": outs})


def exp_a2(par):
    """実験Aの出力を、「冷たい言い方か」で判定し直す（変換はやり直さない）"""
    import re
    d = json.load(open("results/A_variance.json"))
    def one(o):
        out = llm.convert(JUDGE_COLD, o["out"])  # 中身は同じ呼び出し
        m = re.search(r"\{.*?\}", out, re.S)
        try: return bool(json.loads(m.group(0))["cold"])
        except Exception: return None
    with ThreadPoolExecutor(par) as ex:
        colds = list(ex.map(one, d["outs"]))
    for o, c in zip(d["outs"], colds): o["cold"] = c
    n_cold = sum(c is True for c in colds); n_unknown = sum(c is None for c in colds)
    print(f"褒め言葉になっていない：{d['cold']} / {d['n']} 回（判定：褒めているか）")
    print(f"冷たい言い方：{n_cold} / {d['n']} 回（判定：冷たいか）  判定できず：{n_unknown}")
    for o in [o for o in d["outs"] if o.get("cold")][:10]:
        print("  ", o["i"], o["out"])
    d.pop("backend", None); d.pop("model", None)
    save("A_variance", {**d, "cold_tone": n_cold})


def exp_b(par):
    rows = list(csv.DictReader(open(os.path.join(HERE, "..", "data", "eval_candidates.csv"), encoding="utf-8")))
    rows = [r for r in rows if r["label"].strip() in ("praise", "cold")]
    if not rows:
        print("label 列が空です。data/eval_candidates.csv に praise か cold を自分で付けてから実行してください。"); return
    with ThreadPoolExecutor(par) as ex:
        preds = list(ex.map(lambda r: llm.judge(JUDGE, r["text"]), rows))
    res = [{**r, "pred": "praise" if p else "cold"} for r, p in zip(rows, preds)]
    correct = sum(r["pred"] == r["label"] for r in res)
    missed = [r for r in res if r["label"] == "cold" and r["pred"] == "praise"]
    false_alarm = [r for r in res if r["label"] == "praise" and r["pred"] == "cold"]
    print(f"評価データ：{len(res)}件  正解率：{correct / len(res) * 100:.1f}%")
    print(f"冷たいのに「褒め」と判定：{len(missed)}件 / 褒めなのに「冷たい」と判定：{len(false_alarm)}件")
    for r in missed:
        print("  見逃し：", r["text"])
    save("B_eval", {"n": len(res), "accuracy": correct / len(res), "missed": missed, "false_alarm": false_alarm, "rows": res})


def exp_c(n, par):
    random.seed(42)
    comments = random.sample(POOL, n)
    t0 = time.time(); done = [0]
    def one(c):
        r = convert_and_judge(c); done[0] += 1
        if done[0] % 20 == 0:
            print(f"  {done[0]}/{n}件  経過 {time.time() - t0:.0f}s", flush=True)
        return r
    with ThreadPoolExecutor(par) as ex:
        load = list(ex.map(one, comments))
    wall = time.time() - t0
    praise_rate = sum(r["praise"] for r in load) / n
    secs = [r["sec"] for r in load]
    dup_rate = 1 - len({r["final"] for r in load}) / n
    print(f"件数：{n}  並列：{par}  所要：{wall / 60:.1f}分")
    print(f"褒め率：{praise_rate * 100:.2f}%  （褒めていないまま届いた：{n - sum(r['praise'] for r in load)}件）")
    print(f"変換（判定と再変換を含む） p50={pct(secs, .5):.2f}s  p99={pct(secs, .99):.2f}s")
    print(f"褒め言葉の重複率：{dup_rate * 100:.1f}%  再変換が起きた割合：{sum(r['attempts'] > 1 for r in load) / n * 100:.1f}%")
    save("C_load", {"n": n, "par": par, "wall_sec": wall, "praise_rate": praise_rate, "p50": pct(secs, .5),
                    "p99": pct(secs, .99), "dup_rate": dup_rate, "results": load})


def exp_d(par, warmup=30, max_sec=600, ratio=0.05, window=120, min_samples=3, slo=0.9999, threshold=14.4):
    events, lock = [], threading.Lock()
    st = {"canary": False, "rolled_back": False, "t_deploy": None, "t_rollback": None, "max_burn": 0}
    t_start = time.time()

    def worker(text):
        use_v13 = st["canary"] and not st["rolled_back"] and random.random() < ratio
        out = llm.convert(CONVERT_V13 if use_v13 else CONVERT_V12, text); ok = llm.judge(JUDGE, out)
        with lock:
            events.append({"t": time.time() - t_start, "version": "v13" if use_v13 else "v12", "praise": ok, "out": out})

    def monitor():
        while time.time() - t_start < max_sec and not st["rolled_back"]:
            time.sleep(1); now = time.time() - t_start
            if not st["canary"] and now >= warmup:
                st["canary"] = True; st["t_deploy"] = now; print(f"{now:6.1f}s  v13 を canary {ratio * 100:.0f}% に配信", flush=True)
            if not st["canary"]:
                continue
            with lock:
                win = [e for e in events if e["version"] == "v13" and e["t"] >= now - window]
            if len(win) < min_samples:
                continue
            burn = (1 - sum(e["praise"] for e in win) / len(win)) / (1 - slo); st["max_burn"] = max(st["max_burn"], burn)
            if burn > threshold:
                st["rolled_back"] = True; st["t_rollback"] = now
                print(f"{now:6.1f}s  ALERT バーンレート {burn:.1f}倍 → v12 にロールバック", flush=True)

    mon = threading.Thread(target=monitor); mon.start()
    with ThreadPoolExecutor(par) as ex:
        i = 0; pending = set()
        while mon.is_alive():
            pending = {f for f in pending if not f.done()}
            if len(pending) < par:
                pending.add(ex.submit(worker, POOL[i % len(POOL)])); i += 1
            time.sleep(0.05)
    mon.join()
    if st["t_rollback"]:
        print(f"配信からロールバックまで：{st['t_rollback'] - st['t_deploy']:.1f}秒")
    else:
        print("時間内にロールバックしませんでした")
    series = []
    for b in range(0, int(max(e["t"] for e in events)) + 10, 10):
        seg = [e for e in events if b <= e["t"] < b + 10]; v13 = [e for e in seg if e["version"] == "v13"]
        series.append({"t": b, "all_praise_rate": sum(e["praise"] for e in seg) / len(seg) if seg else None,
                       "canary_n": len(v13), "canary_praise_rate": sum(e["praise"] for e in v13) / len(v13) if v13 else None})
    save("D_canary", {**st, "ratio": ratio, "window_sec": window, "events": events, "series": series})


if __name__ == "__main__":
    os.chdir(HERE)
    ap = argparse.ArgumentParser()
    ap.add_argument("exp", choices=["A", "A2", "B", "C", "D"])
    ap.add_argument("--n", type=int)
    ap.add_argument("--par", type=int, default=4)
    a = ap.parse_args()
    print(f"backend={llm.BACKEND} model={llm.MODEL}  並列={a.par}（10件ごとに進み具合を表示します）", flush=True)
    t0 = time.time()
    if a.exp == "A": exp_a(a.n or 100, a.par)
    if a.exp == "A2": exp_a2(a.par)
    if a.exp == "B": exp_b(a.par)
    if a.exp == "C": exp_c(a.n or 200, a.par)
    if a.exp == "D": exp_d(a.par)
    print(f"LLM呼び出し：{llm.stats['requests']}回（失敗 {llm.stats['errors']}回）  所要 {time.time() - t0:.0f}s")
