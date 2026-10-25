from decimal import Decimal

import pytest

from ecogrid.marketplace import Marketplace, MarketplaceError
from ecogrid.models import OrderStatus, Trade

D = Decimal


@pytest.fixture
def market():
    return Marketplace()


def test_order_matches_cheapest_offer_first(market):
    market.list_offer("S1", D("5"), D("0.30"))
    cheap = market.list_offer("S2", D("5"), D("0.20"))
    order = market.place_order("B1", D("3"), D("0.40"))

    assert len(market.trades) == 1
    assert market.trades[0].offer_id == cheap.offer_id
    assert order.status == OrderStatus.FILLED
    assert cheap.status == OrderStatus.PARTIALLY_FILLED


def test_order_fills_across_multiple_offers(market):
    market.list_offer("S1", D("2"), D("0.20"))
    market.list_offer("S2", D("2"), D("0.25"))
    order = market.place_order("B1", D("3"), D("0.30"))

    assert len(market.trades) == 2
    assert order.remaining_kwh == D("0")


def test_order_not_matched_above_max_price(market):
    market.list_offer("S1", D("5"), D("0.50"))
    order = market.place_order("B1", D("5"), D("0.30"))
    assert market.trades == []
    assert order.status == OrderStatus.OPEN


def test_partial_fill_when_supply_short(market):
    market.list_offer("S1", D("2"), D("0.20"))
    order = market.place_order("B1", D("5"), D("0.30"))
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.remaining_kwh == D("3")


def test_cannot_trade_with_self(market):
    market.list_offer("H1", D("5"), D("0.20"))
    market.place_order("H1", D("5"), D("0.30"))
    assert market.trades == []


def test_invalid_price_rejected(market):
    quantity, too_high_price = D("5"), D("5.00")
    with pytest.raises(MarketplaceError):
        market.list_offer("S1", quantity, too_high_price)


def test_zero_quantity_rejected(market):
    zero_quantity, price = D("0"), D("0.20")
    with pytest.raises(MarketplaceError):
        market.place_order("B1", zero_quantity, price)


def test_cannot_offer_more_than_surplus(market):
    quantity, price, surplus = D("10"), D("0.20"), D("4")
    with pytest.raises(MarketplaceError):
        market.list_offer("S1", quantity, price, available_surplus=surplus)


def test_cancel_offer(market):
    offer = market.list_offer("S1", D("5"), D("0.20"))
    market.cancel_offer(offer.offer_id)
    assert offer.status == OrderStatus.CANCELLED
    assert market.open_offers() == []
    with pytest.raises(MarketplaceError):
        market.cancel_offer(offer.offer_id)
    with pytest.raises(MarketplaceError):
        market.cancel_offer("missing")


def test_release_trade_restores_offer_and_order(market):
    offer = market.list_offer("S1", D("5"), D("0.20"))
    order = market.place_order("B1", D("3"), D("0.30"))
    market.release_trade(market.trades[0])
    assert offer.remaining_kwh == D("5")
    assert offer.status == OrderStatus.OPEN
    assert order.remaining_kwh == D("3")
    assert order.status == OrderStatus.OPEN


def test_release_one_of_two_trades_leaves_offer_partially_filled(market):
    offer = market.list_offer("S1", D("5"), D("0.20"))
    market.place_order("B1", D("3"), D("0.30"))
    market.place_order("B2", D("1"), D("0.30"))
    market.release_trade(market.trades[0])
    assert offer.remaining_kwh == D("4")
    assert offer.status == OrderStatus.PARTIALLY_FILLED


def test_release_trade_only_once(market):
    market.list_offer("S1", D("5"), D("0.20"))
    market.place_order("B1", D("3"), D("0.30"))
    trade = market.trades[0]
    market.release_trade(trade)
    with pytest.raises(MarketplaceError):
        market.release_trade(trade)


def test_release_unknown_trade_raises(market):
    stray = Trade(seller_id="S1", buyer_id="B1", quantity_kwh=D("1"),
                  price_per_kwh=D("0.20"), offer_id="missing", order_id="missing")
    with pytest.raises(MarketplaceError):
        market.release_trade(stray)


def test_release_keeps_cancelled_offer_cancelled(market):
    offer = market.list_offer("S1", D("5"), D("0.20"))
    market.place_order("B1", D("3"), D("0.30"))
    market.cancel_offer(offer.offer_id)
    market.release_trade(market.trades[0])
    assert offer.remaining_kwh == D("5")
    assert offer.status == OrderStatus.CANCELLED
