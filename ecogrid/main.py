"""Demo: run one trading cycle from meter data to settlement."""

import os
from decimal import Decimal

from ecogrid.marketplace import Marketplace
from ecogrid.meter import MeterIngestionService
from ecogrid.models import Household
from ecogrid.settlement import SettlementService

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "sample_readings.csv")

# Asking price per kWh for each seller in the demo; others use the default.
SELLER_PRICES = {"H1": Decimal("0.18")}
DEFAULT_PRICE = Decimal("0.22")


def run_demo() -> None:
    households = {
        "H1": Household("H1", "Smith (solar)", has_solar=True),
        "H2": Household("H2", "Nguyen (solar)", has_solar=True),
        "H3": Household("H3", "Patel", wallet_balance=Decimal("20.00")),
        "H4": Household("H4", "Brown", wallet_balance=Decimal("1.00")),
    }

    meters = MeterIngestionService()
    accepted = meters.ingest_csv(DATA_FILE)
    print(f"Accepted {accepted} readings, rejected {len(meters.rejected)}")

    market = Marketplace()
    surplus = meters.surplus_by_household()
    for household_id, kwh in surplus.items():
        if kwh > 0:
            price = SELLER_PRICES.get(household_id, DEFAULT_PRICE)
            market.list_offer(household_id, kwh, price, available_surplus=kwh)
            print(f"{household_id} offers {kwh} kWh at ${price}/kWh")

    market.place_order("H3", Decimal("6"), Decimal("0.25"))
    market.place_order("H4", Decimal("8"), Decimal("0.25"))

    settlement = SettlementService(households, on_failed=market.release_trade)
    for txn in settlement.settle_all(market.trades):
        print(f"{txn.payer_id} -> {txn.payee_id}: ${txn.gross_amount} ({txn.status.value})")

    for offer in market.open_offers():
        print(f"{offer.seller_id} still offers {offer.remaining_kwh} kWh")

    print(f"Platform revenue: ${settlement.platform_revenue}")
    for h in households.values():
        print(f"{h.name}: ${h.wallet_balance}")


if __name__ == "__main__":  # pragma: no cover
    run_demo()
