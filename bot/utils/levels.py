from __future__ import annotations

LEVELS = [
    (0, "novice", "Новичок", "🟢", "Базовый доступ"),
    (11, "verified", "Проверенный", "🔵", "Приоритет в выдаче"),
    (31, "pro", "Профессионал", "🟣", "Сниженная комиссия (3%)"),
    (51, "expert", "Эксперт", "🟡", "0% комиссия навсегда"),
]


def get_level_info(deals: int) -> tuple[dict | None, dict | None]:
    current = LEVELS[0]
    current_idx = 0
    for i, lv in enumerate(LEVELS):
        if deals >= lv[0]:
            current = lv
            current_idx = i
        else:
            break
    next_lv = LEVELS[current_idx + 1] if current_idx + 1 < len(LEVELS) else None
    cur = {
        "key": current[1], "name": current[2], "icon": current[3],
        "bonus": current[4], "threshold": current[0],
    }
    nxt = None
    if next_lv:
        nxt = {
            "key": next_lv[1], "name": next_lv[2], "icon": next_lv[3],
            "bonus": next_lv[4], "threshold": next_lv[0],
        }
    return cur, nxt


def level_progress(deals: int) -> str:
    cur, nxt = get_level_info(deals)
    if nxt is None:
        return f"{deals}/{deals} (максимальный уровень)"
    span = nxt["threshold"] - cur["threshold"]
    done = max(0, min(deals - cur["threshold"], span))
    filled = int(done / span * 10)
    return f"[{'█' * filled}{'░' * (10 - filled)}] {deals}/{nxt['threshold']}"