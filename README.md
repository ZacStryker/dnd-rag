# D&D RAG

Ask natural language questions about D&D 5th Edition rules. Semantic search retrieves the most relevant passages from the Dungeon Master's Guide and Player's Handbook, then Claude AI synthesizes a cited answer grounded exclusively in the source text.

## How It Works

```
Question
   │
   ▼
sentence-transformers (all-MiniLM-L6-v2)
   │  384-dim normalized embedding
   ▼
sqlite-vec cosine similarity search
   │  top-5 chunks across DMG + PHB
   ▼
Anthropic Claude Haiku 3.5
   │  answer grounded in retrieved context
   ▼
Streaming response (SSE) + source citations
```

This is the standard RAG (Retrieval-Augmented Generation) pattern: retrieve relevant context first, then generate an answer conditioned on that context. The model is instructed to only answer from the provided passages, which prevents hallucination and makes every answer verifiable.

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Web framework | Flask Blueprint | Integrated with existing portfolio hub |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) | Local, no API key, 80MB, 384-dim, strong semantic quality |
| Vector store | sqlite-vec | Single `.db` file, zero infrastructure, fits in 2GB RAM |
| LLM | Anthropic Claude Haiku 3.5 | Fast, cheap (~$0.001/query), 200K context window |
| PDF processing | pypdf | Lightweight, page-aware extraction |
| Streaming | Flask SSE + Anthropic streaming SDK | Token-by-token response for responsive UX |

## Knowledge Base

| Source | Label | Content |
|--------|-------|---------|
| Dungeon Master's Guide (5e) | DMG | World-building, encounter design, magic items, monster creation |
| Player's Handbook (5e) | PHB | Character classes, spells, combat rules, equipment |

Combined: ~5,500 chunks across both books.

## Chunking Strategy

- **Per-page chunking** — each PDF page is treated as a unit, preserving natural section boundaries
- **Chunk size** — 1,500 characters with 300-character overlap for long pages
- **Metadata** — each chunk stores source label (DMG/PHB) and page number for citations

## Design Decisions

**Why local embeddings instead of an API?**
`all-MiniLM-L6-v2` loads once into ~80MB of RAM and runs at ~50ms/query on CPU. Eliminates a second API dependency, zero cost, and no round-trip latency for the embedding step.

**Why sqlite-vec instead of ChromaDB or FAISS?**
The knowledge base is ~5,500 vectors — small enough that a single SQLite file is the right tool. No separate process, no serialization complexity, survives restarts, trivial to back up.

**Why top-5 chunks instead of more?**
At 1,500 chars/chunk, top-5 puts ~7,500 characters of context into the prompt — well within Haiku's 200K token window while keeping cost and latency low. More chunks can be passed without issue if needed.

**Why Claude Haiku and not Sonnet?**
For a well-structured RAG prompt where the answer is in the context, Haiku performs comparably to Sonnet at 10x lower cost. Sonnet is worth the upgrade for reasoning-heavy tasks; this is primarily a retrieval + synthesis task.

## Project Structure

```
rag_chatbot/
├── __init__.py              # Blueprint, routes, background indexing thread
├── services/
│   ├── pdf_processor.py     # PDF → overlapping chunks with page metadata
│   ├── embeddings.py        # Lazy-loaded sentence-transformers wrapper
│   ├── vectorstore.py       # sqlite-vec schema, insert, KNN search
│   └── llm.py               # Anthropic streaming + 529 retry logic
├── data/
│   ├── dmg.pdf              # D&D 5e Dungeon Master's Guide (not committed)
│   ├── phb.pdf              # D&D 5e Player's Handbook (not committed)
│   └── vectors.db           # Built on first startup (not committed)
├── templates/
│   └── rag_chatbot/
│       └── index.html
└── static/
    └── script.js
```

## Setup

1. Add your PDF files to `data/`:
   - `data/dmg.pdf` — D&D 5e Dungeon Master's Guide
   - `data/phb.pdf` — D&D 5e Player's Handbook

2. Set your Anthropic API key in `.env` at the project root:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

3. Start the server — indexing runs automatically in the background on first launch:
   ```bash
   python app.py
   ```

The app detects which PDFs are present and indexes them. If you add a new PDF later, delete `data/vectors.db` and restart to trigger re-indexing. To add more books, add an entry to `_SOURCES` in `__init__.py` and drop the PDF in `data/`.

## Adding More Books

Edit `_SOURCES` in `__init__.py`:

```python
_SOURCES = [
    {'filename': 'dmg.pdf',  'label': 'DMG'},
    {'filename': 'phb.pdf',  'label': 'PHB'},
    {'filename': 'xgte.pdf', 'label': "Xanathar's"},  # add new books here
]
```

Then delete `data/vectors.db` and restart. The app re-indexes everything automatically.
