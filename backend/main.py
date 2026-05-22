from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.database import init_db
from backend.router import router

app = FastAPI(title="MedBot - 问诊助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}
