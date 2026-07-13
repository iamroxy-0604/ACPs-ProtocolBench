# -*- coding: utf-8 -*-
"""ACPs QA Worker executor — processes questions using LLM."""
from __future__ import annotations
import json, os
from typing import Optional


class QAAgentExecutor:
    """Executor for ACPs QA workers. Handles LLM-based question answering."""

    def __init__(self, config=None):
        self.config = config or {}
        model_cfg = self.config.get("model", {})
        self._model_name = model_cfg.get("name", "deepseek-v4-pro")
        self._llm_client = None

    async def process_message(self, payload: dict) -> str:
        text = payload.get("text", str(payload))
        try:
            data = json.loads(text) if isinstance(text, str) else text
        except Exception:
            data = {"question": text}
        question = data.get("question", str(data))

        if not self._llm_client:
            from openai import OpenAI
            model_cfg = self.config.get("model", {})
            api_key = os.getenv("OPENAI_API_KEY") or model_cfg.get("openai_api_key", "")
            base_url = os.getenv("OPENAI_BASE_URL") or model_cfg.get("openai_base_url", "https://api.openai.com/v1")
            self._llm_client = OpenAI(api_key=api_key, base_url=base_url)

        try:
            resp = self._llm_client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Provide concise, accurate answers. Keep responses under 150 words."},
                    {"role": "user", "content": question},
                ],
                temperature=0.0, max_tokens=200,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"Error: {e}"
