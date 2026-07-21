"""Synergy layer — the ONLY package allowed to import BOTH engines.

``bazi_engine.bazi`` (BaZi) and ``bazi_engine.zwds`` (ZWDS) are two independent,
engine-separated calculation cores that must never import each other. This
``synergy`` package sits ABOVE both and is the single sanctioned place to combine
them. It is still a Level-4 engine package, so it must NOT import Level-5
(``bazi_engine.routers.*`` or ``bazi_engine.app``).

Placeholder only for now (ZWDS-P0-03) — no logic yet; the standing import-layer
guards in ``tests/test_import_hierarchy.py`` enforce the rules above for future
code.
"""
