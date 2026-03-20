from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from app.tools.base import BaseTool


class PDFParseTool(BaseTool):
    name = "pdf_parse"
    description = "Extract text from PDF files."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
        },
        "required": ["path"],
    }

    async def execute(self, **kwargs) -> dict:
        reader = PdfReader(Path(kwargs["path"]))
        pages = [page.extract_text() or "" for page in reader.pages]
        return {
            "page_count": len(pages),
            "text": "\n".join(pages),
            "pages": pages,
        }
