"""Factory for creating orders."""

from decimal import Decimal

from walltrack.models.order import (
    Order,
    OrderCreateRequest,
    OrderSide,
    OrderType,
)
from walltrack.models.position import Position


class OrderFactory:
    """Factory for creating Order instances."""

    def __init__(self, is_simulation_mode: bool = False):
        """
        Initialize OrderFactory.

        Args:
            is_simulation_mode: Whether to mark all orders as simulated
        """
        self.is_simulation_mode = is_simulation_mode

    def create_entry_order(
        self,
        signal_id: str,
        token_address: str,
        amount_sol: Decimal,
        expected_price: Decimal,
        token_symbol: str | None = None,
        max_slippage_bps: int = 100,
    ) -> Order:
        """
        Create an entry order from a signal.

        Args:
            signal_id: ID of the source signal
            token_address: Token contract address
            amount_sol: Amount in SOL to spend
            expected_price: Expected token price
            token_symbol: Optional token symbol
            max_slippage_bps: Max slippage in basis points

        Returns:
            New Order in PENDING status
        """
        return Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            signal_id=signal_id,
            token_address=token_address,
            token_symbol=token_symbol,
            amount_sol=amount_sol,
            expected_price=expected_price,
            max_slippage_bps=max_slippage_bps,
            is_simulated=self.is_simulation_mode,
        )

    def create_exit_order(
        self,
        position: Position,
        amount_tokens: Decimal,
        expected_price: Decimal,
        exit_reason: str,
        max_slippage_bps: int = 100,
    ) -> Order:
        """
        Create an exit order for a position.

        Args:
            position: Position to exit
            amount_tokens: Amount of tokens to sell
            expected_price: Expected token price
            exit_reason: Reason for exit (for logging)
            max_slippage_bps: Max slippage in basis points

        Returns:
            New Order in PENDING status
        """
        # Calculate SOL equivalent
        amount_sol = amount_tokens * expected_price

        return Order(
            order_type=OrderType.EXIT,
            side=OrderSide.SELL,
            position_id=str(position.id),
            token_address=position.token_address,
            token_symbol=position.token_symbol,
            amount_sol=amount_sol,
            amount_tokens=amount_tokens,
            expected_price=expected_price,
            max_slippage_bps=max_slippage_bps,
            is_simulated=self.is_simulation_mode or position.simulated,
        )

    def from_request(self, request: OrderCreateRequest) -> Order:
        """
        Create order from API request.

        Args:
            request: OrderCreateRequest with order details

        Returns:
            New Order in PENDING status
        """
        return Order(
            order_type=request.order_type,
            side=request.side,
            token_address=request.token_address,
            token_symbol=request.token_symbol,
            amount_sol=request.amount_sol,
            expected_price=request.expected_price,
            max_slippage_bps=request.max_slippage_bps,
            signal_id=request.signal_id,
            position_id=request.position_id,
            is_simulated=request.is_simulated or self.is_simulation_mode,
        )
