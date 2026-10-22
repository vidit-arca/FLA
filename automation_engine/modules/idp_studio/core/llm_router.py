"""
LLM Router: Centralized dispatch and specialized model allocation for IDP Studio.

Allocates right-sized models based on cognitive requirements:
- triage: qwen3.5:4b (sub-150ms classification)
- schema_coder: qwen2.5-coder:7b (precise AST/DAG/JSON parsing, zero hallucination)
- legal_reasoning: qwen2.5:14b (nuanced statutory semantic mapping)
"""

import os
import json
import re
import logging
from typing import Dict, Any, Optional, Union
import requests

logger = logging.getLogger("idp_studio.llm_router")

OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://192.168.112.2:11434").rstrip("/")
GENERATE_ENDPOINT = f"{OLLAMA_BASE_URL}/api/generate"

MODEL_ROLES: Dict[str, str] = {
    "triage": os.getenv("MODEL_TRIAGE", "qwen3.5:4b"),
    "schema_coder": os.getenv("MODEL_SCHEMA_CODER", "qwen2.5-coder:7b"),
    "legal_reasoning": os.getenv("MODEL_LEGAL_REASONING", "qwen2.5:14b"),
}

DEFAULT_TIMEOUTS: Dict[str, int] = {
    "triage": 15,
    "schema_coder": 45,
    "legal_reasoning": 60,
}


def resolve_model(role_or_model: str) -> str:
    """Resolve a role key ('triage', 'schema_coder', etc.) or return direct model name."""
    role_key = role_or_model.lower().strip()
    return MODEL_ROLES.get(role_key, role_or_model)


def clean_json_text(text: str) -> str:
    """Strip markdown code fence blocks if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            first_line = lines[0].strip()
            if first_line.startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
    return text


def call_llm(
    role_or_model: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.1,
    json_mode: bool = False,
    timeout: Optional[int] = None,
) -> str:
    """
    Invoke the allocated model via Ollama.
    """
    model_name = resolve_model(role_or_model)
    role_key = role_or_model.lower().strip()
    actual_timeout = timeout or DEFAULT_TIMEOUTS.get(role_key, 60)

    payload: Dict[str, Any] = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    if system_prompt:
        payload["system"] = system_prompt

    if json_mode:
        payload["format"] = "json"

    try:
        resp = requests.post(
            GENERATE_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=actual_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_response = data.get("response", "")
        return raw_response
    except requests.exceptions.Timeout:
        logger.error(f"[LLMRouter] Timeout ({actual_timeout}s) invoking model {model_name} for role {role_or_model}")
        raise TimeoutError(f"LLM request timed out after {actual_timeout}s ({model_name})")
    except Exception as e:
        logger.error(f"[LLMRouter] Error invoking model {model_name}: {str(e)}")
        raise


def call_llm_json(
    role_or_model: str,
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.1,
    timeout: Optional[int] = None,
) -> Union[Dict[str, Any], list]:
    """
    Invoke the allocated model in JSON mode and parse the resulting JSON object or list.
    """
    raw_text = call_llm(
        role_or_model=role_or_model,
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        json_mode=True,
        timeout=timeout,
    )

    cleaned = clean_json_text(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as err:
        # Fallback regex extraction in case of trailing commas or stray text
        json_match = re.search(r"(\[.*\]|\{.*\})", cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass
        logger.error(f"[LLMRouter] Failed to decode JSON from model response: {cleaned[:200]}")
        raise ValueError(f"Model response was not valid JSON: {err}")
