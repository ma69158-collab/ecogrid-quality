from decimal import Decimal

import pytest

from ecogrid.marketplace import Marketplace
from ecogrid.models import Household, Trade, TransactionStatus
from ecogrid.settlement import SettlementError, SettlementService

D = Decimal


@pytest.fixture
def households():
    return {
        "S1": Household("S1", "Seller", has_solar=True),
        "B1": Household("B1", "Buyer", wallet_balance=D("10.00")),
    }


def make_trade(quantity="5", price="0.20"):
    return Trade(seller_id="S1", buyer_id="B1", quantity_kwh=D(quantity),
                 price_per_kwh=D(price), offer_id="o1", order_id="b1")


def test_successful_settlement_moves_money(households):
    service = SettlementService(households)
    txn = service.settle(make_trade())

    assert txn.status == TransactionStatus.SETTLED
    assert txn.gross_amount == D("1.00")
    assert txn.platform_fee == D("0.02")
    assert households["B1"].wallet_balance == D("9.00")
    assert households["S1"].wallet_balance == D("0.98")
    assert service.platform_revenue == D("0.02")


def test_insufficient_funds_fails(households):
    households["B1"].wallet_balance = D("0.50")
    service = SettlementService(households)
    txn = service.settle(make_trade())
    assert txn.status == TransactionStatus.FAILED
    assert households["S1"].wallet_balance == D("0")


def test_trade_cannot_be_settled_twice(households):
    service = SettlementService(households)
    trade = make_trade()
    service.settle(trade)
    with pytest.raises(SettlementError, match="already processed"):
        service.settle(trade)
    assert service.settle_all([trade]) == []


def test_unknown_household(households):
    service = SettlementService(households)
    trade = make_trade()
    trade.buyer_id = "nobody"
    with pytest.raises(SettlementError, match="Unknown buyer or seller"):
        service.settle(trade)


def test_invalid_fee_rate(households):
    bad_rate = D("1.5")
    with pytest.raises(SettlementError, match="Fee rate must be between 0 and 1"):
        SettlementService(households, fee_rate=bad_rate)


def test_statement(households):
    service = SettlementService(households)
    service.settle(make_trade())
    assert len(service.statement("S1")) == 1
    assert service.statement("other") == []


def test_failed_trade_not_duplicated_on_rerun(households):
    households["B1"].wallet_balance = D("0.50")
    service = SettlementService(households)
    trade = make_trade()
    service.settle_all([trade])
    assert service.settle_all([trade]) == []
    assert len(service.ledger) == 1


def test_failed_trade_is_final(households):
    households["B1"].wallet_balance = D("0.50")
    service = SettlementService(households)
    trade = make_trade()
    assert service.settle(trade).status == TransactionStatus.FAILED
    households["B1"].wallet_balance = D("10.00")
    with pytest.raises(SettlementError, match="already processed"):
        service.settle(trade)


def test_on_failed_called_only_for_failed_payments(households):
    failed = []
    service = SettlementService(households, on_failed=failed.append)
    paid = make_trade(quantity="1")
    service.settle(paid)
    households["B1"].wallet_balance = D("0.10")
    unpaid = make_trade(quantity="5")
    service.settle(unpaid)
    assert failed == [unpaid]


def test_d02_failed_payment_returns_energy_to_offer():
    """Regression test for D-02: energy from a failed payment goes back on sale."""
    homes = {"S1": Household("S1", "Seller", has_solar=True),
             "B1": Household("B1", "Buyer", wallet_balance=D("0.10"))}
    market = Marketplace()
    offer = market.list_offer("S1", D("5"), D("0.20"))
    order = market.place_order("B1", D("3"), D("0.30"))
    service = SettlementService(homes, on_failed=market.release_trade)
    txns = service.settle_all(market.trades)
    assert txns[0].status == TransactionStatus.FAILED
    assert offer.remaining_kwh == D("5")
    assert order.remaining_kwh == D("3")
    assert service.settle_all(market.trades) == []
    assert offer.remaining_kwh == D("5")
