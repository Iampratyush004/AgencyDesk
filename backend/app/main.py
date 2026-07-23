from fastapi import FastAPI
from app.api.routes import auth

app = FastAPI(title="AgencyDesk API")

app.include_router(auth.router, prefix="/auth", tags=["auth"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
