import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
TABLES = ("walkers", "dogs", "walks")
INTEGER_FIELDS = {
    "walkers": ("id", "hourly_rate_cents", "max_dogs"),
    "dogs": ("id",),
    "walks": ("id", "walker_id", "dog_id", "duration_minutes", "price_cents"),
}
BOOLEAN_FIELDS = {
    "walkers": ("active",),
}


def _parse_row(table, row):
    parsed = dict(row)
    for field in INTEGER_FIELDS.get(table, ()):
        parsed[field] = int(parsed[field])
    for field in BOOLEAN_FIELDS.get(table, ()):
        parsed[field] = parsed[field].strip().lower() == "true"
    return parsed


class CsvStore:
    def __init__(self, data_dir=DATA_DIR):
        self._tables = {}
        for table in TABLES:
            with open(Path(data_dir) / f"{table}.csv", newline="") as handle:
                rows = [_parse_row(table, row) for row in csv.DictReader(handle)]
            self._tables[table] = {row["id"]: row for row in rows}

    def all(self, table):
        return list(self._tables[table].values())

    def get(self, table, record_id):
        record = self._tables[table].get(record_id)
        return dict(record) if record else None

    def insert(self, table, record):
        new_id = max(self._tables[table], default=0) + 1
        stored = {**record, "id": new_id}
        self._tables[table][new_id] = stored
        return dict(stored)

    def update(self, table, record_id, changes):
        record = self._tables[table].get(record_id)
        if record is None:
            return None
        record.update(changes)
        return dict(record)
