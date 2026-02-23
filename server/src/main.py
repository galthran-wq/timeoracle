from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.core.database import postgres_engine, Base
from src.core.metrics import MetricsMiddleware, metrics_endpoint
from src.api.users import router as users_router
from src.api.activity import router as activity_router
from src.api.timeline import router as timeline_router


app = FastAPI(
    title="Web API",
    description="",
    version="1.0.0",
    openapi_version="3.1.0",
)

app.add_middleware(MetricsMiddleware)
app.include_router(users_router)
app.include_router(activity_router)
app.include_router(timeline_router)

@app.get("/")
async def root():
    return {"message": "API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/metrics")
async def get_metrics():
    return await metrics_endpoint()


if __name__ == "__main__":
    import uvicorn
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    uvicorn.run(app, host="0.0.0.0", port=8000) 
