import asyncio
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

ALERTS_URL = "https://ubilling.net.ua/aerialalerts/"
POLL_INTERVAL_SECONDS = 45

alert_state = {
    "enabled": False,
    "region": "Харківська область",
    "active": False,
    "changed": None,
    "per_region": {},
    "updated_at": None,
    "last_poll": None,
    "error": None,
}


def _match_region(states: dict, needle: str) -> tuple[str | None, dict | None]:
    needle_low = needle.lower()
    for name, info in states.items():
        if needle_low in name.lower():
            return name, info
    return None, None


async def _poll_once() -> None:
    from config import settings

    needle = settings.ALERT_REGION
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(ALERTS_URL, headers={"User-Agent": "Perevozka24/1.0 (logistics-app)"})
        resp.raise_for_status()
        data = resp.json()
    states = data.get("states") or {}
    per_region = {name: bool(info.get("alertnow")) for name, info in states.items()}
    name, info = _match_region(states, needle)
    alert_state.update(
        enabled=True,
        region=name or needle,
        active=bool(info.get("alertnow")) if info else False,
        changed=(info or {}).get("changed"),
        per_region=per_region,
        updated_at=data.get("cachedat"),
        last_poll=datetime.utcnow().isoformat(),
        error=None,
    )
    logger.info("[alerts] %s active=%s", alert_state["region"], alert_state["active"])


async def _alerts_loop() -> None:
    while True:
        try:
            await _poll_once()
        except Exception as e:
            logger.warning("[alerts] poll failed: %s", e)
            alert_state.update(last_poll=datetime.utcnow().isoformat(), error=str(e)[:200])
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_alerts_polling() -> None:
    from config import settings

    alert_state.update(enabled=True, region=settings.ALERT_REGION)
    logger.info("[alerts] polling air-raid alerts for %s", settings.ALERT_REGION)
    asyncio.create_task(_alerts_loop())
