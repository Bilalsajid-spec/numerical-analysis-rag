# Purpose: split page text into searchable chunks while preserving formula structure.
# Work: preserve complete math units, split tables into rows, and retain bounded overlap.

import hashlib
import re
from bs4 import BeautifulSoup

# Match protected math and table units before ordinary text tokens.
UNITS = re.compile(r"\$\$[\s\S]*?\$\$|(?<!\\)\$(?:\\.|[^$])*?(?<!\\)\$|<table\b[\s\S]*?</table>|[^\s$]+", re.I)


def _table_rows(html):
    # Repeat table headers with each row to preserve the meaning of cell values.
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")
    if not rows:
        return [html]
    rendered = []
    header = rows[0].get_text(" | ", strip=True)
    for row in rows[1:]:
        rendered.append(f"Table columns: {header}\nTable row: {row.get_text(' | ', strip=True)}")
    return rendered or [header]


def chunk_pages(pages, token_count, max_tokens=180, overlap_tokens=25):
    if max_tokens < 1 or not 0 <= overlap_tokens < max_tokens:
        raise ValueError("Require max_tokens > overlap_tokens >= 0")
    chunks = []
    for page in pages:
        # Retain a title for context and keep each chunk within one PDF page.
        lines = [line.strip() for line in page["text"].splitlines() if line.strip()]
        title = next((line.lstrip("# ") for line in lines if line.startswith("#")), lines[0] if lines else "")[:120]
        units = []
        for match in UNITS.finditer(page["text"]):
            unit = match.group()
            units.extend(_table_rows(unit) if unit.lower().startswith("<table") else [unit])
        current, current_size, part = [], 0, 0

        def emit(values):
            nonlocal part
            text = " ".join(values).strip()
            if not text:
                return
            identity = f"{page['source']}:{page['page']}:{part}:{text}"
            chunks.append({
                "id": hashlib.sha256(identity.encode()).hexdigest(), "text": text,
                "source": page["source"], "page": page["page"], "part": part,
                "title": title, "review_required": bool(page.get("review_required", True)),
                "oversize_atomic": token_count(text) > max_tokens,
            })
            part += 1

        for unit in units:
            size = token_count(unit)
            if current and current_size + size > max_tokens:
                emit(current)
                # Keep only complete units in the overlap to avoid splitting equations.
                carry, carry_size = [], 0
                for old in reversed(current):
                    old_size = token_count(old)
                    if carry_size + old_size > overlap_tokens:
                        break
                    carry.insert(0, old)
                    carry_size += old_size
                current, current_size = carry, carry_size
                if current_size + size > max_tokens:
                    current, current_size = [], 0
            current.append(unit)
            current_size += size
            # Store oversized equations intact so lexical search can use their complete text.
            if size > max_tokens:
                emit(current)
                current, current_size = [], 0
        if current:
            emit(current)
    return chunks
