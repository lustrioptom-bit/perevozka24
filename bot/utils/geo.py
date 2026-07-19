import math
import asyncio

EARTH_RADIUS_KM = 6371.0

CITY_COORDS = {
    "харків": (49.9935, 36.2304), "харьков": (49.9935, 36.2304), "kharkiv": (49.9935, 36.2304),
    "київ": (50.4501, 30.5234), "киев": (50.4501, 30.5234), "kyiv": (50.4501, 30.5234),
    "одеса": (46.4825, 30.7233), "одесса": (46.4825, 30.7233), "odesa": (46.4825, 30.7233),
    "дніпро": (48.4647, 35.0462), "днепр": (48.4647, 35.0462), "dnipro": (48.4647, 35.0462),
    "запоріжжя": (47.8388, 35.1396), "запорожье": (47.8388, 35.1396),
    "львів": (49.8397, 24.0297), "львов": (49.8397, 24.0297), "lviv": (49.8397, 24.0297),
    "вінниця": (49.2328, 28.4816), "винница": (49.2328, 28.4816),
    "полтава": (49.5883, 34.5514),
    "чернівці": (48.2920, 25.9358), "черновцы": (48.2920, 25.9358),
    "суми": (50.9077, 34.7981),
    "житомир": (50.2547, 28.6587),
    "хмельницький": (49.4230, 26.9871), "хмельницкий": (49.4230, 26.9871),
    "рівне": (50.6199, 26.2516), "ровно": (50.6199, 26.2516),
    "кропивницький": (48.5079, 32.2623), "кировоград": (48.5079, 32.2623),
    "тернопіль": (49.5535, 25.5948), "тернополь": (49.5535, 25.5948),
    "івано-франківськ": (48.9226, 24.7111), "ивано-франковск": (48.9226, 24.7111),
    "луцьк": (50.7472, 25.3254), "луцк": (50.7472, 25.3254),
    "ужгород": (48.6208, 22.2879),
    "миколаїв": (46.9750, 31.9946), "николаев": (46.9750, 31.9946),
    "черкаси": (49.4444, 32.0598), "черкассы": (49.4444, 32.0598),
    "чернігів": (51.4982, 31.2893), "чернигов": (51.4982, 31.2893),
    "херсон": (46.6354, 32.6169),
    "кам'янець-подільський": (48.6845, 26.5804), "каменец-подольский": (48.6845, 26.5804),
    "мариуполь": (47.0958, 37.5559), "маріуполь": (47.0958, 37.5559),
}


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _lookup_city(address: str) -> tuple[float, float] | None:
    normalized = address.strip().lower()
    if normalized in CITY_COORDS:
        return CITY_COORDS[normalized]
    for city, coords in CITY_COORDS.items():
        if city in normalized:
            return coords
    return None


async def _nominatim_geocode(address: str) -> tuple[float, float] | None:
    import httpx

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": address, "format": "json", "limit": 1, "countrycodes": "ua"},
                    headers={"User-Agent": "Perevozka24/1.0 (logistics-app)"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        return float(data[0]["lat"]), float(data[0]["lon"])
                    return None
                if resp.status_code == 429:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                return None
        except Exception:
            await asyncio.sleep(1)
    return None


async def geocode_address(address: str) -> tuple[float, float] | None:
    result = await _nominatim_geocode(address)
    if result:
        return result

    return _lookup_city(address)


async def get_road_route(from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> dict | None:
    import httpx
    import logging

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"http://router.project-osrm.org/route/v1/driving/{from_lng},{from_lat};{to_lng},{to_lat}"
            resp = await client.get(
                url,
                params={"overview": "full", "geometries": "geojson"},
            )
            logging.getLogger(__name__).info("OSRM %s -> %s", url, resp.status_code)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    distance_km = round(route["distance"] / 1000, 1)
                    coords = route["geometry"]["coordinates"]
                    if len(coords) > 200:
                        step = len(coords) / 200
                        coords = [coords[0]] + [coords[int(i * step)] for i in range(1, 199)] + [coords[-1]]
                    geometry = ";".join(f"{c[1]},{c[0]}" for c in coords)
                    logging.getLogger(__name__).info("OSRM distance: %s km, geometry points: %d", distance_km, len(coords))
                    return {"distance_km": distance_km, "geometry": geometry}
                else:
                    logging.getLogger(__name__).error("OSRM bad response: %s", data.get("code"))
    except Exception as e:
        logging.getLogger(__name__).error("OSRM failed: %s", e, exc_info=True)
    return None
