from typing import Dict, Any, Optional
import json
import logging
from pathlib import Path
from app.normalize import normalize_str

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).parent.parent / "data" / "kb"


def _categorize_position(x_rel: float, y_rel: float):
    """Categorize position into 9 regions (3x3 grid)."""
    y_zone = "top" if y_rel < 0.33 else "middle" if y_rel < 0.67 else "bottom"
    x_zone = "left" if x_rel < 0.33 else "center" if x_rel < 0.67 else "right"

    if y_zone == "middle" and x_zone == "center":
        return "center"

    if y_zone == "middle":
        return f"middle_{x_zone}"

    return f"{y_zone}_{x_zone}"


def _compute_dominant_region(region_counts: Dict[str, int], min_confidence: float = 0.6):
    """Compute dominant region if one region has >min_confidence of occurrences."""
    if not region_counts:
        return None

    total = sum(region_counts.values())
    if total == 0:
        return None

    region_name, count = max(region_counts.items(), key=lambda x: x[1])
    ratio = count / total

    return region_name if ratio >= min_confidence else None


def load_kb(label: str):
    """Load knowledge base for a label from JSON file."""
    kb_path = KB_DIR / f"label_{label}.json"

    if kb_path.exists():
        with open(kb_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    return {
        "anchors": {},
        "enums": {},
        "region_hint": {},
        "region_counts": {}
    }


def save_kb(label: str, kb: Dict[str, Any]):
    """Save knowledge base to JSON file."""
    KB_DIR.mkdir(parents=True, exist_ok=True)
    kb_path = KB_DIR / f"label_{label}.json"

    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)


def init_from_schema(label: str, schema: Dict[str, str]):
    """Initialize KB from schema with normalized anchors based on field names."""
    kb = {
        "anchors": {},
        "enums": {},
        "region_hint": {},
        "region_counts": {}
    }

    for field_name in schema.keys():
        base = field_name.replace("_", " ").strip()

        variations = [
            base,
            base.lower(),
            base.upper(),
            base.title(),
            base.replace(" ", ""),
            base.replace(" ", "_"),
            base.replace(" ", "-")
        ]

        anchors = []
        seen = set()

        for var in variations:
            if not var:
                continue
            normalized = normalize_str(var)
            if normalized and normalized not in seen:
                anchors.append(normalized)
                seen.add(normalized)

        kb["anchors"][field_name] = anchors

    return kb


def update_kb(
    label: str,
    extraction_results: Dict[str, Any],
    heuristic_evidence: Optional[Dict[str, Dict[str, Any]]] = None,
    llm_metadata: Optional[Dict[str, Dict[str, Any]]] = None
):
    """Update KB based on successful extractions from heuristics and LLM."""
    kb = load_kb(label)
    updated = False

    if "region_counts" not in kb:
        kb["region_counts"] = {}

    if heuristic_evidence:
        for field, evidence in heuristic_evidence.items():
            if not extraction_results.get(field):
                continue

            position = evidence.get("position")
            if position and len(position) == 2:
                x_rel, y_rel = position
                region = _categorize_position(x_rel, y_rel)

                if field not in kb["region_counts"]:
                    kb["region_counts"][field] = {}

                if region not in kb["region_counts"][field]:
                    kb["region_counts"][field][region] = 0

                kb["region_counts"][field][region] += 1
                updated = True

                dominant = _compute_dominant_region(kb["region_counts"][field])
                if dominant:
                    old_hint = kb["region_hint"].get(field)
                    if old_hint != dominant:
                        if field not in kb["region_hint"]:
                            kb["region_hint"][field] = []
                        if isinstance(kb["region_hint"][field], str):
                            kb["region_hint"][field] = [
                                kb["region_hint"][field]]
                        if dominant not in kb["region_hint"][field]:
                            kb["region_hint"][field].append(dominant)
                        updated = True

            anchor_used = evidence.get("anchor_used")
            if anchor_used:
                if field not in kb["anchors"]:
                    kb["anchors"][field] = []

                norm_anchor = normalize_str(anchor_used)
                existing_anchors = [normalize_str(
                    a) for a in kb["anchors"][field]]

                extracted_value = extraction_results.get(field, "")
                norm_value = normalize_str(
                    str(extracted_value)) if extracted_value else ""

                if norm_anchor and norm_anchor not in existing_anchors and norm_anchor != norm_value:
                    kb["anchors"][field].append(norm_anchor)
                    updated = True

            line_text = evidence.get("line_text", "")
            if line_text and ":" in line_text:
                parts = line_text.split(":", 1)
                if len(parts) == 2:
                    potential_anchor = parts[0].strip()
                    potential_value = parts[1].strip()

                    if potential_anchor and len(potential_anchor.split()) <= 3:
                        if field not in kb["anchors"]:
                            kb["anchors"][field] = []

                        norm_potential = normalize_str(potential_anchor)
                        norm_value = normalize_str(potential_value)
                        existing_anchors = [normalize_str(
                            a) for a in kb["anchors"][field]]

                        if norm_potential and norm_potential not in existing_anchors and norm_potential != norm_value:
                            kb["anchors"][field].append(norm_potential)
                            updated = True

    if llm_metadata:
        for field, metadata in llm_metadata.items():
            if not metadata or not extraction_results.get(field):
                continue

            field_metadata = metadata.get("metadata")
            if not field_metadata:
                continue

            anchors = field_metadata.get("anchors")
            if anchors and isinstance(anchors, list):
                if field not in kb["anchors"]:
                    kb["anchors"][field] = []

                extracted_value = extraction_results.get(field, "")
                norm_value = normalize_str(
                    str(extracted_value)) if extracted_value else ""

                for anchor in anchors:
                    norm_anchor = normalize_str(anchor)
                    existing_anchors = [normalize_str(
                        a) for a in kb["anchors"][field]]

                    if norm_anchor and norm_anchor not in existing_anchors and norm_anchor != norm_value:
                        kb["anchors"][field].append(norm_anchor)
                        updated = True

            enums = field_metadata.get("enums")
            if enums and isinstance(enums, list):
                if field not in kb["enums"]:
                    kb["enums"][field] = []

                for enum_val in enums:
                    norm_enum = normalize_str(enum_val)
                    existing_enums = [normalize_str(
                        e) for e in kb["enums"][field]]

                    if norm_enum and norm_enum not in existing_enums:
                        kb["enums"][field].append(norm_enum)
                        updated = True

            region = field_metadata.get("region")
            if region and region not in [None, "null"]:
                valid_regions = ["top_left", "top_right", "bottom_left",
                                 "bottom_right", "header", "footer", "body"]
                if region in valid_regions:
                    if field not in kb["region_hint"]:
                        kb["region_hint"][field] = []
                    if isinstance(kb["region_hint"][field], str):
                        kb["region_hint"][field] = [kb["region_hint"][field]]
                    if region not in kb["region_hint"][field]:
                        kb["region_hint"][field].append(region)
                        updated = True

    if updated:
        save_kb(label, kb)
