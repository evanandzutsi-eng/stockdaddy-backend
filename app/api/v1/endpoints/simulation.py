from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.db.session import get_db
from app.db.models.portfolio import DemoPortfolio, DemoTransaction # Ensure these match your models
from app.schemas.demo import DemoOrderRequest, DemoOrderResponse

router = APIRouter()

@router.post("/demo/order", response_model=DemoOrderResponse)
async def execute_demo_order(
    order: DemoOrderRequest,
    current_user_id: str = "mock-user-id", # Replace with actual JWT dependency: Depends(get_current_user)
    db: AsyncSession = Depends(get_db)
):
    """Submits a basic Market order against the ₦10,000,000 paper wallet."""
    
    # 1. Fetch or Create Demo Portfolio
    result = await db.execute(select(DemoPortfolio).where(DemoPortfolio.user_id == current_user_id))
    portfolio = result.scalars().first()
    
    if not portfolio:
        portfolio = DemoPortfolio(user_id=current_user_id, cash_balance=10000000.00)
        db.add(portfolio)
        await db.flush()

    # 2. Mock Execution Price (In production, fetch from Redis/DB tick data)
    execution_price = 37.67 if order.stock_symbol == "GTCO" else 100.00 
    total_value = execution_price * order.quantity

    # 3. Validate Balance for BUY
    if order.action == "BUY":
        if total_value > portfolio.cash_balance:
            raise HTTPException(status_code=400, detail="Insufficient sandbox funds.")
        portfolio.cash_balance -= total_value
    else:
        # SELL logic (omitted for brevity, would check holdings)
        portfolio.cash_balance += total_value

    # 4. Record Transaction
    transaction = DemoTransaction(
        id=str(uuid.uuid4()),
        portfolio_id=portfolio.id,
        stock_symbol=order.stock_symbol,
        action=order.action,
        quantity=order.quantity,
        execution_price=execution_price,
        total_value=total_value
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(portfolio)

    return DemoOrderResponse(
        success=True,
        message=f"Successfully executed {order.action} order for {order.quantity} units of {order.stock_symbol}.",
        transaction_id=transaction.id,
        new_cash_balance=portfolio.cash_balance,
        executed_price=execution_price
    )