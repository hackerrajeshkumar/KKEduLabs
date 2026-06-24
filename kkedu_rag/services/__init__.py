"""Service layer: orchestration that wires the domain + agents into a turn.

``ingestion`` loads documents into the store; ``pipeline`` runs one Q&A turn
(answerer -> verifier -> memory). The ``cli`` interface drives these. Consumers
import concrete modules; this init stays free of heavy imports.
"""
