from datetime import datetime, timedelta

from services.errors import ConflictError, NotFoundError, ValidationError

ALLOWED_DURATIONS = (30, 60)
LARGE_DOG_SURCHARGE_CENTS = 500
REQUIRED_FIELDS = ("walker_id", "dog_id", "start_time", "duration_minutes")


class WalkService:
    def __init__(self, store, clock):
        self.store = store
        self.clock = clock

    def list_walkers(self):
        return [walker for walker in self.store.all("walkers") if walker["active"]]

    def get_walker(self, walker_id):
        return self._require("walkers", walker_id)

    def list_walks(self, walker_id=None, status=None):
        walks = self.store.all("walks")
        if walker_id is not None:
            walks = [walk for walk in walks if walk["walker_id"] == walker_id]
        if status is not None:
            walks = [walk for walk in walks if walk["status"] == status]
        return walks

    def get_walk(self, walk_id):
        return self._require("walks", walk_id)

    def create_walk(self, payload):
        missing = [field for field in REQUIRED_FIELDS if field not in payload]
        if missing:
            raise ValidationError(f"missing fields: {', '.join(missing)}")

        walker = self._require("walkers", payload["walker_id"])
        dog = self._require("dogs", payload["dog_id"])
        if not walker["active"]:
            raise ConflictError("walker is not accepting walks")

        duration = payload["duration_minutes"]
        if duration not in ALLOWED_DURATIONS:
            raise ValidationError(f"duration_minutes must be one of {list(ALLOWED_DURATIONS)}")

        start = self._parse_time(payload["start_time"])
        if start <= self.clock():
            raise ValidationError("start_time must be in the future")

        end = start + timedelta(minutes=duration)
        overlapping = [
            walk
            for walk in self.list_walks(walker_id=walker["id"], status="scheduled")
            if self._overlaps(walk, start, end)
        ]
        if len(overlapping) >= walker["max_dogs"]:
            raise ConflictError("walker is fully booked for that time")
        if any(walk["dog_id"] == dog["id"] for walk in overlapping):
            raise ConflictError("dog already has a walk at that time")

        price = walker["hourly_rate_cents"] * duration // 60
        if dog["size"] == "large":
            price += LARGE_DOG_SURCHARGE_CENTS

        return self.store.insert("walks", {
            "walker_id": walker["id"],
            "dog_id": dog["id"],
            "start_time": start.isoformat(timespec="minutes"),
            "duration_minutes": duration,
            "status": "scheduled",
            "price_cents": price,
        })

    def cancel_walk(self, walk_id):
        walk = self._require("walks", walk_id)
        if walk["status"] != "scheduled":
            raise ConflictError(f"cannot cancel a walk that is {walk['status']}")
        return self.store.update("walks", walk_id, {"status": "cancelled"})

    def payout_statement(self, walker_id, date_from, date_to, page, page_size):
        walks = [
            walk
            for walk in self.store.all("walks")
            if walk["walker_id"] == walker_id
            and walk["status"] != "scheduled"
            and date_from <= datetime.fromisoformat(walk["start_time"]) < date_to
        ]
        offset = page * page_size
        page_walks = walks[offset:offset + page_size]
        return {
            "walker_id": walker_id,
            "from": date_from.date().isoformat(),
            "to": date_to.date().isoformat(),
            "total_walks": len(walks),
            "total_earnings_cents": sum(walk["price_cents"] for walk in page_walks),
            "page": page,
            "page_size": page_size,
            "total_pages": len(walks) // page_size,
            "walks": page_walks,
        }

    def _require(self, table, record_id):
        record = self.store.get(table, record_id)
        if record is None:
            raise NotFoundError(f"{table[:-1]} {record_id} not found")
        return record

    @staticmethod
    def _parse_time(value):
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValidationError("start_time must be an ISO 8601 datetime")

    @staticmethod
    def _overlaps(walk, start, end):
        walk_start = datetime.fromisoformat(walk["start_time"])
        walk_end = walk_start + timedelta(minutes=walk["duration_minutes"])
        return walk_start < end and start < walk_end
