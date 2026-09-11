"""FastAPI app — W1-T4 完整后端。

W1-T1 仅有 /health；T4 把 8 个 API + CSV 批量导入 + 改密接口接进来。

CORS：allow http://localhost:5173（前端 Vite dev origin），T1 已配不动。
路由分组：
    - api/teachers.py    → /api/teachers（2 个端点）
    - api/classes.py     → /api/classes（3 个端点）
    - api/students.py    → /api/classes/{id}/students/* + /api/students/{id}/*（4 个端点）
合计 9 个端点（含批量改密）。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import classes, students, teachers, questions

app = FastAPI(title="tiered-homework-backend")

# CORS：显式 allow 前端 dev origin，不用 *
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === W1-T4 路由挂载 ===
app.include_router(teachers.router)
app.include_router(classes.router)
app.include_router(students.router)

# === W3-T2 路由挂载 ===
app.include_router(questions.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "tiered-homework-backend"}