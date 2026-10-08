"""Offline tests: request building and formatting, with the API mocked."""

from typing import Any

import pytest

import systembolaget_mcp as sb


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace the API key lookup and HTTP calls; record the request."""
    calls: dict[str, Any] = {"response": {"products": [], "metadata": {"docCount": 0}}}

    async def fake_key() -> str:
        return "test-key"

    async def fake_request(url: str, params: Any = None, headers: Any = None) -> Any:
        calls.update(url=url, params=params, headers=headers)
        return calls["response"]

    monkeypatch.setattr(sb, "extract_api_key", fake_key)
    monkeypatch.setattr(sb, "make_api_request", fake_request)
    return calls


PRODUCT = {
    "productNameBold": "Stigbergets Amazing Haze",
    "productNameThin": "IPA",
    "productNumber": "3148715",
    "priceInclVat": 37.9,
    "volume": 330.0,
    "alcoholPercentage": 6.5,
    "categoryLevel1": "Öl",
    "country": "Sverige",
    "assortmentText": "Fast sortiment",
    "tasteClocks": [
        {"key": "TasteClockBitter", "value": 8},
        {"key": "TasteClockBody", "value": 7},
        {"key": "TasteClockSweetness", "value": 1},
    ],
    "tasteClockGroup": "Tydlig beska",
    "color": "Oklar, gulorange färg.",
    "aroma": "Humlearomatisk doft.",
    "taste": "Humlearomatisk, fruktig smak med tydlig beska.",
    "usage": "Serveras vid 8-10°C.",
    "tasteSymbols": "Grillat;Hamburgare",
    "grapes": None,
    "description": None,
}


async def test_search_uses_current_parameters(api: dict[str, Any]) -> None:
    params = sb.SearchProductsInput(
        query="IPA",
        category="Öl",
        country="Sverige",
        min_price=19.9,
        max_price=40.5,
        min_alcohol=5.0,
        max_alcohol=7.0,
        limit=5,
        offset=10,
    )
    await sb.search_products(params)

    assert api["url"].endswith("/productsearch/search")
    assert api["params"] == {
        "textQuery": "IPA",
        "categoryLevel1": "Öl",
        "country": "Sverige",
        "price.min": 19,
        "price.max": 41,
        "alcoholPercentage.min": 5.0,
        "alcoholPercentage.max": 7.0,
        "page": 3,
        "size": 5,
    }
    assert api["headers"]["Ocp-Apim-Subscription-Key"] == "test-key"


async def test_first_page_is_one(api: dict[str, Any]) -> None:
    await sb.search_products(sb.SearchProductsInput(query="vin", limit=10))
    assert api["params"]["page"] == 1


async def test_search_reports_doc_count(api: dict[str, Any]) -> None:
    api["response"] = {"products": [PRODUCT], "metadata": {"docCount": 278}}
    result = await sb.search_products(sb.SearchProductsInput(query="IPA", limit=1))
    assert "Found 278 products" in result


async def test_product_details_endpoint_and_formatting(api: dict[str, Any]) -> None:
    api["response"] = PRODUCT
    result = await sb.get_product(sb.GetProductInput(product_number="3148715"))

    assert api["url"].endswith("/product/productNumber/3148715")
    assert "**Price:** 37.9 SEK" in result
    assert "Bitterness (beska): 8/12 ●●●●●●●●○○○○" in result
    assert "Body (fyllighet): 7/12 ●●●●●●●○○○○○" in result
    assert "Sweetness (sötma): 1/12 ●○○○○○○○○○○○" in result
    assert "Style: Tydlig beska" in result
    assert "Aroma (doft): Humlearomatisk doft." in result
    assert "**Food Pairings:** Grillat, Hamburgare" in result
    assert "None" not in result


def test_products_without_taste_data_have_no_taste_sections() -> None:
    md = sb.format_product_markdown({"productNameBold": "X", "price": 10, "tasteClocks": []})
    assert "Taste clocks" not in md
    assert "Tasting notes" not in md
