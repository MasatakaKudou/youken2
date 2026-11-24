# youken2：#2 褒め言葉変換基盤の実測キット

YouTubeチャンネル「要件定義からやります」#2の検証用リポジトリです。

※ `src/userSearch.js` はわざとSQLインジェクションを含むデモ用コードです（setup.py が PR として作成）。本番では使わないでください。

すべて無料で動く構成です。工藤さんの操作は、アカウントが必要な部分（キーの発行とColab）と、コマンド数行だけです。

| 何を測るか | どこで動かすか |
|---|---|
| 100回変換・判定の精度・負荷試験・カナリア | Google Colab（無料GPU）：`colab/youken02_batch.ipynb` |
| Webhookで検知して上書き・表示時間・AIレビューのオチ | Mac：`mac/`（LLMは Gemini API 無料枠） |
| 冒頭の手元デモ | Mac の Claude Code：`.claude/skills/soften-review/` |

---

## 手順1：キーを2つ用意する（ブラウザで約5分）

### GitHub
1. テスト用リポジトリ：`MasatakaKudou/youken2`（このキットを push したもの）
2. Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
   - Repository access：**Only select repositories** でテスト用リポジトリだけを選ぶ
   - Permissions（Repository）：
     - Contents：Read and write
     - Issues：Read and write
     - Pull requests：Read and write
     - Webhooks：Read and write
   - 生成されたトークンをコピー（チャットには貼らない）

### Gemini
1. Google AI Studio（aistudio.google.com）で「Get API key」→ キーを作成してコピー。**課金設定はしない**
2. AI Studio のモデル一覧で、無料で使えるモデル名（Flash-Lite 系など）を確認しておく
   - 無料枠では、送った内容が Google の改善に使われます。テスト用のコメント以外は送らないでください

## 手順2：Mac でセットアップ（コマンド1つ）

ターミナルで、クローンしたリポジトリの `mac` に移動して実行します。

```bash
cd youken2/mac
python3 setup.py
```

聞かれたら、リポジトリ名（`MasatakaKudou/youken2`）、トークン、APIキー、モデル名を入力します。トークンとキーは画面に表示されません。

`setup.py` が自動でやること：
- `.env` に保存（自分だけが読める権限）
- smee.io のチャンネルを作り、テスト用リポジトリに Webhook を登録
- テスト用の Issue と、SQLインジェクションを含む PR を作成
- Gemini で「ここバグってる」を1回変換して、つながるか確認

最後に「セットアップ完了」と出れば OK です。エラーが出たら、そのまま Claude に貼ってください（トークンやキーは出力に含まれません）。

## 手順3：Mac でデモと計測

**ターミナル1**（撮影と計測のあいだ、ずっと動かしておく）
```bash
./start.sh
```
表示された Issue の URL をブラウザで開き、「ここバグってる」とコメントすると、数秒で褒め言葉に書き換わります。**手元デモ2か所目の撮影はここ**です。

**ターミナル2**
```bash
./run.sh display    # 変換前コメントの表示時間を20回測る（約2分）
./run.sh review     # AIレビューがPRをレビュー → 褒め言葉に変換される（オチ）
```
オチの画面は、PR のページを開いたまま `./run.sh review` を実行して撮影します。

## 手順4：Colab で一括の実測（ブラウザ）

1. colab.research.google.com で `colab/youken02_batch.ipynb` をアップロードして開く
2. 「ランタイム」→「ランタイムのタイプを変更」→ **T4 GPU** → 保存
3. 実験B の前に、`data/eval_candidates.csv` の **label 列を自分で付ける**（praise か cold）。label_draft は Claude の下書きなので、そのまま写さない
4. 「ランタイム」→「すべてのセルを実行」。実験B ではCSVのアップロードを求められる
5. 実験C は、まず `N = 100` に書き換えて速度を見てから増やすと安全
6. 最後のセルで `results.zip` がダウンロードされる

GPU が割り当てられないときは、時間をおいてやり直してください。

## 手順5：冒頭の手元デモ（スキル）

スキルはリポジトリの `.claude/skills/soften-review/` に入っています。クローンしたフォルダで Claude Code を開き、 `/soften-review ここバグってる` を実行して撮影します。入力してから結果が出るまでの秒数を測っておいてください。

## 終わったら Claude に渡すもの

- Colab の `results.zip`
- `mac/logs/server.jsonl` と `mac/logs/display.jsonl`
- 手元デモの動画2本と、スキルの作成時間
