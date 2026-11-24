#!/bin/bash
# 計測とオチを実行する（start.sh を別のターミナルで動かしたまま使う）
#   ./run.sh display   … 変換前コメントの表示時間を20回測る
#   ./run.sh review    … AIレビューにPRをレビューさせる（オチ）
cd "$(dirname "$0")"
source .env
case "$1" in
  display) python3 measure_display.py "$GITHUB_REPO" "$ISSUE_NUMBER" "${2:-20}" ;;
  review)  python3 ai_review.py "$GITHUB_REPO" "$PR_NUMBER" ;;
  *) echo "使い方：./run.sh display | ./run.sh review" ;;
esac
