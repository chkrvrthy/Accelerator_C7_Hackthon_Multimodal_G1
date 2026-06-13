"""Image RAG package — embedder, vector store, retriever.

OWNER: Person B
SPRINT CONCEPTS: Sprint 3 — Chunking + embeddings + LanceDB + LlamaIndex.

The public surface other slices use is exactly one class — ``LanceRetriever``
— which implements the ``Retriever`` Protocol. The brand agent imports
``Retriever`` from ``src.contracts``, NOT ``LanceRetriever`` directly. That
contract decoupling is what lets Person C ship before Person B finishes.
"""

__all__: list[str] = []
