"""Split text into overlapping chunks (a preview of RAG, Module 6 goes deeper)."""


def chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> list[str]:
    """Pack paragraphs into chunks of <= max_chars.
    `overlap` chars from the end of each chunk are repeated at the start of the next,
    so a sentence split across chunks keeps its context."""
    if overlap >= max_chars:
        raise ValueError("overlap must be smaller than max_chars")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            current = current[-overlap:]  # carry context forward
        current = f"{current}\n\n{para}" if current else para

        # a single huge paragraph: hard-split it
        while len(current) > max_chars:
            chunks.append(current[:max_chars])
            current = current[max_chars - overlap:]

    if current:
        chunks.append(current)
    return chunks
