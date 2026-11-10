# Purpose: restore simple table superscripts and subscripts from the original PDF.
# Work: check and repair OCR table expressions using original PDF glyph positions.

import re

import pymupdf
from bs4 import BeautifulSoup


def _script_expression(spans, cell_bbox):
    # Assign each text span to a table cell using its center position.
    cell = pymupdf.Rect(cell_bbox)
    selected = []
    for span in spans:
        x0, y0, x1, y1 = span["bbox"]
        centre = pymupdf.Point((x0 + x1) / 2, (y0 + y1) / 2)
        if span["text"].strip() and centre in cell:
            selected.append(span)
    if not selected:
        return None

    # Handle one base letter and its simple scripts.
    # Exclude complex fractions and matrices from this repair rule.
    largest = max(span["size"] for span in selected)
    bases = [span for span in selected if span["size"] >= largest * 0.88]
    if len(bases) != 1 or not re.fullmatch(r"[A-Za-z]", bases[0]["text"]):
        return None
    base = bases[0]
    groups = {"sub": [], "sup": []}
    for span in selected:
        if span is base:
            continue
        shift = span["origin"][1] - base["origin"][1]
        if abs(shift) < largest * 0.12:
            return None
        groups["sup" if shift < 0 else "sub"].append(span)
    if not any(groups.values()):
        return None

    latex = base["text"]
    for kind, symbol in [("sub", "_"), ("sup", "^")]:
        group = sorted(groups[kind], key=lambda span: span["origin"][0])
        if not group:
            continue
        # Skip nested scripts and fractions that involve ambiguous multiple baselines.
        baselines = [span["origin"][1] for span in group]
        value = "".join(span["text"] for span in group).strip()
        if max(baselines) - min(baselines) > largest * 0.15:
            return None
        if not re.fullmatch(r"[A-Za-z0-9()+ =.,-]+", value):
            return None
        latex += f"{symbol}{{{value}}}"
    return latex


def _html_spans(value):
    # Find table HTML in the structured OCR result.
    if isinstance(value, dict):
        if "html" in value:
            yield value
        else:
            for child in value.values():
                yield from _html_spans(child)
    elif isinstance(value, list):
        for child in value:
            yield from _html_spans(child)


def restore_table_scripts(text, middle_json, pdf_path, page_number):
    restored = 0
    if not middle_json:
        return text, restored
    with pymupdf.open(pdf_path) as pdf:
        page = pdf[page_number - 1]
        spans = [span for block in page.get_text("dict")["blocks"]
                 for line in block.get("lines", []) for span in line["spans"]]
        if not spans:
            return text, restored
        for info in middle_json.get("pdf_info", []):
            for block in info.get("para_blocks", []):
                if block.get("type") != "table":
                    continue
                clip = (pymupdf.Rect(block["bbox"]) + (-2, -2, 2, 4)) & page.rect
                if clip.is_empty:
                    continue
                candidates = page.find_tables(clip=clip, strategy="lines").tables
                for span in _html_spans(block):
                    original = span["html"]
                    soup = BeautifulSoup(original, "html.parser")
                    rows = [row.find_all(["td", "th"]) for row in soup.find_all("tr")]
                    for table in candidates:
                        # Replace cells only when row counts, column counts, and headers match.
                        if len(rows) != table.row_count or not rows:
                            continue
                        if any(len(row) != table.col_count for row in rows):
                            continue
                        if any(cell.get("rowspan", "1") != "1" or cell.get("colspan", "1") != "1"
                               for row in rows for cell in row):
                            continue
                        native = table.extract()
                        normalize = lambda value: re.sub(r"\s+", "", value or "")
                        if [normalize(cell.get_text()) for cell in rows[0]] != [normalize(t) for t in native[0]]:
                            continue
                        for row_index, row in enumerate(rows):
                            for col_index, cell in enumerate(row):
                                bbox = table.rows[row_index].cells[col_index]
                                if bbox is None:
                                    continue
                                latex = _script_expression(spans, bbox)
                                if latex:
                                    cell.clear()
                                    cell.append(f"${latex}$")
                                    restored += 1
                        text = text.replace(original, str(soup), 1)
                        break
    return text, restored
