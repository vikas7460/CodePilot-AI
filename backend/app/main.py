from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.repo_routes import router as repo_router

app = FastAPI(
    title="AI Software Engineer Backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repo_router, prefix="/repos")


@app.get("/")
def home():
    return {
        "message": "AI Software Engineer Backend is running",
        "status": "ok",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }