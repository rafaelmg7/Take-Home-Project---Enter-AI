import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from app.normalize import normalize_str

ACCEPT_THRESHOLD = 0.8
UNCERTAIN_THRESHOLD = 0.6


@dataclass
class Candidate:
    """Candidate value for field extraction."""
    value: str
    line_idx: int
    method: str
    anchor_used: str = ""
    anchor_score: float = 0.0
    position_score: float = 0.0
    enum_score: float = 0.0
    total_score: float = 0.0

    def calculate_total_score(self):
        self.total_score = (
            0.5 * self.anchor_score +
            0.3 * self.position_score +
            0.2 * self.enum_score
        )


def extract_candidates(
    lines: List[Dict[str, Any]],
    field: str,
    field_desc: str,
    kb_field: Dict[str, Any]
):
    """Extract candidate values for a field using heuristics."""
    candidates = []
    anchors = kb_field.get("anchors", [])

    if not anchors:
        return candidates

    for idx, line in enumerate(lines):
        text = line.get("text", "")
        if not text:
            continue

        norm_text = normalize_str(text)

        for anchor in anchors:
            norm_anchor = normalize_str(anchor)

            if norm_anchor not in norm_text:
                continue

            same_line_value = extract_same_line(text, anchor)
            if same_line_value:
                candidate = Candidate(
                    value=same_line_value,
                    line_idx=idx,
                    method="anchor_same_line",
                    anchor_used=anchor,
                    anchor_score=1.0
                )
                candidates.append(candidate)

            if idx + 1 < len(lines):
                next_line_value = extract_next_line(
                    text, anchor, line)
                if next_line_value:
                    candidate = Candidate(
                        value=next_line_value,
                        line_idx=idx + 1,
                        method="next_line",
                        anchor_used=anchor,
                        anchor_score=0.9
                    )
                    candidates.append(candidate)

    return candidates


def extract_same_line(text: str, anchor: str):
    """Extract value from same line after anchor (patterns: "Anchor: VALUE" or "Anchor - VALUE")."""
    pattern = rf'{re.escape(anchor)}\s*[::\-–—]\s*(.+?)$'
    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        return None

    value = match.group(1).strip()
    return value if value and value not in [':', '-', '–', '—'] else None


def extract_next_line(current_text: str, anchor: str, next_line: Dict[str, Any]):
    """Extract value from next line if current line is header/label."""
    norm_current = normalize_str(current_text)
    norm_anchor = normalize_str(anchor)

    if ':' in current_text or '-' in current_text:
        return None

    next_text = next_line.get("text", "").strip()
    if not next_text:
        return None

    tokens = next_text.split()
    if len(tokens) == 0:
        return None

    if len(tokens) == 1:
        return tokens[0]

    if norm_anchor not in norm_current:
        return None

    words_in_current = current_text.split()

    if len(words_in_current) <= 2 or any(keyword in norm_current for keyword in ['profissional', 'completo', 'numero', 'nome']):
        return next_text

    anchor_word_idx = None
    for i, word in enumerate(words_in_current):
        if normalize_str(word) == norm_anchor or norm_anchor in normalize_str(word):
            anchor_word_idx = i
            break

    if anchor_word_idx is not None and anchor_word_idx < len(tokens):
        return tokens[anchor_word_idx]

    return tokens[0]


def score_candidates(
    candidates: List[Candidate],
    kb_field: Dict[str, Any],
    line_positions: Optional[List[float]] = None
):
    """Calculate scores for all candidates."""
    enums = kb_field.get("enums", [])
    region_hint = kb_field.get("region_hint", "")

    for candidate in candidates:
        if enums:
            norm_value = normalize_str(candidate.value)
            norm_enums = [normalize_str(e) for e in enums]
            candidate.enum_score = 1.0 if norm_value in norm_enums else 0.0

        if region_hint and line_positions and candidate.line_idx < len(line_positions):
            y_rel = line_positions[candidate.line_idx]
            if region_hint in ["top_left", "top_right", "header"] and y_rel < 0.3:
                candidate.position_score = 1.0
            elif region_hint in ["bottom_left", "bottom_right", "footer"] and y_rel > 0.7:
                candidate.position_score = 1.0
            else:
                candidate.position_score = 0.5
        else:
            candidate.position_score = 0.5

        candidate.calculate_total_score()

    return candidates


def select_best(
    candidates: List[Candidate],
    k: int = 3
):
    """Select best candidate and return top-K candidates."""
    if not candidates:
        return None, []

    sorted_candidates = sorted(
        candidates, key=lambda c: c.total_score, reverse=True)

    seen = {}
    deduped = []
    for cand in sorted_candidates:
        norm_val = normalize_str(cand.value)
        if norm_val not in seen:
            seen[norm_val] = cand
            deduped.append(cand)

    top_k = deduped[:k]
    best = top_k[0] if top_k else None

    if best and best.total_score < UNCERTAIN_THRESHOLD:
        return None, top_k

    return best, top_k
