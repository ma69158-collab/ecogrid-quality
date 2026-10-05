"""Smart Meter Integration context: ingest and validate IoT meter readings."""

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Iterable, List, Tuple

from ecogrid.models import MeterReading

REQUIRED_COLUMNS = ("meter_id", "household_id", "timestamp", "generated_kwh", "consumed_kwh")
MAX_READING_KWH = Decimal("50")  # sanity limit for a single interval


class InvalidReadingError(ValueError):
    """Raised when a meter reading fails validation."""


def parse_reading(row: Dict[str, str]) -> MeterReading:
    """Convert one CSV row into a validated MeterReading."""
    missing = [col for col in REQUIRED_COLUMNS if not row.get(col)]
    if missing:
        raise InvalidReadingError(f"Missing fields: {', '.join(missing)}")

    try:
        timestamp = datetime.fromisoformat(row["timestamp"])
    except ValueError as exc:
        raise InvalidReadingError(f"Bad timestamp: {row['timestamp']}") from exc

    try:
        generated = Decimal(row["generated_kwh"])
        consumed = Decimal(row["consumed_kwh"])
    except InvalidOperation as exc:
        raise InvalidReadingError("kWh values must be numeric") from exc

    if generated < 0 or consumed < 0:
        raise InvalidReadingError("kWh values cannot be negative")
    if generated > MAX_READING_KWH or consumed > MAX_READING_KWH:
        raise InvalidReadingError("kWh value exceeds sanity limit")

    return MeterReading(
        meter_id=row["meter_id"],
        household_id=row["household_id"],
        timestamp=timestamp,
        generated_kwh=generated,
        consumed_kwh=consumed,
    )


class MeterIngestionService:
    """Collects readings and reports surplus energy per household."""

    def __init__(self) -> None:
        self.readings: List[MeterReading] = []
        self.rejected: List[Tuple[Dict[str, str], str]] = []
        self._seen: set = set()

    def ingest(self, rows: Iterable[Dict[str, str]]) -> int:
        """Ingest rows, skipping invalid or duplicate readings.

        Returns the number of readings accepted.
        """
        accepted = 0
        for row in rows:
            try:
                reading = parse_reading(row)
            except InvalidReadingError as err:
                self.rejected.append((row, str(err)))
                continue
            key = (reading.meter_id, reading.timestamp)
            if key in self._seen:
                self.rejected.append((row, "Duplicate reading"))
                continue
            self._seen.add(key)
            self.readings.append(reading)
            accepted += 1
        return accepted

    def ingest_csv(self, path: str) -> int:
        """Ingest readings from a CSV file."""
        with open(path, newline="", encoding="utf-8") as handle:
            return self.ingest(csv.DictReader(handle))

    def surplus_by_household(self) -> Dict[str, Decimal]:
        """Total surplus kWh available to sell, per household."""
        totals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for reading in self.readings:
            totals[reading.household_id] += reading.surplus_kwh
        return dict(totals)

    def consumption_by_household(self) -> Dict[str, Decimal]:
        """Total consumed kWh per household."""
        totals: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for reading in self.readings:
            totals[reading.household_id] += reading.consumed_kwh
        return dict(totals)
