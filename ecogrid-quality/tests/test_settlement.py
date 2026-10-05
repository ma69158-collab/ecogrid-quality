from decimal import Decimal

import pytest

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
    with pytest.raises(SettlementError):
        service.settle(trade)
    assert service.settle_all([trade]) == []


def test_unknown_household(households):
    service = SettlementService(households)
    trade = make_trade()
    trade.buyer_id = "nobody"
    with pytest.raises(SettlementError):
        service.settle(trade)


def test_invalid_fee_rate(households):
    with pytest.raises(SettlementError):
        SettlementService(households, fee_rate=D("1.5"))


def test_statement(households):
    service = SettlementService(households)
    service.settle(make_trade())
    assert len(service.statement("S1")) == 1
    assert service.statement("other") == []
