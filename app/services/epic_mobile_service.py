# -*- coding: utf-8 -*-
"""Epic mobile weekly freebies (Android / iOS) discovery and injection.

Mobile freebies are separate store SKUs (e.g. ``/p/<slug>-android-<hash>`` and
``/p/<slug>-ios-<hash>``), claimed through the exact same $0 desktop web checkout
flow as PC freebies. Both platform switches are disabled by default:

- ``EPIC_MOBILE_ANDROID``
- ``EPIC_MOBILE_IOS``

Discovery runs inside an active ``store.epicgames.com`` page context so Cloudflare
accepts the request. Any discovery error degrades gracefully to PC-only collection.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from loguru import logger
from playwright.async_api import Page

from models import PromotionGame
from settings import settings

DISCOVER_API = (
    "https://egs-platform-service.store.epicgames.com/api/v2/public/discover/home"
    "?count=10&country={country}&locale={locale}&platform={platform}&start=0&store=EGS"
)
LOCALE = "en"
COUNTRIES = ("US", "CN")

VALID_PLATFORMS = ("android", "ios")
PLATFORM_LABELS = {"android": "Android", "ios": "iOS"}
PLATFORM_FLAGS = {"android": "EPIC_MOBILE_ANDROID", "ios": "EPIC_MOBILE_IOS"}

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}

FETCH_JSON_JS = """
async (url) => {
  try {
    const response = await fetch(url, {
      headers: {accept: 'application/json'},
      credentials: 'include',
    });
    if (!response.ok) {
      return {ok: false, status: response.status, body: ''};
    }
    return {ok: true, status: response.status, body: await response.text()};
  } catch (error) {
    return {ok: false, status: 0, body: '', error: String(error)};
  }
}
"""


def enabled_platforms() -> list[str]:
    """Return enabled mobile platforms from environment overrides or EpicSettings."""
    platforms: list[str] = []
    for platform in VALID_PLATFORMS:
        flag_name = PLATFORM_FLAGS[platform]
        raw_env = os.getenv(flag_name)
        if raw_env is not None and raw_env.strip():
            normalized = raw_env.strip().lower()
            if normalized in _TRUTHY:
                platforms.append(platform)
                continue
            if normalized in _FALSY:
                continue
        if bool(getattr(settings, flag_name, False)):
            platforms.append(platform)
    return platforms


def is_claimable_free(content: dict) -> bool:
    """Return True when the mobile entry is actively claimable for $0."""
    for entry in content.get("purchase") or []:
        if not isinstance(entry, dict):
            continue
        price = entry.get("price") or {}
        if entry.get("purchaseType") == "Claim" and price.get("decimalPrice") == 0:
            return True
    return False


def parse_free_games(payload: dict, platform: str) -> list[dict]:
    """Extract currently free mobile games from an Epic discover payload."""
    games: list[dict] = []
    for section in payload.get("data") or []:
        if not isinstance(section, dict) or section.get("type") != "freeGame":
            continue
        for offer in section.get("offers") or []:
            if not isinstance(offer, dict):
                continue
            content = offer.get("content") or {}
            if not isinstance(content, dict):
                continue
            slug = ((content.get("mapping") or {}).get("slug") or "").strip()
            if not slug or not is_claimable_free(content):
                continue

            offer_id = ""
            namespace = ""
            for entry in content.get("purchase") or []:
                if not isinstance(entry, dict) or entry.get("purchaseType") != "Claim":
                    continue
                purchase_payload = entry.get("purchasePayload") or {}
                offer_id = (purchase_payload.get("offerId") or "").strip()
                namespace = (purchase_payload.get("sandboxId") or "").strip()
                break

            games.append(
                {
                    "slug": slug,
                    "title": (content.get("title") or slug).strip(),
                    "platform": platform,
                    "offer_id": offer_id or (offer.get("offerId") or "").strip(),
                    "namespace": namespace,
                }
            )
    return games


async def _fetch_json(page: Page, url: str) -> dict | None:
    try:
        result = await page.evaluate(FETCH_JSON_JS, url)
    except Exception as err:
        logger.debug("Epic mobile: in-page fetch raised | url={} | err={!r}", url, err)
        result = None

    if isinstance(result, dict) and result.get("ok"):
        try:
            return json.loads(result.get("body") or "{}")
        except ValueError as err:
            logger.debug("Epic mobile: invalid JSON payload | err={!r}", err)
            return None

    if isinstance(result, dict):
        logger.debug(
            "Epic mobile: in-page fetch rejected | status={!r} | err={!r} | page_url={}",
            result.get("status"),
            result.get("error"),
            getattr(page, "url", "?"),
        )

    try:
        await page.wait_for_timeout(1500)
        result = await page.evaluate(FETCH_JSON_JS, url)
        if isinstance(result, dict) and result.get("ok"):
            return json.loads(result.get("body") or "{}")
    except Exception as err:
        logger.debug("Epic mobile: in-page fetch retry failed | url={} | err={!r}", url, err)

    try:
        response = await page.request.get(
            url,
            headers={"accept": "application/json", "referer": "https://store.epicgames.com/"},
            timeout=20000,
        )
    except Exception as err:
        logger.debug("Epic mobile: page.request failed | url={} | err={!r}", url, err)
        return None

    if response is None or not response.ok:
        logger.debug(
            "Epic mobile: page.request non-OK | status={!r}", getattr(response, "status", None)
        )
        return None
    try:
        return json.loads(await response.text())
    except ValueError as err:
        logger.debug("Epic mobile: page.request invalid JSON | err={!r}", err)
        return None


async def _discover_platform(page: Page, platform: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for country in COUNTRIES:
        url = DISCOVER_API.format(country=country, locale=LOCALE, platform=platform)
        payload = await _fetch_json(page, url)
        if payload is None:
            continue
        for game in parse_free_games(payload, platform):
            if game["slug"] in seen:
                continue
            seen.add(game["slug"])
            found.append(game)
    logger.debug("Epic mobile: discovered {} ({})", len(found), platform)
    return found


@asynccontextmanager
async def _store_origin_page(page: Page) -> AsyncIterator[Page]:
    if "store.epicgames.com" in (page.url or ""):
        yield page
        return

    temp_page = await page.context.new_page()
    try:
        await temp_page.goto(
            "https://store.epicgames.com/en-US/", wait_until="domcontentloaded", timeout=60000
        )
        yield temp_page
    finally:
        with suppress(Exception):
            await temp_page.close()


def _to_promotion(game: dict, product_url_prefix: str) -> PromotionGame:
    platform_label = PLATFORM_LABELS.get(game["platform"], game["platform"])
    return PromotionGame(
        title=f"{game['title']} ({platform_label})",
        id=game["offer_id"],
        namespace=game["namespace"],
        description=f"Epic Games mobile freebie ({platform_label})",
        offerType="BASE_GAME",
        url=f"{product_url_prefix.rstrip('/')}/{game['slug']}",
    )


async def append_mobile_promotions(
    page: Page,
    promotions: list[PromotionGame],
    product_url_prefix: str,
    exclude_offer_ids: set[str] | None = None,
) -> list[PromotionGame]:
    """Append unclaimed mobile promotions when mobile switches are enabled."""
    platforms = enabled_platforms()
    if not platforms:
        return promotions

    logger.debug("Epic mobile: discovering on page={}", getattr(page, "url", "?"))

    owned = exclude_offer_ids or set()
    try:
        existing_urls = {promotion.url for promotion in promotions}
        extras: list[PromotionGame] = []
        async with _store_origin_page(page) as discovery_page:
            logger.debug("Epic mobile: discovering on page={}", discovery_page.url)
            for platform in platforms:
                for game in await _discover_platform(discovery_page, platform):
                    promotion = _to_promotion(game, product_url_prefix)
                    if promotion.url in existing_urls:
                        logger.debug("Epic mobile: skip duplicate url={}", promotion.url)
                        continue
                    if promotion.id and promotion.id in owned:
                        logger.success(
                            "Game already claimed previously - title='{}' url='{}'",
                            promotion.title,
                            promotion.url,
                        )
                        continue
                    existing_urls.add(promotion.url)
                    extras.append(promotion)
    except Exception as err:
        logger.warning("Epic mobile: discovery failed, continuing with PC only | err={!r}", err)
        return promotions

    if not extras:
        logger.info("Epic mobile: no free mobile game found this week")
        return promotions

    logger.info(
        "📱 Epic mobile: including {} free mobile item(s) | {}",
        len(extras),
        ", ".join(f"{item.title} -> {item.url}" for item in extras),
    )
    return [*promotions, *extras]
