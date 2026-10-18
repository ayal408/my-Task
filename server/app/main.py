import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, String, Text, Date, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./tasks.db"), pool_pre_ping=True)
class Base(DeclarativeBase): pass
class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    project: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(20))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))
class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    project: str = Field(default="כללי", max_length=100)
    status: Literal["todo", "doing", "done"] = "todo"
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: date | None = None
    @field_validator("title", "project")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value: raise ValueError("יש להזין ערך")
        return value
class TaskOut(TaskInput):
    id: str
    created_at: str
    updated_at: str
    model_config = {"from_attributes": True}
class Backup(BaseModel):
    version: Literal[1] = 1
    tasks: list[TaskInput] = Field(max_length=10000)
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield
app = FastAPI(title="הלוח שלי", lifespan=lifespan)
def session():
    with Session(engine) as db: yield db
def now(): return datetime.now(timezone.utc).isoformat()
def add_task(db, payload):
    task = Task(id=str(uuid4()), **payload.model_dump(), created_at=now(), updated_at=now())
    db.add(task)
    return task
@app.get("/api/health")
def health(db: Session = Depends(session)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}
@app.get("/api/tasks", response_model=list[TaskOut])
def list_tasks(db: Session = Depends(session)):
    return db.scalars(select(Task).order_by(Task.created_at.desc())).all()
@app.post("/api/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskInput, db: Session = Depends(session)):
    task = add_task(db, payload)
    db.commit(); db.refresh(task)
    return task
@app.put("/api/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: str, payload: TaskInput, db: Session = Depends(session)):
    task = db.get(Task, task_id)
    if task is None: raise HTTPException(404, "המשימה לא נמצאה")
    for key, value in payload.model_dump().items(): setattr(task, key, value)
    task.updated_at = now()
    db.commit(); db.refresh(task)
    return task
@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, db: Session = Depends(session)):
    task = db.get(Task, task_id)
    if task is None: raise HTTPException(404, "המשימה לא נמצאה")
    db.delete(task); db.commit()
@app.get("/api/backup")
def backup(db: Session = Depends(session)):
    return {"version": 1, "tasks": [TaskInput.model_validate(TaskOut.model_validate(t).model_dump()).model_dump(mode="json") for t in db.scalars(select(Task)).all()]}
@app.post("/api/import")
def import_backup(payload: Backup, db: Session = Depends(session)):
    for task in payload.tasks: add_task(db, task)
    db.commit()
    return {"imported": len(payload.tasks)}
