ENUM_TYPES = [
    ("userrole", ["client", "driver", "both"]),
    ("vehicletype", ["car", "minivan", "truck_3_5t", "heavy_truck"]),
    ("ordertype", ["passenger", "freight"]),
    ("orderstatus", ["new", "active", "in_transit", "completed", "cancelled"]),
    ("bidstatus", ["pending", "accepted", "rejected"]),
]


def ensure_enum_statements() -> list[str]:
    stmts = []
    for name, values in ENUM_TYPES:
        joined = ", ".join(f"'{v}'" for v in values)
        stmts.append(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') "
            f"THEN CREATE TYPE {name} AS ENUM ({joined}); END IF; END $$;"
        )
    return stmts
