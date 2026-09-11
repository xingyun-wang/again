"""FastAPI app — W1-T1 真实后端。

最小 hello world：CORS 通 /health，前端可 ping。
T2/T4 不在本任务范围（不做班级/学生/档位）。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="tiered-homework-backend")

# CORS：显式 allow 前端 dev origin，不用 *
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "tiered-homework-backend"}
