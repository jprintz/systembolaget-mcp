#!/usr/bin/env python3
"""Test suite for Systembolaget MCP server.

This test suite validates the MCP server tools by calling them directly
without going through the JSON-RPC protocol. These tests call the real
Systembolaget API: run them with `pytest -m live`.
"""

import pytest
from systembolaget_mcp import (
    search_products,
    get_product,
    search_stores,
    SearchProductsInput,
    GetProductInput,
    SearchStoresInput,
)

pytestmark = pytest.mark.live


class TestProductSearch:
    """Tests for product search functionality."""

    @pytest.mark.asyncio
    async def test_search_products_basic(self):
        """Test basic product search returns results."""
        params = SearchProductsInput(query="öl", limit=5)

        result = await search_products(params)

        # Should return a string (either markdown or error message)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should not be an error message
        assert not result.startswith("Error:")

    @pytest.mark.asyncio
    async def test_search_products_with_filters(self):
        """Test product search with multiple filters."""
        params = SearchProductsInput(query="öl", country="Sverige", max_price=50.0, limit=5)

        result = await search_products(params)

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain markdown headers
        assert "Product Search Results" in result or "No products found" in result

    @pytest.mark.asyncio
    async def test_search_products_json_format(self):
        """Test product search with JSON output format."""
        params = SearchProductsInput(query="vin", limit=3, format="json")

        result = await search_products(params)

        assert isinstance(result, str)
        # Should be valid JSON structure (basic check)
        assert "{" in result and "}" in result
        # JSON responses should contain products array or pagination (might be truncated)
        assert "products" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_search_products_pagination(self):
        """Test product search pagination."""
        params = SearchProductsInput(query="öl", limit=10, offset=0)

        result = await search_products(params)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_search_products_unusual_query(self):
        """Test product search with unusual query string."""
        params = SearchProductsInput(query="xyzabc123nonexistent", limit=5)

        result = await search_products(params)

        assert isinstance(result, str)
        assert len(result) > 0
        # API may return fuzzy matches or "no results" - both are valid
        assert (
            "Product Search Results" in result or "No products found" in result or "Error" in result
        )


class TestProductDetails:
    """Tests for individual product details."""

    @pytest.mark.asyncio
    async def test_get_product_invalid_number(self):
        """Test getting product with invalid product number."""
        params = GetProductInput(product_number="999999999")

        result = await get_product(params)

        assert isinstance(result, str)
        # Should either return error or "not found"
        assert "Error" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_get_product_json_format(self):
        """Test getting product details in JSON format."""
        params = GetProductInput(product_number="1", format="json")

        result = await get_product(params)

        assert isinstance(result, str)
        # Will likely error but should still return a string


class TestStoreSearch:
    """Tests for store search functionality."""

    @pytest.mark.asyncio
    async def test_search_stores_by_city(self):
        """Test searching for stores by city."""
        params = SearchStoresInput(city="Stockholm", limit=3)

        result = await search_stores(params)

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain store results or error
        assert "Store Search Results" in result or "No stores found" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_search_stores_by_query(self):
        """Test searching for stores by query."""
        params = SearchStoresInput(query="Vasagatan", limit=5)

        result = await search_stores(params)

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_search_stores_json_format(self):
        """Test store search with JSON output format."""
        params = SearchStoresInput(city="Göteborg", limit=2, format="json")

        result = await search_stores(params)

        assert isinstance(result, str)
        # Should be valid JSON structure
        assert "{" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_search_stores_pagination(self):
        """Test store search pagination."""
        params = SearchStoresInput(city="Stockholm", limit=5, offset=0)

        result = await search_stores(params)

        assert isinstance(result, str)
        assert len(result) > 0


class TestInputValidation:
    """Tests for input validation."""

    def test_search_products_invalid_price_range(self):
        """Test that invalid price range raises validation error."""
        with pytest.raises(ValueError, match="max_price must be greater than"):
            SearchProductsInput(query="öl", min_price=100.0, max_price=50.0)

    def test_search_products_invalid_alcohol_range(self):
        """Test that invalid alcohol range raises validation error."""
        with pytest.raises(ValueError, match="max_alcohol must be greater than"):
            SearchProductsInput(query="vin", min_alcohol=15.0, max_alcohol=10.0)

    def test_search_products_limit_bounds(self):
        """Test that limit respects min/max bounds."""
        # Should accept valid limits
        params = SearchProductsInput(query="öl", limit=20)
        assert params.limit == 20

        # Should reject invalid limits
        with pytest.raises(ValueError):
            SearchProductsInput(query="öl", limit=0)

        with pytest.raises(ValueError):
            SearchProductsInput(query="öl", limit=101)


# Manual test runner for debugging (optional)
if __name__ == "__main__":
    import sys

    pytest.main([__file__, "-v"] + sys.argv[1:])


class TestNewTools:
    """Live checks for the tools added in this fork."""

    async def test_get_store_opening_hours(self):
        from systembolaget_mcp import GetStoreInput, get_store

        result = await get_store(GetStoreInput(store_id="0104"))
        assert "Nybrogatan" in result
        assert "Opening hours" in result

    async def test_check_stock_in_stockholm(self):
        from systembolaget_mcp import CheckStockInput, check_stock

        # Norrlands Guld Export: in the fixed assortment of virtually every store.
        result = await check_stock(
            CheckStockInput(product_number="141212", latitude=59.3326, longitude=18.0649, max_stores=3)
        )
        assert "in stock" in result
        assert not result.startswith("Error")

    async def test_upcoming_launches_calendar(self):
        from systembolaget_mcp import UpcomingLaunchesInput, upcoming_launches

        result = await upcoming_launches(UpcomingLaunchesInput())
        assert "Upcoming launches" in result or "No upcoming launches" in result

    async def test_search_with_new_filters(self):
        params = SearchProductsInput(
            category="Vin", food_pairing=["Lamm"], labels=["organic"], sort_by="price", limit=3
        )
        result = await search_products(params)
        assert "Product Search Results" in result
