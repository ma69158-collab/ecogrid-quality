"""Financial Settlement context: pay sellers for matched trades."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List

from ecogrid.models import Household, Trade, Transaction, TransactionStatus

PLATFORM_FEE_RATE = Decimal("0.02")  # 2% fee kept by EcoGrid
CENT = Decimal("0.01")


class SettlementError(Exception):
    """Raised when a settlement cannot be processed."""


class SettlementService:
    """Moves money between household wallets and keeps a ledger."""

    def __init__(self, households: Dict[str, Household], fee_rate: Decimal = PLATFORM_FEE_RATE) -> None:
        if fee_rate < 0 or fee_rate >= 1:
            raise SettlementError("Fee rate must be between 0 and 1")
        self.households = households
        self.fee_rate = fee_rate
        self.ledger: List[Transaction] = []
        self.platform_revenue = Decimal("0.00")
        self._settled_trades: set = set()

    def calculate_fee(self, amount: Decimal) -> Decimal:
        return (amount * self.fee_rate).quantize(CENT, rounding=ROUND_HALF_UP)

    def settle(self, trade: Trade) -> Transaction:
        """Settle one trade. Each trade can only be settled once."""
        if trade.trade_id in self._settled_trades:
            raise SettlementError(f"Trade {trade.trade_id} already settled")

        buyer = self.households.get(trade.buyer_id)
        seller = self.households.get(trade.seller_id)
        if buyer is None or seller is None:
            raise SettlementError("Unknown buyer or seller")

        gross = trade.total_value
        fee = self.calculate_fee(gross)
        txn = Transaction(
            trade_id=trade.trade_id,
            payer_id=buyer.household_id,
            payee_id=seller.household_id,
            gross_amount=gross,
            platform_fee=fee,
            net_amount=gross - fee,
        )

        if buyer.wallet_balance < gross:
            txn.status = TransactionStatus.FAILED
            txn.failure_reason = "Insufficient funds"
        else:
            buyer.wallet_balance -= gross
            seller.wallet_balance += txn.net_amount
            self.platform_revenue += fee
            txn.status = TransactionStatus.SETTLED
            self._settled_trades.add(trade.trade_id)

        self.ledger.append(txn)
        return txn

    def settle_all(self, trades: List[Trade]) -> List[Transaction]:
        return [self.settle(t) for t in trades if t.trade_id not in self._settled_trades]

    def statement(self, household_id: str) -> List[Transaction]:
        """All transactions involving a household."""
        return [t for t in self.ledger if household_id in (t.payer_id, t.payee_id)]
