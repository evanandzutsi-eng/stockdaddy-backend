import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models.portfolio import (
    SimulationPortfolio,
    SimulationHolding,
    SimulationTrade,
)
from app.schemas.simulation import (
    TradeAction,
    TradeExecutionRequest,
    HoldingSnapshot,
)

logger = logging.getLogger(__name__)


class InsufficientFundsError(Exception):
    """Raised when a BUY order exceeds the virtual cash balance."""
    pass


class InsufficientHoldingsError(Exception):
    """Raised when a SELL order exceeds the current holding quantity."""
    pass


class StockPriceUnavailableError(Exception):
    """Raised when no market data is available for the requested symbol."""
    pass


async def get_latest_stock_price(
    stock_symbol: str, 
    db: AsyncSession
) -> Decimal:
    """
    Fetches the most recent closing price for an NGX stock.
    
    In production, this queries the TimescaleDB hypertable for the latest tick.
    Currently returns a deterministic placeholder to unblock the simulation engine 
    until the Market Data module (File 9) is fully wired.
    
    TODO: Replace with actual TimescaleDB query:
        SELECT close_price FROM ngx_ticks 
        WHERE symbol = :symbol 
        ORDER BY timestamp DESC LIMIT 1
    """
    # Deterministic placeholder prices for development/testing
    PLACEHOLDER_PRICES = {
        "GTCO": Decimal("37.50"),
        "DANGCEM": Decimal("498.00"),
        "MTNN": Decimal("245.00"),
        "AIRTELAFRI": Decimal("1850.00"),
        "BUACEMENT": Decimal("92.00"),
        "ZENITHBANK": Decimal("42.30"),
        "ACCESSCORP": Decimal("18.75"),
        "UBA": Decimal("22.10"),
        "FBNH": Decimal("25.60"),
        "WAPCO": Decimal("45.00"),
    }
    
    price = PLACEHOLDER_PRICES.get(stock_symbol.upper())
    if price is None:
        raise StockPriceUnavailableError(
            f"No market data available for {stock_symbol}. "
            f"Available symbols: {list(PLACEHOLDER_PRICES.keys())}"
        )
    return price


async def get_or_create_portfolio(
    user_id: str, 
    db: AsyncSession
) -> SimulationPortfolio:
    """
    Retrieves the user's persistent portfolio or creates one 
    with the default ₦1,000,000 virtual balance.
    """
    result = await db.execute(
        select(SimulationPortfolio)
        .options(selectinload(SimulationPortfolio.holdings))
        .where(SimulationPortfolio.user_id == user_id)
    )
    portfolio = result.scalar_one_or_none()

    if portfolio is None:
        portfolio = SimulationPortfolio(
            user_id=user_id,
            cash_balance_ngn=Decimal(str(settings.DEMO_INITIAL_BALANCE_NGN)),
            total_trade_count=0,
            is_demo_graduated=False,
        )
        db.add(portfolio)
        await db.flush()  # Flush to generate the ID without committing
        logger.info(f"Created new simulation portfolio for user {user_id}")

    return portfolio


