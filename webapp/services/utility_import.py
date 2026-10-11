import asyncio
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from bot.utils.geo import geo_stats_snapshot, _geo_stats_delta
from db.engine import async_session
from db.models import GeocodeCache, MapEvent, User, UserRole
from webapp.services.events_import import _fetch_channel_messages, _cached_geocode

logger = logging.getLogger(__name__)

SOURCE = "avariukaxarkiv"
FETCH_INTERVAL_SECONDS = 600
UTILITY_TTL_HOURS = 6
# Nominatim viewbox for Kharkiv city: left,top,right,bottom (lng/lat)
KHARKIV_VIEWBOX = "36.10,50.10,36.40,49.90"

utility_state = {
    "enabled": False,
    "source": SOURCE,
    "last_run": None,
    "last_sections": 0,
    "last_inserted": 0,
    "last_updated": 0,
    "last_error": None,
}

_STREET_PREFIX = r"(?:вул\.|вулиця|вулиці|пров\.|провулок|просп\.|проспект|проїзд|проезд|шосе|в['’]їзд|бульв\.|бульвар|набережна|площа|майдан|тупик)"
_STREET_RE = re.compile(_STREET_PREFIX + r"\s*[^,():;\n]+", re.I)
_STREET_PREFIX_STRIP = re.compile(_STREET_PREFIX + r"\s*", re.I)

_HEADER_POWER = re.compile(r"^[^\w]*(\u26a1|електро)", re.I)
_HEADER_WATER = re.compile(r"^[^\w]*([\U0001F4A7\U0001F525\U0001F6B0\U0001F4A6]|(холодне|гаряче)?\s*водо)", re.I)
_DIGEST_HINT = re.compile(r"аварійні роботи|комунальні", re.I)

_STOP_TAIL = re.compile(
    r"\s+(?:всі|все|будинки|будинок|та|і|провулках|вулицях|адреси|район|райони)\s*$",
    re.I,
)
_HOUSE = r"\d+(?:[-\u2013]\d+)*(?:[-\u2013][А-Яа-яІіЇїЄєҐґ])?(?:/\d+)?"
_TRAILING_NUMBERS = re.compile(rf"(?:\s+{_HOUSE}(?:\s*,\s*{_HOUSE})*)+$")


def _header_service(line: str) -> str | None:
    stripped = line.lstrip()
    if _HEADER_POWER.match(stripped):
        return "power"
    if _HEADER_WATER.match(stripped):
        return "water"
    return None


def _clean_street(raw: str) -> str:
    s = re.sub(r"\s+", " ", raw).strip(" .,;:-\u2013\u2014")
    s = _TRAILING_NUMBERS.sub("", s)
    s = _STOP_TAIL.sub("", s)
    return re.sub(r"\s+", " ", s).strip(" .,;:-\u2013\u2014")


def _valid_street(street: str) -> bool:
    if "/" in street:
        return False
    body = _STREET_PREFIX_STRIP.sub("", street).strip()
    return len(body) >= 3 and bool(re.search(r"[А-Яа-яЁёІіЇїЄєҐґ]{3}", body))


def _parse_sections(messages: list[str]) -> list[tuple[str, str, str]]:
    """Extract (event_type, street, description) from outage digests."""
    results: list[tuple[str, str, str]] = []
    for text in messages:
        if not _DIGEST_HINT.search(text):
            continue
        current: str | None = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            svc = _header_service(line)
            if svc:
                current = svc
                continue
            if current is None:
                continue
            matches = list(_STREET_RE.finditer(line))
            for i, match in enumerate(matches):
                end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
                segment = line[match.start() : end]
                street = _clean_street(match.group(0))
                if not _valid_street(street):
                    continue
                if street.lower() not in segment.lower():
                    continue
                desc = re.sub(r"\s+", " ", segment).strip(" ,;:-\u2013\u2014")
                results.append((current, street, desc[:500]))
    return results


async def _run_cycle() -> None:
    from config import settings

    messages = await _fetch_channel_messages(SOURCE)
    sections = _parse_sections(messages)
    utility_state.update(
        last_run=datetime.utcnow().isoformat(),
        last_sections=len(sections),
        last_error=None,
    )
    if not sections:
        logger.info("[utility:%s] no outage sections found", SOURCE)
        return

    async with async_session() as session:
        purge = datetime.utcnow() - timedelta(days=14)
        await session.execute(delete(GeocodeCache).where(GeocodeCache.last_try < purge))

        admins = settings.ADMIN_IDS
        if not admins:
            logger.warning("[utility] no ADMIN_IDS configured, skip")
            return
        system_user_id = admins[0]
        existing_user = (await session.execute(select(User).where(User.id == system_user_id))).scalar_one_or_none()
        if not existing_user:
            session.add(
                User(
                    id=system_user_id,
                    username="_import",
                    full_name="Импорт событий",
                    role=UserRole.admin,
                    rating=5.0,
                )
            )
            await session.commit()

        now = datetime.utcnow()
        ttl = timedelta(hours=UTILITY_TTL_HOURS)
        stats = {"geocoded": 0, "cache_hits": 0, "inserted": 0, "updated": 0}
        geo_before = geo_stats_snapshot()
        seen: set[tuple[str, str]] = set()

        for event_type, street, description in sections:
            key = (event_type, street.lower())
            if key in seen:
                continue
            seen.add(key)
            coords = await _cached_geocode(
                session, street, now, stats, viewbox=KHARKIV_VIEWBOX, bounded=True
            )
            if not coords:
                continue
            lat, lng = coords
            existing = (
                await session.execute(
                    select(MapEvent)
                    .where(
                        MapEvent.user_id == system_user_id,
                        MapEvent.event_type == event_type,
                        MapEvent.expires_at > now,
                        MapEvent.description.ilike(f"%{street}%"),
                    )
                    .order_by(MapEvent.created_at.desc())
                )
            ).scalars().first()
            if existing:
                existing.lat = lat
                existing.lng = lng
                existing.created_at = now
                existing.expires_at = now + ttl
                existing.description = description
                stats["updated"] += 1
                continue
            session.add(
                MapEvent(
                    user_id=system_user_id,
                    lat=lat,
                    lng=lng,
                    event_type=event_type,
                    description=description,
                    created_at=now,
                    expires_at=now + ttl,
                )
            )
            stats["inserted"] += 1
            await session.flush()

        await session.commit()
        logger.info(
            "[utility:%s] sections %d, inserted %d, updated %d",
            SOURCE,
            len(sections),
            stats["inserted"],
            stats["updated"],
        )
        utility_state.update(
            last_inserted=stats["inserted"],
            last_updated=stats["updated"],
        )
        delta = _geo_stats_delta(geo_before)
        utility_state["geo_detail"] = (
            f"ok:{delta['ok']}|429:{delta['rate_limited']}|http:{delta['http_other']}|exc:{delta['exc']}"
        )


async def _utility_loop() -> None:
    while True:
        try:
            await _run_cycle()
        except Exception as e:
            logger.warning("[utility:%s] cycle failed: %s", SOURCE, e)
            utility_state.update(last_run=datetime.utcnow().isoformat(), last_error=str(e)[:200])
        await asyncio.sleep(FETCH_INTERVAL_SECONDS)


def start_utility_import() -> None:
    utility_state.update(enabled=True)
    logger.info("[utility] watching channel: %s", SOURCE)
    asyncio.create_task(_utility_loop())
