"""
prompt_library.py — Combi Prompt Library 로더

Combi는 Prompt Generator가 아니라 Execution Engine이다.
운영자가 승인한 prompts.json 만 읽어서 그대로 실행한다. (PRD 6장)
"""
import json
import os
from typing import Any, Dict, List

_PROMPTS_PATH = os.path.join(os.path.dirname(__file__), "prompts.json")


def load_prompts(active_only: bool = True) -> List[Dict[str, Any]]:
    with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompts = data.get("prompts", [])
    if active_only:
        prompts = [p for p in prompts if p.get("active")]
    return prompts


def get_prompt(prompt_id: str) -> Dict[str, Any] | None:
    for p in load_prompts(active_only=False):
        if p.get("id") == prompt_id:
            return p
    return None
