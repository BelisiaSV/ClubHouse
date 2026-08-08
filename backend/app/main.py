from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import mas

app = FastAPI(title="ClubHouse Football SaaS API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mas.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
