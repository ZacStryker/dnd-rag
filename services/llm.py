import json
import os
import time
from typing import Generator

from anthropic import Anthropic, APIStatusError

_client = None

_SYSTEM_PROMPT = (
    'You are an expert D&D 5th Edition rules assistant. '
    'Help Dungeon Masters and players understand the rules, lore, and guidance '
    'in the official D&D 5e books.\n\n'
    'Answer questions based ONLY on the provided context passages. '
    'Cite sources inline using the format [DMG p. X] or [PHB p. X]. '
    'If the answer is not in the provided context, say: '
    '"I couldn\'t find that in the provided sections — try rephrasing or '
    'asking about a related topic." '
    'Be precise and use correct D&D terminology.'
)


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
    return _client


def stream_answer(question: str, chunks: list[dict]) -> Generator[str, None, None]:
    """Yield SSE-formatted strings streaming Claude's answer token by token."""
    context = '\n\n---\n\n'.join(
        f'[{c["source"]} p. {c["page"]}]\n{c["text"]}' for c in chunks
    )
    user_message = f'Context from the DMG:\n\n{context}\n\nQuestion: {question}'

    params = {
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': 1024,
        'system': _SYSTEM_PROMPT,
        'messages': [{'role': 'user', 'content': user_message}],
    }

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            with _get_client().messages.stream(**params) as stream:
                for text in stream.text_stream:
                    yield f'data: {json.dumps({"type": "token", "text": text})}\n\n'
            yield f'data: {json.dumps({"type": "done"})}\n\n'
            return
        except APIStatusError as e:
            if e.status_code == 529 and attempt < max_attempts - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s, 8s
                time.sleep(wait)
                continue
            raise
