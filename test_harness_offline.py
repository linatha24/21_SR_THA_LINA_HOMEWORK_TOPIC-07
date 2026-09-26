"""
test_harness_offline.py
------------------------
Quick offline sanity checks for permission control, validation, and
error handling — no API key or network call needed. Run with:

    python test_harness_offline.py
"""

from harness import run_tool

print("1) Customer searches products (allowed):")
print(run_tool("search_products", {"query": "laptop"}, role="customer", call_count=1))

print("\n2) Customer tries to delete a product (should be denied):")
print(run_tool("delete_product", {"product_id": 1}, role="customer", call_count=2))

print("\n3) Admin deletes a product (allowed):")
print(run_tool("delete_product", {"product_id": 3}, role="admin", call_count=3))

print("\n4) Invalid input - negative product_id (should fail validation):")
print(run_tool("check_stock", {"product_id": -5}, role="admin", call_count=4))

print("\n5) Unregistered tool call - e.g. buy_product (should fail with UNKNOWN_TOOL):")
print(run_tool("buy_product", {"product_id": 2, "quantity": 1}, role="customer", call_count=5))

print("\n6) Unknown product id (should fail with NOT_FOUND):")
print(run_tool("check_stock", {"product_id": 999}, role="customer", call_count=6))