"""
Product Ranker
--------------
Deterministic, explainable ranking for small result sets.

Default strategy:
1) Prefer products flagged as "is_default" (if present)
2) Prefer exact phrase matches in name (if a query was provided via context)
3) Stable alphabetical order for determinism

You can extend this to include telemetry, bundle frequency, or pricing tiers.
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any


class ProductRanker:
    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = weights or {}

    def _score(self, p: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> tuple:
        name = (p.get("name") or "").lower()
        is_default = p.get("is_default", False)
        q = (context or {}).get("query") or ""
        q = q.lower().strip()

        exact_hit = (1 if q and q in name else 0)

        # lower tuple sorts earlier; invert booleans
        return (
            0 if is_default else 1,  # prefer defaults
            0 if exact_hit else 1,   # prefer exact name contains
            name                     # then alphabetical
        )

    def rank(self, products: List[Dict[str, Any]], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return sorted(products, key=lambda p: self._score(p, context))