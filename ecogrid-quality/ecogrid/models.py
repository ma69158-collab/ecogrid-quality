"""Core domain models shared across the EcoGrid bounded contexts."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid


def new_id() -> str:
    """Return a short unique identifier."""
    return uuid.uuid4().hex[:12]


class OrderStatus(Enum):
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"


class TransactionStatus(Enum):
    PENDING = "pending"
    SETTLED = "settled"
    FAILED = "failed"


@dataclass
class Household:
    """A residential participant who may buy and/or sell energy."""

    household_id: str
    name: str
    has_solar: bool = False
    wallet_balance: Decimal = Decimal("0.00")


@dataclass
class MeterReading:
    """One reading from a smart meter for a time interval."""

    meter_id: str
    household_id: str
    timestamp: datetime
    generated_kwh: Decimal
    consumed_kwh: Decimal

    @property
    def surplus_kwh(self) -> Decimal:
        """Energy available to sell (never negative)."""
        surplus = self.generated_kwh - self.consumed_kwh
        return surplus if surplus > 0 else Decimal("0")


@dataclass
class SellOffer:
    """A seller's offer of surplus energy at a minimum price per kWh."""

    seller_id: str
    quantity_kwh: Decimal
    price_per_kwh: Decimal
    offer_id: str = field(default_factory=new_id)
    remaining_kwh: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.OPEN
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if self.remaining_kwh is None:
            self.remaining_kwh = self.quantity_kwh


@dataclass
class BuyOrder:
    """A buyer's request for energy up to a maximum price per kWh."""

    buyer_id: str
    quantity_kwh: Decimal
    max_price_per_kwh: Decimal
    order_id: str = field(default_factory=new_id)
    remaining_kwh: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.OPEN
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if self.remaining_kwh is None:
            self.remaining_kwh = self.quantity_kwh


@dataclass
class Trade:
    """A matched trade between one seller and one buyer."""

    seller_id: str
    buyer_id: str
    quantity_kwh: Decimal
    price_per_kwh: Decimal
    offer_id: str
    order_id: str
    trade_id: str = field(default_factory=new_id)
    executed_at: datetime = field(default_factory=datetime.now)

    @property
    def total_value(self) -> Decimal:
        return (self.quantity_kwh * self.price_per_kwh).quantize(Decimal("0.01"))


@dataclass
class Transaction:
    """A financial settlement record for a trade."""

    trade_id: str
    payer_id: str
    payee_id: str
    gross_amount: Decimal
    platform_fee: Decimal
    net_amount: Decimal
    transaction_id: str = field(default_factory=new_id)
    status: TransactionStatus = TransactionStatus.PENDING
    failure_reason: Optional[str] = None
