import io

import pytest
from docx import Document


@pytest.fixture
def docx_bytes() -> bytes:
    doc = Document()
    doc.add_paragraph("[00:00:05] Lan: Xin chao")
    doc.add_paragraph("[00:00:20] Minh: Chao chi")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
