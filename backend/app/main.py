from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import compensation, players, wellness

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ClubHouse Football SaaS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(compensation.router)
app.include_router(wellness.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
