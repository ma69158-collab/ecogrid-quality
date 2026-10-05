from decimal import Decimal

import pytest

from ecogrid.meter import InvalidReadingError, MeterIngestionService, parse_reading


def row(**overrides):
    base = {
        "meter_id": "M1",
        "household_id": "H1",
        "timestamp": "2026-10-01T10:00:00",
        "generated_kwh": "4.0",
        "consumed_kwh": "1.5",
    }
    base.update(overrides)
    return base


def test_parse_valid_reading_and_surplus():
    reading = parse_reading(row())
    assert reading.surplus_kwh == Decimal("2.5")


def test_surplus_never_negative():
    reading = parse_reading(row(generated_kwh="0", consumed_kwh="3"))
    assert reading.surplus_kwh == Decimal("0")


@pytest.mark.parametrize(
    "bad_row",
    [
        row(meter_id=""),
        row(timestamp="yesterday"),
        row(generated_kwh="abc"),
        row(consumed_kwh="-1"),
        row(generated_kwh="999"),
    ],
)
def test_invalid_readings_raise(bad_row):
    with pytest.raises(InvalidReadingError):
        parse_reading(bad_row)


def test_ingest_rejects_duplicates_and_invalid_rows():
    service = MeterIngestionService()
    accepted = service.ingest([row(), row(), row(timestamp="bad")])
    assert accepted == 1
    assert len(service.rejected) == 2


def test_surplus_and_consumption_totals():
    service = MeterIngestionService()
    service.ingest([
        row(),
        row(timestamp="2026-10-01T11:00:00", generated_kwh="3", consumed_kwh="1"),
        row(meter_id="M2", household_id="H2", generated_kwh="0", consumed_kwh="2"),
    ])
    assert service.surplus_by_household() == {"H1": Decimal("4.5"), "H2": Decimal("0")}
    assert service.consumption_by_household()["H2"] == Decimal("2")


def test_ingest_csv(tmp_path):
    csv_file = tmp_path / "readings.csv"
    csv_file.write_text(
        "meter_id,household_id,timestamp,generated_kwh,consumed_kwh\n"
        "M1,H1,2026-10-01T10:00:00,4,1\n",
        encoding="utf-8",
    )
    service = MeterIngestionService()
    assert service.ingest_csv(str(csv_file)) == 1
