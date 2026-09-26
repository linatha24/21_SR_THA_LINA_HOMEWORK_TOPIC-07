"""
tools.py
--------
Real implementations of every tool. This is the "business logic" layer.
Tools never trust the caller blindly - inputs arrive already validated
by schemas.py (via harness.py), but we still guard against bad state
(e.g. unknown product id, insufficient stock) and return structured
results instead of raising raw exceptions, so the agent can observe
what happened and decide what to do next.
"""

from typing import Any, Dict

# --- Fake in-memory "database" -------------------------------------------
_PRODUCTS: Dict[int, Dict[str, Any]] = {
    1: {"id": 1, "name": "Dell XPS 13 Laptop", "stock": 5, "price": 999},
    2: {"id": 2, "name": "MacBook Air M2", "stock": 0, "price": 1099},
    3: {"id": 3, "name": "Logitech Wireless Mouse", "stock": 42, "price": 25},
    4: {"id": 4, "name": "ThinkPad X1 Carbon Laptop", "stock": 3, "price": 1299},
}


def search_products(query: str) -> Dict[str, Any]:
    """Return products whose name matches query keywords (case-insensitive)."""
    q_words = query.lower().split()
    if not q_words:
        return {"ok": True, "results": list(_PRODUCTS.values())}
    matches = [
        p for p in _PRODUCTS.values()
        if all(word in p["name"].lower() for word in q_words)
    ]
    return {"ok": True, "results": matches}


def check_stock(product_id: int) -> Dict[str, Any]:
    """Return the current stock level for a product."""
    product = _PRODUCTS.get(product_id)
    if product is None:
        return {"ok": False, "error": "NOT_FOUND", "message": f"No product with id {product_id}"}
    return {"ok": True, "product_id": product_id, "name": product["name"], "stock": product["stock"]}


def delete_product(product_id: int) -> Dict[str, Any]:
    """Admin-only: remove a product from the catalog entirely."""
    if product_id not in _PRODUCTS:
        return {"ok": False, "error": "NOT_FOUND", "message": f"No product with id {product_id}"}
    removed = _PRODUCTS.pop(product_id)
    return {"ok": True, "message": f"Deleted product '{removed['name']}' (id={product_id})."}


# Registry mapping tool name -> the actual python function to call
TOOL_IMPLEMENTATIONS = {
    "search_products": search_products,
    "check_stock": check_stock,
    "delete_product": delete_product,
}