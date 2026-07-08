from fastapi import FastAPI

from app.routes import router

app = FastAPI(title="JobMatch AI API")
app.include_router(router)
