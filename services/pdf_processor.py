from pypdf import PdfReader


def extract_chunks(pdf_path: str, chunk_size: int = 1500, overlap: int = 300) -> list[dict]:
    """Extract text from a PDF and split into overlapping chunks with page metadata."""
    reader = PdfReader(pdf_path)
    chunks = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or '').strip()
        if not text:
            continue

        if len(text) <= chunk_size:
            chunks.append({
                'text': text,
                'page': page_num,
                'chunk_index': len(chunks),
            })
        else:
            # Split long pages into overlapping sub-chunks
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                # Try to break at a natural boundary
                if end < len(text):
                    for sep in ['\n\n', '\n', '. ', ' ']:
                        idx = text.rfind(sep, start + chunk_size // 2, end)
                        if idx != -1:
                            end = idx + len(sep)
                            break

                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append({
                        'text': chunk_text,
                        'page': page_num,
                        'chunk_index': len(chunks),
                    })

                next_start = end - overlap
                if next_start <= start:
                    break
                start = next_start

    return chunks
