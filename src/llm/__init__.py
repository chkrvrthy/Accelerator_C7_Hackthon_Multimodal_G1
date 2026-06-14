"""LLM gateway layer.

Public surface is intentionally tiny — the rest of the codebase talks to LLMs
through the ``LLMClient`` / ``VisionLLM`` Protocols defined in
``src/contracts.py``. Concrete classes live next to this file and are imported
lazily so a teammate who does not own this slice (e.g. Person C) does not have
to install the full LLM dependency tree just to run their tests against fakes.

OWNER: Person A
SPRINT CONCEPTS: Sprint 1 (OpenAI Chat Completion standard), Sprint 2 (HF stub),
                 Sprint 5 (cost optimization).
"""

# NOTE: keep this file import-cheap. Anything that pulls openai/transformers
# must live behind a function so other slices stay snappy.

__all__: list[str] = []
