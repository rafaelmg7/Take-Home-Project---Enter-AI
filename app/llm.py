from typing import Dict, List, Optional
import json
import asyncio
import logging
import os
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MAX_DOC_CHARS = 2000


def resolve_batched_gpt5_mini(
    doc_text: str,
    schema: Dict[str, str],
    uncertain_fields: List[str],
    candidates_by_field: Optional[Dict[str, List[str]]] = None,
    timeout_seconds: float = 8.0
):
    """Resolve uncertain fields using a single batched LLM call."""
    if not uncertain_fields:
        return {}

    if len(doc_text) > MAX_DOC_CHARS:
        doc_text = doc_text[:MAX_DOC_CHARS] + "\n[...truncated]"

    candidates_by_field = candidates_by_field or {}

    system_prompt = "Extract data from document. Return JSON only. Use null if not found."

    fields_list = []
    for field in uncertain_fields:
        desc = schema.get(field, "")
        cands = candidates_by_field.get(field, [])
        entry = f'"{field}": {desc}'
        if cands:
            entry += f' [{cands[0]}]'
        fields_list.append(entry)

    user_prompt = f"""Fields: {', '.join(fields_list)}

Doc:
{doc_text}

JSON format:
{{"fields": {{"{uncertain_fields[0]}": "value|null", ...}}, "metadata": {{"{uncertain_fields[0]}": {{"anchors": ["label"], "enums": ["val"], "region": "top_left|null"}}, ...}}}}

metadata is optional, only if found in doc."""

    try:
        response = client.responses.create(
            model="gpt-5-mini",
            instructions=system_prompt,
            input=user_prompt,
            reasoning={"effort": "minimal"},
            text={"verbosity": "low", "format": {"type": "json_object"}},
            max_output_tokens=500,
            timeout=timeout_seconds
        )

        output_text = response.output_text.strip()
        result_data = json.loads(output_text)

        fields = result_data.get("fields", {})
        metadata = result_data.get("metadata", {})

        output = {}
        for field in uncertain_fields:
            output[field] = {
                "value": fields.get(field),
                "metadata": metadata.get(field)
            }

        return output

    except asyncio.TimeoutError:
        return {field: {"value": None, "metadata": None} for field in uncertain_fields}

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON: {e}")
        return {field: {"value": None, "metadata": None} for field in uncertain_fields}

    except Exception as e:
        logger.error(f"LLM error: {e}")
        return {field: {"value": None, "metadata": None} for field in uncertain_fields}
