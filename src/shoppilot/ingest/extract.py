"""Turn raw file bytes into plain text."""
import io

from pypdf import PdfReader
from pypdf.errors import PyPdfError


def extract_text(data: bytes, filename: str) -> str:
    """Raises ValueError for anything we can't handle = a PERMANENT failure (no retries)."""
    name = filename.lower()
    if name.endswith((".md", ".txt")):
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"not valid UTF-8 text: {e}") from e
    if name.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(data))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except PyPdfError as e:
            raise ValueError(f"corrupt PDF: {e}") from e
    raise ValueError(f"unsupported file type: {filename}")
