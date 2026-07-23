from fastapi import FastAPI
from app.api.routes import auth_router, projects_router

app = FastAPI(title="AgencyDesk API")

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(projects_router, prefix="/projects", tags=["projects"])
@app.get("/health")
def health_check():
    return {"status": "ok"}
