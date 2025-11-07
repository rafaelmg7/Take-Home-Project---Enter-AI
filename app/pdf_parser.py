from typing import Dict, BinaryIO
import fitz


class Line:
    """Text line extracted from PDF."""

    def __init__(self, text: str, y_rel: float, x_rel: float, bbox: Dict[str, float] = None):
        self.text = text
        self.y_rel = y_rel
        self.x_rel = x_rel
        self.bbox = bbox or {}

    def to_dict(self):
        return {
            "text": self.text,
            "y_rel": self.y_rel,
            "x_rel": self.x_rel,
            "bbox": self.bbox
        }


def parse_pdf(pdf_file: BinaryIO):
    """Parse PDF and extract text lines with positional metadata."""
    pdf_bytes = pdf_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    all_lines = []
    page_count = len(doc)

    for page_num in range(page_count):
        page = doc[page_num]
        page_height = page.rect.height
        page_width = page.rect.width

        text_dict = page.get_text("dict")
        blocks = text_dict.get("blocks", [])

        spans = []
        for block in blocks:
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        spans.append({
                            "text": span.get("text", ""),
                            "bbox": bbox,
                            "y": bbox[1],
                            "x": bbox[0],
                        })

        spans.sort(key=lambda s: (s["y"], s["x"]))

        Y_TOLERANCE = 3.0
        lines_grouped = []
        current_line = []
        current_y = None

        for span in spans:
            if not span["text"].strip():
                continue

            span_y = span["y"]

            if current_y is None or abs(span_y - current_y) <= Y_TOLERANCE:
                current_line.append(span)
                if current_y is None:
                    current_y = span_y
            else:
                if current_line:
                    lines_grouped.append(current_line)
                current_line = [span]
                current_y = span_y

        if current_line:
            lines_grouped.append(current_line)

        for line_spans in lines_grouped:
            line_spans.sort(key=lambda s: s["x"])
            line_text = " ".join(s["text"] for s in line_spans)
            x0 = min(s["bbox"][0] for s in line_spans)
            y0 = min(s["bbox"][1] for s in line_spans)
            x1 = max(s["bbox"][2] for s in line_spans)
            y1 = max(s["bbox"][3] for s in line_spans)

            y_rel = y0 / page_height if page_height > 0 else 0.0
            x_rel = (x0 + x1) / 2 / page_width if page_width > 0 else 0.0

            bbox = {
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "width": x1 - x0,
                "height": y1 - y0,
                "page": page_num + 1
            }

            line = Line(
                text=line_text,
                y_rel=y_rel,
                x_rel=x_rel,
                bbox=bbox
            )
            all_lines.append(line)

    doc.close()

    full_text = "\n".join(line.text for line in all_lines)

    return {
        "lines": [line.to_dict() for line in all_lines],
        "full_text": full_text,
        "page_count": page_count
    }
