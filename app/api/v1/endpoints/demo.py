import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis

from app.schemas.demo import (
    DemoInitializeResponse, 
    DemoStatusResponse, 
    TutorialStepID, 
    TutorialStepUpdateRequest,
    TutorialStepStatus
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# --------------------------------------------------------------------------
# DEPENDENCY INJECTION (Redis Client)
# --------------------------------------------------------------------------
# In production, this is injected via a centralized database/redis session manager.
# For this module's standalone execution, we define the dependency signature.
async def get_redis_client() -> Redis:
    """
    Dependency to yield an active async Redis connection.
    """
    # Placeholder for the actual Redis connection pool dependency 
    # which will be fully wired in the db/session.py module.
    raise NotImplementedError("Redis dependency must be wired via app.db.session.get_redis")

# --------------------------------------------------------------------------
# MOCK USER DEPENDENCY (Until Auth module is complete)
# --------------------------------------------------------------------------
class MockUser:
    def __init__(self, user_id: str):
        self.id = user_id

async def get_current_user() -> MockUser:
    """
    Temporary dependency to simulate an authenticated user.
    Will be replaced by JWT extraction in app.core.security.
    """
    return MockUser(user_id="demo_user_001")

# --------------------------------------------------------------------------
# TUTORIAL GATE DEFINITIONS
# --------------------------------------------------------------------------
TUTORIAL_GATES = {
    TutorialStepID.VIEW_WATCHLIST: {
        "title": "Build Your First Watchlist",
        "description": "Track your favorite NGX stocks like $GTCO and $DANGCEM.",
        "order": 1
    },
    TutorialStepID.EXECUTE_FIRST_TRADE: {
        "title": "Execute a Virtual Trade",
        "description": "Use your ₦1,000,000 virtual balance to buy your first stock.",
        "order": 2
    },
    TutorialStepID.VIEW_PORTFOLIO_PNL: {
        "title": "Monitor Your P&L",
        "description": "See how server-side calculations track your profit and loss in real-time.",
        "order": 3
    },
    TutorialStepID.EXPLORE_COMMUNITY: {
        "title": "Join the Community",
        "description": "Once you complete 3 trades, unlock the anti-scam moderated forums.",
        "order": 4
    }
}

# --------------------------------------------------------------------------
# ENDPOINTS
# --------------------------------------------------------------------------

@router.post("/initialize", response_model=DemoInitializeResponse, status_code=status.HTTP_201_CREATED)
async def initialize_demo_environment(
    current_user: MockUser = Depends(get_current_user),
    redis: Redis = Depends(get_redis_client)
):
    """
    Initializes the Beginner Demo Version. 
    Creates a Redis-backed virtual portfolio with ₦1,000,000 and resets the tutorial state.
    """
    user_id = current_user.id
    portfolio_key = f"demo:portfolio:{user_id}"
    tutorial_key = f"demo:tutorial:{user_id}"

    # 1. Initialize Virtual Portfolio in Redis (TTL: 30 days for inactive demos)
    portfolio_state = {
        "balance_ngn": settings.DEMO_INITIAL_BALANCE_NGN,
        "holdings": {},
        "trade_count": 0,
        "initialized": True
    }
    await redis.set(portfolio_key, json.dumps(portfolio_state), ex=60*60*24*30)

    # 2. Initialize Tutorial State
    tutorial_state = {step.value: False for step in TutorialStepID}
    await redis.set(tutorial_key, json.dumps(tutorial_state), ex=60*60*24*30)

    logger.info(f"Demo environment initialized for user {user_id}")

    return DemoInitializeResponse(
        user_id=user_id,
        virtual_balance_ngn=settings.DEMO_INITIAL_BALANCE_NGN,
        status="initialized"
    )

@router.get("/status", response_model=DemoStatusResponse)
async def get_demo_status(
    current_user: MockUser = Depends(get_current_user),
    redis: Redis = Depends(get_redis_client)
):
    """
    Retrieves the current state of the user's virtual portfolio and tutorial progress.
    """
    user_id = current_user.id
    portfolio_key = f"demo:portfolio:{user_id}"
    tutorial_key = f"demo:tutorial:{user_id}"

    # Fetch Portfolio State
    portfolio_raw = await redis.get(portfolio_key)
    if not portfolio_raw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Demo portfolio not initialized. Please call /demo/initialize first."
        )
    portfolio_state = json.loads(portfolio_raw)

    # Fetch Tutorial State
    tutorial_raw = await redis.get(tutorial_key)
    tutorial_state = json.loads(tutorial_raw) if tutorial_raw else {step.value: False for step in TutorialStepID}

    # Build Tutorial Steps Response
    steps_response = []
    completed_count = 0
    for step_id, meta in TUTORIAL_GATES.items():
        is_completed = tutorial_state.get(step_id.value, False)
        if is_completed:
            completed_count += 1
        steps_response.append(TutorialStepStatus(
            step_id=step_id,
            title=meta["title"],
            description=meta["description"],
            is_completed=is_completed
        ))

    # Sort by defined order
    steps_response.sort(key=lambda x: TUTORIAL_GATES[x.step_id]["order"])

    total_steps = len(TUTORIAL_GATES)
    progress_pct = (completed_count / total_steps) * 100 if total_steps > 0 else 0.0

    return DemoStatusResponse(
        user_id=user_id,
        portfolio_initialized=portfolio_state.get("initialized", False),
        current_virtual_balance_ngn=portfolio_state.get("balance_ngn", 0.0),
        tutorial_steps=steps_response,
        overall_progress_percentage=round(progress_pct, 2)
    )

@router.put("/tutorial/{step_id}", status_code=status.HTTP_200_OK)
async def update_tutorial_step(
    step_id: TutorialStepID,
    payload: TutorialStepUpdateRequest,
    current_user: MockUser = Depends(get_current_user),
    redis: Redis = Depends(get_redis_client)
):
    """
    Marks a specific tutorial gate as completed. 
    Enforces sequential progression to ensure beginners don't skip critical onboarding.
    """
    user_id = current_user.id
    tutorial_key = f"demo:tutorial:{user_id}"

    tutorial_raw = await redis.get(tutorial_key)
    if not tutorial_raw:
        raise HTTPException(status_code=404, detail="Tutorial state not found. Initialize demo first.")
    
    tutorial_state = json.loads(tutorial_raw)

    # Enforce sequential progression (cannot complete step 2 before step 1)
    current_step_order = TUTORIAL_GATES[step_id]["order"]
    if current_step_order > 1:
        # Find the previous step ID
        prev_step_id = next((s for s, meta in TUTORIAL_GATES.items() if meta["order"] == current_step_order - 1), None)
        if prev_step_id and not tutorial_state.get(prev_step_id.value, False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You must complete the previous tutorial step before unlocking this one."
            )

    # Update state
    tutorial_state[step_id.value] = payload.completed
    await redis.set(tutorial_key, json.dumps(tutorial_state), ex=60*60*24*30)

    return {"message": f"Step '{step_id.value}' marked as {'completed' if payload.completed else 'incomplete'}."}