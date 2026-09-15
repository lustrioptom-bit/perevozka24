from __future__ import annotations

# In-memory wizard/input states.
# {user_id: {"type": ..., "cities": [...], "radius_km": int, "frequency": str}}
PREFS_STATE: dict[int, dict] = {}
PREFS_ADDING_CITY: set[int] = set()

# {user_id: order_id} — waiting for custom price text
PRICE_STATE: dict[int, int] = {}

# {user_id: {"order_id": int, "reviewee_id": int[, "rating": int, "comment": str|None, "step": str]}}
REVIEW_STATE: dict[int, dict] = {}