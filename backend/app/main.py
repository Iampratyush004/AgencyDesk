import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth_router,
    projects_router,
    tasks_router,
    comments_router,
    time_entries_router,
    files_router,
    invitations_router,
)

app = FastAPI(title="AgencyDesk API")

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(projects_router, prefix="/projects", tags=["projects"])
app.include_router(tasks_router, tags=["tasks"])
app.include_router(comments_router, tags=["comments"])
app.include_router(time_entries_router, tags=["time_entries"])
app.include_router(files_router, tags=["files"])
app.include_router(
    invitations_router,
    prefix="/invitations",
    tags=["invitations"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}