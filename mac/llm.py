"""LLM の切り替え口。環境変数 LLM_BACKEND=claude（初期値）か gemini。"""
import os
if os.environ.get("LLM_BACKEND", "claude") == "gemini":
    from llm_gemini import *  # noqa
    from llm_gemini import MODEL, stats  # noqa
else:
    from llm_claude import *  # noqa
    from llm_claude import MODEL, stats  # noqa
BACKEND = os.environ.get("LLM_BACKEND", "claude")
