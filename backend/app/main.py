from fastapi import FastAPI
from app.api.routes import auth_router, projects_router, tasks_router

app = FastAPI(title="AgencyDesk API")

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(projects_router, prefix="/projects", tags=["projects"])
app.include_router(tasks_router, tags=["tasks"])
@app.get("/health")
def health_check():
    return {"status": "ok"}
