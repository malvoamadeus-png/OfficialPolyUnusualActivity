# -*- coding: utf-8 -*-
"""OpenAI client for filtering interesting Polymarket new markets."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from packages.common.paths import PROJECT_ROOT

MODEL_NAME = "gpt-5.4-mini"

NEW_MARKETS_FILTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "selected_markets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "question_zh": {"type": "string"},
                    "slug": {"type": "string"},
                    "reason": {"type": "string"},
                    "appeal_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["question", "question_zh", "slug", "reason", "appeal_tags"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["selected_markets"],
    "additionalProperties": False,
}

FILTER_PROMPT_TEMPLATE = """Role: 你是一位资深的预测市场分析师与内容策展人，擅长从海量交易市场中捕捉具有“病毒式传播潜力”和“高大众感知度”的话题。
Task:
以下是一份 Polymarket 预测题目的列表。请按照以下标准筛选，找出那些对非专业投资者（普通大众）也具有吸引力的题目。

筛选标准：
1. 大众相关性：题目涉及全球知名人物、重大国际新闻或与日常生活息息相关的事件。
2. 博彩性：大众更有可能愿意下注博彩的题目，不一定具备认知但愿意随意玩一玩的。
3. 娱乐性与戏剧性：优先选择带有“梗”属性、社交媒体互动、或具有戏剧性反转潜力的题目。
4. 认知门槛低：即使不关注金融或特定体育联赛的人，也能一眼看懂预测逻辑并产生兴趣。

排除项：
- 严禁：具体的、小众的体育赛事。
- 严禁：过于枯燥的纯宏观经济数据。
- 严禁：纯技术性或项目内部治理话题。
- 严禁：发文频率相关的话题。

题目列表：
{market_list}

请返回你筛选出的题目，每个题目包含：
- question: 原始英文题目
- question_zh: 翻译为通顺的中文题目，保留人名/公司名的常用中文译名
- slug: 原始 slug
- reason: 1-2 句中文，说明为什么这个题目有吸引力
- appeal_tags: 自由生成的标签数组，描述这个题目的吸引力类型

只返回 JSON，不要输出额外说明。"""


@dataclass
class FilterResult:
    selected: list[dict[str, Any]]
    raw_text: str
    usage: dict[str, int]


class NewMarketsFilterClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._load_env_file()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        if not self.api_key:
            raise ValueError("未找到 OPENAI_API_KEY")

    @staticmethod
    def _load_env_file() -> None:
        candidates = [
            Path.cwd() / ".env",
            PROJECT_ROOT / ".env",
            PROJECT_ROOT / "backend" / ".env",
            Path("/etc/odailyseer/odailyseer.env"),
        ]
        for env_path in candidates:
            if not env_path.exists():
                continue
            try:
                for raw in env_path.read_text(encoding="utf-8").splitlines():
                    line = raw.strip().lstrip("\ufeff")
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = value
                break
            except OSError:
                continue

    def filter_markets(self, markets: list[dict[str, Any]]) -> FilterResult:
        lines = []
        for i, m in enumerate(markets, 1):
            lines.append(f"{i}. [{m['slug']}] {m['question']}")
        market_list = "\n".join(lines)

        prompt = FILTER_PROMPT_TEMPLATE.format(market_list=market_list)
        payload = {
            "model": MODEL_NAME,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        }
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "selected_markets_payload",
                    "schema": NEW_MARKETS_FILTER_SCHEMA,
                    "strict": True,
                }
            },
        }

        response = requests.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()

        text = self._extract_text(data)
        parsed = self._parse_json(text)
        selected = parsed.get("selected_markets", [])

        usage_obj = data.get("usage") or {}
        usage = {
            "input_tokens": int(usage_obj.get("input_tokens", 0) or 0),
            "output_tokens": int(usage_obj.get("output_tokens", 0) or 0),
        }
        return FilterResult(selected=selected, raw_text=text, usage=usage)

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
        output = response.get("output", [])
        texts: list[str] = []

        for item in output:
            for content in item.get("content", []) or []:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text)

        if texts:
            return "\n".join(texts)

        fallback = response.get("output_text")
        if isinstance(fallback, str) and fallback.strip():
            return fallback

        raise ValueError("OpenAI 返回中未找到文本内容")

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if fence:
            obj = json.loads(fence.group(1))
            if isinstance(obj, dict):
                return obj

        start = text.find("{")
        if start < 0:
            raise ValueError("OpenAI 返回不是可解析的 JSON 对象")

        depth = 0
        in_str = False
        escape = False
        end = -1
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = idx + 1
                    break

        if end < 0:
            raise ValueError("OpenAI JSON 提取失败")

        obj = json.loads(text[start:end])
        if not isinstance(obj, dict):
            raise ValueError("OpenAI 返回 JSON 不是对象")
        return obj
