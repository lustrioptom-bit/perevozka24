import asyncio
import html
import logging
import re
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

from config import settings
from bot.utils.geo import _nominatim_geocode, haversine
from db.engine import async_session
from db.models import MapEvent, User, UserRole
from webapp.routers.api import MAP_EVENT_TTL_HOURS

logger = logging.getLogger(__name__)

import_state = {"enabled": False, "sources": [], "last_run": None, "last_inserted": 0, "last_error": None}

FETCH_INTERVAL_SECONDS = 300
MAX_GEOCODES_PER_CYCLE = 24
DEDUP_DISTANCE_KM = 0.4
NOMINATIM_PAUSE = 1.2

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

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}\s*")
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


def _clean_line(line: str) -> str:
    line = _TIME_RE.sub("", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip(" –—·•*").strip()


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


def _candidate_lines(messages: list[str]) -> list[tuple[str, str]]:
    out = []
    for text in messages:
        for line in text.splitlines():
            cleaned = _clean_line(line)
            if len(cleaned) < 8:
                continue
            low = cleaned.lower()
            if any(word in low for word in MILITARY_BLACKLIST):
                continue
            for pattern, event_type in TRAFFIC_PATTERNS:
                if pattern.search(cleaned):
                    out.append((cleaned, event_type))
                    break
    return out


async def _run_cycle(username: str) -> None:
    messages = await _fetch_channel_messages(username)
    if not messages:
        logger.info("[import:%s] no messages", username)
        return
    candidates = _candidate_lines(messages)
    logger.info("[import:%s] %d candidate lines", username, len(candidates))
    if not candidates:
        import_state.update(last_run=datetime.utcnow().isoformat(), last_inserted=0, last_error=None)
        return

    async with async_session() as session:
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
        existing = list(
            (await session.execute(select(MapEvent).where(MapEvent.expires_at > now))).scalars().all()
        )

        geocoded = 0
        inserted = 0
        geo_cache: dict[str, tuple[float, float] | None] = {}
        for cleaned, event_type in candidates:
            placed = False
            for address in _address_candidates(cleaned):
                if address not in geo_cache:
                    if geocoded >= MAX_GEOCODES_PER_CYCLE:
                        break
                    result = None
                    for query in _formulations(address):
                        if geocoded:
                            await asyncio.sleep(NOMINATIM_PAUSE)
                        coords = await _nominatim_geocode(query)
                        geocoded += 1
                        if coords:
                            result = coords
                            break
                    geo_cache[address] = result
                coords = geo_cache[address]
                if placed or not coords:
                    continue
                lat, lng = coords
                duplicate = any(
                    e.event_type == event_type
                    and e.user_id == system_user_id
                    and haversine(lat, lng, e.lat, e.lng) <= DEDUP_DISTANCE_KM
                    for e in existing
                )
                if duplicate:
                    break
                session.add(
                    MapEvent(
                        user_id=system_user_id,
                        lat=lat,
                        lng=lng,
                        event_type=event_type,
                        description=cleaned[:500],
                        expires_at=now + timedelta(hours=MAP_EVENT_TTL_HOURS),
                    )
                )
                inserted += 1
                placed = True
                break
            if placed:
                continue
        await session.commit()
        logger.info("[import:%s] geocoded %d, inserted %d", username, geocoded, inserted)
        import_state.update(
            last_run=datetime.utcnow().isoformat(), last_inserted=inserted, last_error=None
        )


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