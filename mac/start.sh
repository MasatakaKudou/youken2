#!/bin/bash
# smee の転送と変換サーバーをまとめて起動する。止めるときは Ctrl+C
cd "$(dirname "$0")"
[ -f .env ] || { echo "先に python3 setup.py を実行してください"; exit 1; }
source .env
npx --yes smee-client --url "$SMEE_URL" --target http://127.0.0.1:3000/ &
SMEE_PID=$!
trap 'kill $SMEE_PID 2>/dev/null' EXIT
echo "Issue #$ISSUE_NUMBER にコメントすると、褒め言葉に書き換わります：https://github.com/$GITHUB_REPO/issues/$ISSUE_NUMBER"
python3 server.py
