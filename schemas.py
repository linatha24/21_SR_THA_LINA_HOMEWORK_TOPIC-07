"""
schemas.py
----------
Explicit input schemas for every tool. These describe exactly what
arguments the model is allowed to send when it calls a tool: field
names, types, which are required, and any constraints (e.g. positive
integers). Pydantic both validates the data AND lets us auto-generate
the JSON schema the LLM needs to see.
"""

from pydantic import BaseModel, Field, field_validator


class SearchProductsInput(BaseModel):
    """Search products in the catalog by keyword(s) or product name."""
    query: str = Field(..., description="Free text search keyword, e.g. 'laptop' or 'Dell'")

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v.strip()


class CheckStockInput(BaseModel):
    """Check the available stock level for a product given its integer ID."""
    product_id: int = Field(..., description="Product ID to check", gt=0)


class DeleteProductInput(BaseModel):
    """Admin-only: permanently delete a product from the catalog."""
    product_id: int = Field(..., description="Product ID to delete", gt=0)


# ---------------------------------------------------------------------------
# Tool registry: maps tool name -> pydantic input model
# Used to validate arguments AND build tool schemas for the LLM.
# ---------------------------------------------------------------------------
TOOL_INPUT_MODELS = {
    "search_products": SearchProductsInput,
    "check_stock": CheckStockInput,
    "delete_product": DeleteProductInput,
}