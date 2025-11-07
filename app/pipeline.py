from typing import Dict, Any, List
import logging
import time

from app.kb import load_kb, init_from_schema, save_kb, update_kb
from app.heuristics import extract_candidates, score_candidates, select_best, ACCEPT_THRESHOLD
from app.normalize import normalize_field
from app.llm import resolve_batched_gpt5_mini

logger = logging.getLogger(__name__)

LLM_TIMEOUT = 8.0
MIN_TIME_FOR_LLM = 2.5


def run_extraction_pipeline(
    pdf_lines: List[Dict[str, Any]],
    doc_text: str,
    schema: Dict[str, str],
    label: str,
    timeout_seconds: float = 9.0
):
    """Orchestrate the full extraction pipeline."""
    start_time = time.time()

    kb = load_kb(label)
    if not kb.get("anchors"):
        kb = init_from_schema(label, schema)
        save_kb(label, kb)

    results = {}
    uncertain_fields = []
    candidates_by_field = {}
    heuristic_evidence = {}
    extraction_metadata = {
        "processing_time": 0.0,
        "llm_used": False,
    }

    line_positions = [line.get("y_rel", 0.5) for line in pdf_lines]

    for field, field_desc in schema.items():
        kb_field = {
            "anchors": kb.get("anchors", {}).get(field, []),
            "enums": kb.get("enums", {}).get(field, []),
            "region_hint": kb.get("region_hint", {}).get(field, "")
        }

        candidates = extract_candidates(pdf_lines, field, field_desc, kb_field)

        if not candidates:
            uncertain_fields.append(field)
            results[field] = None
            continue

        scored = score_candidates(candidates, kb_field, line_positions)
        best, top_k = select_best(scored)

        candidates_by_field[field] = [c.value for c in top_k]

        if best and best.total_score >= ACCEPT_THRESHOLD:
            normalized = normalize_field(best.value)
            results[field] = normalized

            line_text = pdf_lines[best.line_idx].get(
                "text", "") if best.line_idx < len(pdf_lines) else ""
            x_rel = pdf_lines[best.line_idx].get(
                "x_rel", 0.5) if best.line_idx < len(pdf_lines) else 0.5
            y_rel = pdf_lines[best.line_idx].get(
                "y_rel", 0.5) if best.line_idx < len(pdf_lines) else 0.5

            heuristic_evidence[field] = {
                "anchor_used": best.anchor_used,
                "method": best.method,
                "line_text": line_text,
                "score": best.total_score,
                "position": (x_rel, y_rel)
            }
        else:
            uncertain_fields.append(field)
            results[field] = None

    elapsed = time.time() - start_time
    time_remaining = timeout_seconds - elapsed

    llm_results = {}
    if uncertain_fields and time_remaining > MIN_TIME_FOR_LLM:
        extraction_metadata["llm_used"] = True

        try:
            llm_results = resolve_batched_gpt5_mini(
                doc_text=doc_text,
                schema=schema,
                uncertain_fields=uncertain_fields,
                candidates_by_field=candidates_by_field,
                timeout_seconds=LLM_TIMEOUT
            )

            for field, llm_data in llm_results.items():
                value = llm_data.get("value")
                if value:
                    normalized = normalize_field(value)
                    if normalized:
                        results[field] = normalized

        except Exception as e:
            logger.error(f"LLM resolution failed: {e}")

    if heuristic_evidence or llm_results:
        try:
            update_kb(
                label=label,
                extraction_results=results,
                heuristic_evidence=heuristic_evidence,
                llm_metadata=llm_results
            )
        except Exception as e:
            logger.error(f"KB update failed: {e}")

    extraction_metadata["processing_time"] = time.time() - start_time

    return {
        "fields": results,
        "metadata": extraction_metadata
    }
