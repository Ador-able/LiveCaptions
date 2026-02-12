from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from .routers import tasks, download
from . import models

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="LiveCaptions API")

# Configure CORS
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(download.router, prefix="/api", tags=["download"]) # Add download router

@app.get("/")
def read_root():
    return {"message": "Welcome to LiveCaptions API"}
