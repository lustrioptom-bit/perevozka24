import asyncio
import html
import logging
import re
from datetime import datetime, timedelta

import httpx
from sqlalchemy import delete, select

from config import settings
from bot.utils.geo import _nominatim_geocode, geo_stats_snapshot, _geo_stats_delta, haversine
from db.engine import async_session
from db.models import GeocodeCache, MapEvent, User, UserRole
from webapp.routers.api import MAP_EVENT_TTL_HOURS

logger = logging.getLogger(__name__)

import_state = {
    "enabled": False,
    "sources": [],
    "last_run": None,
    "last_candidates": 0,
    "last_geocoded": 0,
    "last_inserted": 0,
    "last_extended": 0,
    "last_error": None,
}

FETCH_INTERVAL_SECONDS = 60
MAX_GEOCODES_PER_CYCLE = 10
DEDUP_DISTANCE_KM = 0.4
NOMINATIM_PAUSE = 1.5
CACHE_TTL = timedelta(days=7)
NEGATIVE_CACHE_TTL = timedelta(hours=3)
REPORT_TZ_OFFSET_HOURS = 3
TIME_TOLERANCE_MINUTES = 3

_STREET_LEXEME_RE = re.compile(
    r"\b(?:улица|ул\.|бульвар|проспект|пр-т|переулок|пер\.|площадь|пл\.|набережная|шоссе|проезд)\b",
    re.I,
)

TRAFFIC_PATTERNS = [
    (re.compile(r"перекры", re.I), "traffic"),
    (re.compile(r"перекоыт", re.I), "traffic"),
    (re.compile(r"пробк", re.I), "traffic"),
    (re.compile(r"затор", re.I), "traffic"),
    (re.compile(r"\bдтп\b", re.I), "accident"),
    (re.compile(r"авари", re.I), "accident"),
    (re.compile(r"столкн", re.I), "accident"),
    (re.compile(r"вмял", re.I), "accident"),
    (re.compile(r"ремонт", re.I), "road"),
    (re.compile(r"светофор", re.I), "road"),
    (re.compile(r"\bяма|\bямы", re.I), "road"),
]

MILITARY_BLACKLIST = (
    "тцк", "военком", "облав", "повест", "комендант", "блокпост",
    "блок-пост", "военн", "рекрут", "зелён", "зеленый бус", "мусор",
    "петух", "пидор", "мудак", "гопот", "борух",
)

_LEADING_TIME_RE = re.compile(r"^(\d{1,2}:\d{2})\s*")
_TRAILING_TIME_RE = re.compile(r"(?<!\d)(\d{1,2}:\d{2})\s*$")
_BLOCK_RE = re.compile(r'tgme_widget_message_text[^>]*>(.*?)</div>', re.S)

_WORD = r"А-Яа-яЁёІіЇїЄєҐґ"
_STREET_LEXEME_FIRST = re.compile(
    rf"\b(?:улица|ул\.|бульвар|проспект|пр-т|переулок|пер\.|площадь|пл\.|набережная|шоссе|проезд)"
    rf"\s+[{_WORD}][{_WORD}.\'\-\s]{{1,60}}?(?:,\s*\d{{1,4}}[\d/\-.\w]*)?",
    re.I,
)
_NAME_THEN_STREET = re.compile(
    rf"[{_WORD}][{_WORD}\s\'\-\u0027]{{2,50}}?\b(?:улица|провулок|площадь|набережная|пр-т)\b(?:,\s*\d{{1,4}}[\d/\-.\w]*)?",
    re.I,
)
_PRE_KEYWORD = re.compile(
    rf"^\s*([{_WORD}][{_WORD}.\'\-\s]{{2,50}}?)(?=\s*(?:перекрыв|перекоыт|стопа|стоит|стоят|не\s+работа|ремонт\b|пробк|затор))",
    re.I,
)


def _extract_report_time(line: str) -> tuple[str, datetime | None]:
    """Strip a leading/trailing HH:MM timestamp and convert it to naive UTC."""
    stamp = None
    lead = _LEADING_TIME_RE.match(line)
    if lead:
        stamp = lead.group(1)
        line = line[lead.end() :]
    else:
        tail = _TRAILING_TIME_RE.search(line)
        if tail:
            stamp = tail.group(1)
            line = line[: tail.start()]
    line = re.sub(r"\s+", " ", line).strip(" ,.;!–—„\"'")
    if not stamp:
        return line, None
    try:
        hour, minute = (int(x) for x in stamp.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return line, None
    except (ValueError, TypeError):
        return line, None
    local_now = datetime.utcnow() + timedelta(hours=REPORT_TZ_OFFSET_HOURS)
    local_report = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if local_report - local_now > timedelta(minutes=TIME_TOLERANCE_MINUTES):
        local_report -= timedelta(days=1)
    return line, local_report - timedelta(hours=REPORT_TZ_OFFSET_HOURS)


def _extract_messages(page: str) -> list[str]:
    texts = []
    for match in _BLOCK_RE.finditer(page):
        block = match.group(1)
        block = re.sub(r"<br\s*/?>", "\n", block)
        block = re.sub(r"</p><p>", "\n", block)
        block = re.sub(r"<[^>]+>", "", block)
        block = html.unescape(block).strip()
        if block:
            texts.append(block)
    return texts


async def _fetch_channel_messages(username: str) -> list[str]:
    url = f"https://t.me/s/{username}"
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        resp.raise_for_status()
        return _extract_messages(resp.text)


def _address_candidates(line: str) -> list[str]:
    candidates = []
    for regex in (_STREET_LEXEME_FIRST, _NAME_THEN_STREET):
        matches = regex.findall(line)
        if matches:
            candidates.append(matches[-1])
    match = _PRE_KEYWORD.search(line)
    if match:
        candidates.append(match.group(1))
    first_clause = line.split(",", 1)[0].strip()
    if first_clause != line:
        candidates.append(first_clause)
    candidates.append(line)
    cleaned = []
    for cand in candidates:
        cand = re.sub(r"\s+", " ", cand).strip(" ,.;!–—„\"'")
        if len(cand) >= 3 and cand not in cleaned:
            cleaned.append(cand)
    return cleaned[:4]


def _formulations(address: str) -> list[str]:
    if _STREET_LEXEME_RE.search(address):
        return [f"Харьков, {address}"]
    return [f"Харьков, {address} улица", f"Харьков, {address}"]


def _candidate_lines(messages: list[str]) -> list[tuple[str, str, datetime | None]]:
    out = []
    for text in messages:
        for line in text.splitlines():
            cleaned, report_dt = _extract_report_time(line)
            if len(cleaned) < 8:
                continue
            low = cleaned.lower()
            if any(word in low for word in MILITARY_BLACKLIST):
                continue
            for pattern, event_type in TRAFFIC_PATTERNS:
                if pattern.search(cleaned):
                    out.append((cleaned, event_type, report_dt))
                    break
    return out


async def _geocode_with_backoff(query: str, stats: dict) -> tuple[float, float] | None:
    for attempt in range(3):
        coords = await _nominatim_geocode(query, _max_attempts=1)
        stats["geocoded"] += 1
        if coords:
            return coords
        await asyncio.sleep(NOMINATIM_PAUSE * (attempt + 1))
    return None


async def _cached_geocode(session, address: str, now: datetime, stats: dict) -> tuple[float, float] | None:
    row = (
        await session.execute(
            select(GeocodeCache).where(GeocodeCache.address == address[:256])
        )
    ).scalar_one_or_none()
    if row:
        cached_ts = row.created_at or row.last_try
        if row.lat is not None and (now - cached_ts) < CACHE_TTL:
            stats["cache_hits"] += 1
            return row.lat, row.lng
        if row.lat is None and (now - cached_ts) < NEGATIVE_CACHE_TTL:
            return None
    if stats["geocoded"] >= MAX_GEOCODES_PER_CYCLE:
        return None
    coords = None
    for query in _formulations(address):
        coords = await _geocode_with_backoff(query, stats)
        if stats["geocoded"] >= MAX_GEOCODES_PER_CYCLE:
            break
        if coords:
            break
    if row:
        row.lat = coords[0] if coords else None
        row.lng = coords[1] if coords else None
        row.last_try = now
    else:
        session.add(
            GeocodeCache(
                address=address[:256],
                lat=coords[0] if coords else None,
                lng=coords[1] if coords else None,
                last_try=now,
            )
        )
    return coords


async def _run_cycle(username: str) -> None:
    messages = await _fetch_channel_messages(username)
    if not messages:
        logger.info("[import:%s] no messages", username)
        return
    candidates = _candidate_lines(messages)
    logger.info("[import:%s] %d candidate lines", username, len(candidates))
    if not candidates:
        import_state.update(
            last_run=datetime.utcnow().isoformat(),
            last_candidates=0,
            last_geocoded=0,
            last_inserted=0,
            last_error=None,
        )
        return

    async with async_session() as session:
        purge = datetime.utcnow() - timedelta(days=14)
        await session.execute(delete(GeocodeCache).where(GeocodeCache.last_try < purge))
        admins = settings.ADMIN_IDS
        if not admins:
            logger.warning("[import] no ADMIN_IDS configured, skip")
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

        stats = {"geocoded": 0, "cache_hits": 0, "inserted": 0, "skipped": 0}
        geo_before = geo_stats_snapshot()
        tolerance = timedelta(minutes=TIME_TOLERANCE_MINUTES)
        for cleaned, event_type, report_dt in candidates:
            if report_dt:
                start_at = report_dt - tolerance
                if report_dt + tolerance <= now:
                    stats["skipped"] += 1
                    continue
            else:
                start_at = now
            visible_until = start_at + timedelta(hours=MAP_EVENT_TTL_HOURS)
            for address in _address_candidates(cleaned):
                coords = await _cached_geocode(session, address, now, stats)
                if not coords:
                    continue
                lat, lng = coords
                near = (
                    await session.execute(
                        select(MapEvent)
                        .where(
                            MapEvent.user_id == system_user_id,
                            MapEvent.event_type == event_type,
                            MapEvent.lat.between(lat - 0.006, lat + 0.006),
                            MapEvent.lng.between(lng - 0.006, lng + 0.006),
                        )
                        .order_by(MapEvent.created_at.desc())
                    )
                ).scalars().all()
                old = next(
                    (
                        e
                        for e in near
                        if haversine(lat, lng, e.lat, e.lng) <= DEDUP_DISTANCE_KM
                        and e.expires_at
                        and e.expires_at > now
                    ),
                    None,
                )
                if old:
                    old.created_at = start_at
                    old.expires_at = visible_until
                    old.description = cleaned[:500]
                    stats["skipped"] += 1
                    break
                session.add(
                    MapEvent(
                        user_id=system_user_id,
                        lat=lat,
                        lng=lng,
                        event_type=event_type,
                        description=cleaned[:500],
                        created_at=start_at,
                        expires_at=visible_until,
                    )
                )
                stats["inserted"] += 1
                await session.flush()
                break
        await session.commit()
        logger.info(
            "[import:%s] inserted %d, skipped %d",
            username,
            stats["inserted"],
            stats["skipped"],
        )
        import_state.update(
            last_run=datetime.utcnow().isoformat(),
            last_candidates=len(candidates),
            last_geocoded=stats["geocoded"],
            last_inserted=stats["inserted"],
            last_extended=stats["skipped"],
            last_error=None,
        )
        delta = _geo_stats_delta(geo_before)
        import_state["geo_detail"] = f"ok:{delta['ok']}|429:{delta['rate_limited']}|http:{delta['http_other']}|exc:{delta['exc']}"


async def _import_loop() -> None:
    sources = settings.CHANNEL_IMPORT_SOURCES
    while True:
        for username in sources:
            try:
                await _run_cycle(username)
            except Exception as e:
                logger.warning("[import:%s] cycle failed: %s", username, e)
                import_state.update(last_run=datetime.utcnow().isoformat(), last_error=str(e)[:200])
        await asyncio.sleep(FETCH_INTERVAL_SECONDS)


def start_channel_events_import() -> None:
    sources = settings.CHANNEL_IMPORT_SOURCES
    if not sources:
        logger.info("[import] disabled: CHANNEL_IMPORT_SOURCES_RAW not set")
        return
    import_state.update(enabled=True, sources=sources)
    logger.info("[import] watching channels: %s", ", ".join(sources))
    asyncio.create_task(_import_loop())