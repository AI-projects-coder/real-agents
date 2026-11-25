from shoppilot.ingest.chunking import chunk_text


def test_short_text_is_one_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_chunks_respect_max_size():
    text = "\n\n".join(f"Paragraph {i} " + "x" * 150 for i in range(20))
    chunks = chunk_text(text, max_chars=500, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)


def test_huge_paragraph_is_hard_split():
    chunks = chunk_text("y" * 2000, max_chars=800, overlap=100)
    assert len(chunks) == 3
    assert all(len(c) <= 800 for c in chunks)
