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


async def test_tools_are_registered_read_only() -> None:
    tools = {tool.name: tool for tool in await sb.mcp.list_tools()}
    assert set(tools) == {
        "systembolaget_search_products",
        "systembolaget_get_product",
        "systembolaget_search_stores",
        "systembolaget_get_store",
        "systembolaget_check_stock",
        "systembolaget_upcoming_launches",
    }
    for tool in tools.values():
        annotations = tool.annotations
        assert annotations is not None, tool.name
        assert annotations.title, tool.name
        assert annotations.read_only_hint is True
        assert annotations.destructive_hint is False
        assert annotations.idempotent_hint is True
        assert annotations.open_world_hint is True


# --- new filters, stores, stock and launches -------------------------------------------


def test_new_search_filters_and_sorting() -> None:
    params = sb.SearchProductsInput(
        category="Vin",
        subcategory="Rött vin",
        food_pairing=["Lamm", "Nöt"],
        grape="Nebbiolo",
        labels=["organic", "vegan", "natural_wine"],
        vintage=2020,
        assortment="Fast sortiment",
        new_arrivals="last_month",
        max_sugar_g_per_l=3.5,
        packaging="Glasflaska",
        sort_by="price",
        sort_direction="desc",
        limit=10,
    )
    qp = sb.build_search_params(params)
    assert qp["categoryLevel2"] == "Rött vin"
    assert qp["tasteSymbols"] == ["Lamm", "Nöt"]
    assert qp["grapes"] == "Nebbiolo"
    assert qp["label"] == ["Ekologiskt"]
    assert qp["otherSelections"] == ["Vegansk", "Naturvin"]
    assert qp["vintage"] == 2020
    assert qp["assortmentText"] == "Fast sortiment"
    assert qp["newArrivalType"] == "Nytt senaste månaden"
    assert qp["sugarContent.max"] == 4
    assert qp["packagingLevel1"] == "Glasflaska"
    assert (qp["sortBy"], qp["sortDirection"]) == ("Price", "Descending")


STORE = {
    "siteId": "0104",
    "alias": None,
    "address": "Nybrogatan 47",
    "postalCode": "114 39",
    "city": "STOCKHOLM",
    "phone": "08-662 50 16",
    "isActive": True,
    "isTastingStore": False,
    "position": {"latitude": 59.3371, "longitude": 18.0790},
    "openingHours": [
        {"date": "2026-10-08T00:00:00", "openFrom": "10:00:00", "openTo": "19:00:00", "reason": None},
        {"date": "2026-10-09T00:00:00", "openFrom": "10:00:00", "openTo": "19:00:00", "reason": None},
        {"date": "2026-10-10T00:00:00", "openFrom": "10:00:00", "openTo": "15:00:00", "reason": None},
        {"date": "2026-10-11T00:00:00", "openFrom": "00:00:00", "openTo": "00:00:00", "reason": "-"},
        {"date": "2026-10-12T00:00:00", "openFrom": "00:00:00", "openTo": "00:00:00", "reason": "Helgdag"},
    ],
}


def at(stamp: str) -> "sb.datetime":
    return sb.datetime.fromisoformat(stamp).replace(tzinfo=sb.STOCKHOLM)


def test_open_now() -> None:
    assert sb.open_now(STORE, at("2026-10-08T12:00")) == "Open now (closes 19:00)"
    assert sb.open_now(STORE, at("2026-10-08T08:30")) == "Closed now (opens today 10:00)"
    assert sb.open_now(STORE, at("2026-10-10T16:00")) == "Closed now"  # no later opening listed
    assert sb.open_now(STORE, at("2026-10-09T19:30")) == "Closed now (opens Sat 10:00)"


def test_opening_hours_show_closed_days_and_reasons() -> None:
    hours = sb.format_opening_hours(STORE)
    assert "- Thu 2026-10-08: 10:00-19:00" in hours
    assert "- Sun 2026-10-11: closed\n" in hours
    assert "- Mon 2026-10-12: closed (Helgdag)" in hours


def test_normalize_store_id() -> None:
    assert sb.normalize_store_id("104") == "0104"
    assert sb.normalize_store_id(" 0104 ") == "0104"


@pytest.fixture
def routed(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Answer API calls by URL suffix; record the URLs requested."""
    routes: dict[str, Any] = {}
    seen: list[str] = []

    async def fake_key() -> str:
        return "test-key"

    async def fake_request(url: str, params: Any = None, headers: Any = None) -> Any:
        seen.append(url)
        for suffix, response in routes.items():
            if url.endswith(suffix):
                return response
        raise AssertionError(f"unexpected request {url}")

    monkeypatch.setattr(sb, "extract_api_key", fake_key)
    monkeypatch.setattr(sb, "make_api_request", fake_request)
    monkeypatch.setattr(sb, "_stores_cache", None)
    return {"routes": routes, "seen": seen}


async def test_check_stock_nearest_stores(routed: dict[str, Any]) -> None:
    far = {**STORE, "siteId": "1411", "address": "Linnégatan 28 B", "city": "GÖTEBORG",
           "position": {"latitude": 57.69, "longitude": 11.95}}
    routed["routes"].update({
        "/product/productNumber/141212": {"productId": "507949", "productNameBold": "Norrlands Guld",
                                          "productNameThin": "Export"},
        "/site/stores": [STORE, far],
        "/stockbalance/store/0104/507949": {"stock": 409, "shelf": "27-10-01", "isInStoreAssortment": True},
    })
    result = await sb.check_stock(
        sb.CheckStockInput(product_number="141212", latitude=59.34, longitude=18.07, max_stores=1)
    )
    # Stock is looked up by productId, at the nearest store only.
    assert routed["seen"][-1].endswith("/stockbalance/store/0104/507949")
    assert "Norrlands Guld - Export" in result
    assert "**409 in stock**, shelf 27-10-01" in result
    assert "Göteborg" not in result and "GÖTEBORG" not in result


async def test_check_stock_needs_a_place() -> None:
    result = await sb.check_stock(sb.CheckStockInput(product_number="141212"))
    assert result.startswith("Error:")


async def test_upcoming_launch_calendar(routed: dict[str, Any]) -> None:
    routed["routes"]["/productsearch/search"] = {
        "products": [],
        "metadata": {"docCount": 0},
        "filters": [{"name": "UpcomingLaunches", "searchModifiers": [
            {"value": "Lansering 2026-10-09", "count": 60},
            {"value": "Lansering 2026-10-15", "count": 25},
        ]}],
    }
    result = await sb.upcoming_launches(sb.UpcomingLaunchesInput())
    assert "- Fri 2026-10-09: 60 products" in result
    assert "- Thu 2026-10-15: 25 products" in result