async def execute_trade(
    user_id: str,
    request: TradeExecutionRequest,
    db: AsyncSession,
) -> SimulationTrade:
    """
    CORE SIMULATION ENGINE: Executes a virtual BUY or SELL order.
    
    Architectural Mandate: ALL calculations happen server-side within a 
    single database transaction to prevent race conditions and client manipulation.
    """
    symbol = request.stock_symbol.upper()
    quantity = request.quantity
    action = request.action

    # 1. Fetch current market price
    current_price = await get_latest_stock_price(symbol, db)
    total_cost = current_price * Decimal(str(quantity))

    # 2. Load portfolio with row-level locking to prevent concurrent mutations
    result = await db.execute(
        select(SimulationPortfolio)
        .options(selectinload(SimulationPortfolio.holdings))
        .where(SimulationPortfolio.user_id == user_id)
        .with_for_update()  # PostgreSQL SELECT ... FOR UPDATE row lock
    )
    portfolio = result.scalar_one_or_none()

    if portfolio is None:
        portfolio = await get_or_create_portfolio(user_id, db)

    # 3. Execute trade logic
    if action == TradeAction.BUY:
        # --- BUY LOGIC ---
        if Decimal(str(portfolio.cash_balance_ngn)) < total_cost:
            raise InsufficientFundsError(
                f"Insufficient virtual funds. Required: ₦{total_cost:,.2f}, "
                f"Available: ₦{portfolio.cash_balance_ngn:,.2f}"
            )

        # Deduct cash
        portfolio.cash_balance_ngn = Decimal(str(portfolio.cash_balance_ngn)) - total_cost

        # Update or create holding
        holding = next(
            (h for h in portfolio.holdings if h.stock_symbol == symbol), 
            None
        )
        if holding is None:
            holding = SimulationHolding(
                portfolio_id=portfolio.id,
                stock_symbol=symbol,
                quantity=quantity,
                avg_cost_basis_ngn=current_price,
            )
            db.add(holding)
        else:
            # Weighted average cost basis recalculation
            old_total_cost = Decimal(str(holding.avg_cost_basis_ngn)) * Decimal(str(holding.quantity))
            new_total_cost = old_total_cost + total_cost
            new_quantity = holding.quantity + quantity
            holding.avg_cost_basis_ngn = (new_total_cost / Decimal(str(new_quantity))).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            holding.quantity = new_quantity

    elif action == TradeAction.SELL:
        # --- SELL LOGIC ---
        holding = next(
            (h for h in portfolio.holdings if h.stock_symbol == symbol), 
            None
        )
        if holding is None or holding.quantity < quantity:
            available = holding.quantity if holding else 0
            raise InsufficientHoldingsError(
                f"Insufficient holdings for {symbol}. "
                f"Requested: {quantity}, Available: {available}"
            )

        # Credit cash
        portfolio.cash_balance_ngn = Decimal(str(portfolio.cash_balance_ngn)) + total_cost

        # Reduce holding
        holding.quantity -= quantity
        if holding.quantity == 0:
            await db.delete(holding)

    # 4. Record immutable trade in audit log
    trade_record = SimulationTrade(
        portfolio_id=portfolio.id,
        stock_symbol=symbol,
        action=action.value,
        quantity=quantity,
        execution_price_ngn=current_price,
        total_value_ngn=total_cost,
    )
    db.add(trade_record)

    # 5. Increment trade counter (drives the Verification Gate)
    portfolio.total_trade_count += 1

    await db.flush()
    return trade_record


async def compute_portfolio_valuation(
    user_id: str,
    db: AsyncSession,
) -> dict:
    """
    Computes the full portfolio valuation server-side.
    Returns pre-calculated PnL figures so the client only renders static numbers.
    """
    result = await db.execute(
        select(SimulationPortfolio)
        .options(selectinload(SimulationPortfolio.holdings))
        .where(SimulationPortfolio.user_id == user_id)
    )
    portfolio = result.scalar_one_or_none()

    if portfolio is None:
        portfolio = await get_or_create_portfolio(user_id, db)

    cash = Decimal(str(portfolio.cash_balance_ngn))
    total_holdings_value = Decimal("0.00")
    total_unrealized_pnl = Decimal("0.00")
    holdings_snapshot = []

    for holding in portfolio.holdings:
        if holding.quantity == 0:
            continue

        try:
            current_price = await get_latest_stock_price(holding.stock_symbol, db)
        except StockPriceUnavailableError:
            current_price = Decimal(str(holding.avg_cost_basis_ngn))

        qty = Decimal(str(holding.quantity))
        cost_basis = Decimal(str(holding.avg_cost_basis_ngn))
        market_value = current_price * qty
        unrealized_pnl = (current_price - cost_basis) * qty
        pnl_pct = (
            (unrealized_pnl / (cost_basis * qty)) * Decimal("100")
            if cost_basis > 0 else Decimal("0.00")
        )

        total_holdings_value += market_value
        total_unrealized_pnl += unrealized_pnl

        holdings_snapshot.append(HoldingSnapshot(
            stock_symbol=holding.stock_symbol,
            quantity=holding.quantity,
            avg_cost_basis_ngn=float(cost_basis),
            current_market_price_ngn=float(current_price),
            unrealized_pnl_ngn=float(unrealized_pnl),
            unrealized_pnl_percentage=float(pnl_pct.quantize(Decimal("0.01"))),
            total_market_value_ngn=float(market_value),
        ))

    total_portfolio_value = cash + total_holdings_value
    initial_investment = Decimal(str(settings.DEMO_INITIAL_BALANCE_NGN))
    overall_pnl_pct = (
        ((total_portfolio_value - initial_investment) / initial_investment) * Decimal("100")
        if initial_investment > 0 else Decimal("0.00")
    )

    return {
        "user_id": user_id,
        "cash_balance_ngn": float(cash),
        "total_holdings_value_ngn": float(total_holdings_value),
        "total_portfolio_value_ngn": float(total_portfolio_value),
        "total_unrealized_pnl_ngn": float(total_unrealized_pnl),
        "total_unrealized_pnl_percentage": float(overall_pnl_pct.quantize(Decimal("0.01"))),
        "total_trade_count": portfolio.total_trade_count,
        "is_demo_graduated": portfolio.is_demo_graduated,
        "holdings": holdings_snapshot,
    }