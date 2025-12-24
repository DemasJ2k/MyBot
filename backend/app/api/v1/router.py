from fastapi import APIRouter
from app.api.v1 import auth_routes, data_routes, strategy_routes, backtest_routes, optimization_routes, ai_routes

api_router = APIRouter()
api_router.include_router(auth_routes.router, prefix="/auth")
api_router.include_router(data_routes.router)
api_router.include_router(strategy_routes.router)
api_router.include_router(backtest_routes.router)
api_router.include_router(optimization_routes.router)
api_router.include_router(ai_routes.router)
