"""Marketplace context: match sellers of surplus energy with buyers."""

from decimal import Decimal
from typing import Dict, List, Optional

from ecogrid.models import BuyOrder, OrderStatus, SellOffer, Trade


class MarketplaceError(Exception):
    """Raised for invalid marketplace operations."""


class Marketplace:
    """A simple order book that matches buy orders to the cheapest offers."""

    def __init__(self, min_price: Decimal = Decimal("0.05"), max_price: Decimal = Decimal("1.00")) -> None:
        self.min_price = min_price
        self.max_price = max_price
        self.offers: Dict[str, SellOffer] = {}
        self.orders: Dict[str, BuyOrder] = {}
        self.trades: List[Trade] = []

    # ----- validation -------------------------------------------------
    def _check_price(self, price: Decimal) -> None:
        if price < self.min_price or price > self.max_price:
            raise MarketplaceError(
                f"Price {price} outside allowed range {self.min_price}-{self.max_price}"
            )

    @staticmethod
    def _check_quantity(quantity: Decimal) -> None:
        if quantity <= 0:
            raise MarketplaceError("Quantity must be positive")

    # ----- offers and orders -----------------------------------------
    def list_offer(self, seller_id: str, quantity_kwh: Decimal, price_per_kwh: Decimal,
                   available_surplus: Optional[Decimal] = None) -> SellOffer:
        """List surplus energy for sale.

        If ``available_surplus`` is given, the seller cannot list more than it.
        """
        self._check_quantity(quantity_kwh)
        self._check_price(price_per_kwh)
        if available_surplus is not None and quantity_kwh > available_surplus:
            raise MarketplaceError("Cannot offer more energy than measured surplus")
        offer = SellOffer(seller_id=seller_id, quantity_kwh=quantity_kwh, price_per_kwh=price_per_kwh)
        self.offers[offer.offer_id] = offer
        return offer

    def place_order(self, buyer_id: str, quantity_kwh: Decimal, max_price_per_kwh: Decimal) -> BuyOrder:
        """Place a buy order and immediately try to match it."""
        self._check_quantity(quantity_kwh)
        self._check_price(max_price_per_kwh)
        order = BuyOrder(buyer_id=buyer_id, quantity_kwh=quantity_kwh, max_price_per_kwh=max_price_per_kwh)
        self.orders[order.order_id] = order
        self.match(order)
        return order

    def cancel_offer(self, offer_id: str) -> None:
        offer = self.offers.get(offer_id)
        if offer is None:
            raise MarketplaceError(f"Unknown offer {offer_id}")
        if offer.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
            raise MarketplaceError("Offer can no longer be cancelled")
        offer.status = OrderStatus.CANCELLED

    def open_offers(self) -> List[SellOffer]:
        """Open offers sorted by cheapest price, then oldest first."""
        active = [
            o for o in self.offers.values()
            if o.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)
        ]
        return sorted(active, key=lambda o: (o.price_per_kwh, o.created_at))

    # ----- matching ---------------------------------------------------
    def match(self, order: BuyOrder) -> List[Trade]:
        """Fill a buy order from the cheapest eligible offers."""
        new_trades: List[Trade] = []
        for offer in self.open_offers():
            if order.remaining_kwh <= 0:
                break
            if offer.price_per_kwh > order.max_price_per_kwh:
                break  # offers are sorted, so no cheaper ones remain
            if offer.seller_id == order.buyer_id:
                continue  # households cannot trade with themselves

            quantity = min(order.remaining_kwh, offer.remaining_kwh)
            trade = Trade(
                seller_id=offer.seller_id,
                buyer_id=order.buyer_id,
                quantity_kwh=quantity,
                price_per_kwh=offer.price_per_kwh,
                offer_id=offer.offer_id,
                order_id=order.order_id,
            )
            offer.remaining_kwh -= quantity
            order.remaining_kwh -= quantity
            offer.status = OrderStatus.FILLED if offer.remaining_kwh == 0 else OrderStatus.PARTIALLY_FILLED
            new_trades.append(trade)

        if new_trades:
            order.status = OrderStatus.FILLED if order.remaining_kwh == 0 else OrderStatus.PARTIALLY_FILLED
        self.trades.extend(new_trades)
        return new_trades
