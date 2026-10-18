import os
import calendar
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone, timedelta
from typing import Literal
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import create_engine, String, Text, Date, JSON, ForeignKey, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

engine = create_engine(os.getenv('DATABASE_URL', 'sqlite:///./tasks.db'), pool_pre_ping=True)
class Base(DeclarativeBase): pass
class Task(Base):
    __tablename__ = 'tasks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    project: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(20))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))
# Additive tables keep existing v1 task rows intact.
class Details(Base):
    __tablename__ = 'task_details'
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
class History(Base):
    __tablename__ = 'task_history'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey('tasks.id'), index=True)
    at: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(30))
    snapshot: Mapped[dict] = mapped_column(JSON)
class Checklist(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    done: bool = False
    @field_validator('text')
    @classmethod
    def trim(cls,v):
        if not v.strip(): raise ValueError('empty item')
        return v.strip()
class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=10000)
    project: str = Field(default='כללי', min_length=1, max_length=100)
    status: Literal['todo','doing','done'] = 'todo'
    priority: Literal['low','medium','high'] = 'medium'
    due_date: date | None = None
    checklist: list[Checklist] = Field(default_factory=list, max_length=100)
    focus_date: date | None = None
    recurrence: Literal['none','daily','weekly','monthly'] = 'none'
    reminder_date: date | None = None
    position: float = Field(default=0, ge=-1e12, le=1e12, allow_inf_nan=False)
    @field_validator('title','project')
    @classmethod
    def clean(cls,v):
        if not v.strip(): raise ValueError('יש להזין ערך')
        return v.strip()
    @model_validator(mode='after')
    def recurring_date(self):
        if self.recurrence != 'none' and not self.due_date:
            raise ValueError('משימה חוזרת חייבת תאריך יעד')
        return self
class Backup(BaseModel):
    version: Literal[1,2] = 2
    tasks: list[TaskInput] = Field(max_length=10000)
class Changes(BaseModel):
    ids: list[str] = Field(max_length=10000)
    status: Literal['todo','doing','done']
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    yield
app=FastAPI(title='הלוח שלי',version='2.0.0',lifespan=lifespan)
def session():
    with Session(engine) as db: yield db
def now(): return datetime.now(timezone.utc).isoformat()
base_keys={'title','description','project','status','priority','due_date'}
def detail(db,t):
    row=db.get(Details,t.id)
    if row is None:
        row=Details(task_id=t.id,data={});db.add(row);db.flush()
    return row
def output(db,t):
    data=detail(db,t).data
    return {**{k:getattr(t,k) for k in base_keys},'id':t.id,'created_at':t.created_at,'updated_at':t.updated_at,
            'checklist':data.get('checklist',[]),'focus_date':data.get('focus_date'),
            'recurrence':data.get('recurrence','none'),'reminder_date':data.get('reminder_date'),
            'position':data.get('position',0),'deleted_at':data.get('deleted_at')}
def record(db,t,action):
    snapshot=output(db,t)
    snapshot={k:(v.isoformat() if isinstance(v,date) else v) for k,v in snapshot.items()}
    db.add(History(id=str(uuid4()),task_id=t.id,at=now(),action=action,snapshot=snapshot))
def get_task(db,id,deleted=False):
    t=db.scalar(select(Task).where(Task.id==id).with_for_update())
    if t is None or (detail(db,t).data.get('deleted_at') and not deleted): raise HTTPException(404,'המשימה לא נמצאה')
    return t
def add_task(db,p):
    fields=p.model_dump();t=Task(id=str(uuid4()),**{k:fields[k] for k in base_keys},created_at=now(),updated_at=now())
    db.add(t);db.flush()
    db.add(Details(task_id=t.id,data={k:v for k,v in p.model_dump(mode='json').items() if k not in base_keys}));db.flush()
    record(db,t,'created');return t
@app.get('/api/health')
def health(db:Session=Depends(session)):
    db.execute(text('SELECT 1'));return {'status':'ok'}
@app.get('/api/tasks')
def list_tasks(trash:bool=False,db:Session=Depends(session)):
    result=[output(db,t) for t in db.scalars(select(Task).order_by(Task.created_at.desc())).all()]
    db.commit()
    return sorted([t for t in result if bool(t['deleted_at'])==trash],key=lambda t:t['position'])
@app.post('/api/tasks',status_code=201)
def create_task(payload:TaskInput,db:Session=Depends(session)):
    t=add_task(db,payload);db.commit();return output(db,t)
@app.put('/api/tasks/{task_id}')
def update_task(task_id:str,payload:TaskInput,db:Session=Depends(session)):
    t=get_task(db,task_id);before=t.status;row=detail(db,t);old=dict(row.data)
    record(db,t,'before_update')
    fields=payload.model_dump()
    for k in base_keys:setattr(t,k,fields[k])
    row.data={**old,**{k:v for k,v in payload.model_dump(mode='json').items() if k not in base_keys}}
    t.updated_at=now()
    # One next occurrence per completed instance, even after reopening and completing again.
    if before!='done' and t.status=='done' and payload.recurrence!='none' and not old.get('next_id'):
        due=payload.due_date;anchor=old.get('monthly_day',due.day)
        if payload.recurrence=='monthly':
            year=due.year+(due.month==12);month=due.month%12+1
            next_date=date(year,month,min(anchor,calendar.monthrange(year,month)[1]))
        else:next_date=due+timedelta(days=1 if payload.recurrence=='daily' else 7)
        new=payload.model_copy(update={'status':'todo','due_date':next_date,'focus_date':None,'reminder_date':(next_date-(due-payload.reminder_date)) if payload.reminder_date else None,
                                      'checklist':[item.model_copy(update={'done':False}) for item in payload.checklist]})
        next_task=add_task(db,new);next_row=detail(db,next_task);next_row.data={**next_row.data,'monthly_day':anchor}
        row.data={**row.data,'next_id':next_task.id}
    record(db,t,'updated');db.commit();return output(db,t)
@app.post('/api/reorder')
def reorder(payload:Changes,db:Session=Depends(session)):
    if len(set(payload.ids))!=len(payload.ids):raise HTTPException(422,'duplicate ids')
    tasks=[get_task(db,id) for id in payload.ids]
    if any(t.status!=payload.status for t in tasks):raise HTTPException(409,'יש לרענן את הלוח לפני סידור')
    for index,t in enumerate(tasks):
        row=detail(db,t);row.data={**row.data,'position':index};t.updated_at=now()
    db.commit();return {'ordered':len(tasks)}
@app.delete('/api/tasks/{task_id}',status_code=204)
def delete_task(task_id:str,db:Session=Depends(session)):
    t=get_task(db,task_id);record(db,t,'before_delete');row=detail(db,t);row.data={**row.data,'deleted_at':now()};record(db,t,'deleted');db.commit()
@app.post('/api/tasks/{task_id}/restore')
def restore_task(task_id:str,db:Session=Depends(session)):
    t=get_task(db,task_id,True);row=detail(db,t);row.data={**row.data,'deleted_at':None};record(db,t,'restored');db.commit();return output(db,t)
@app.get('/api/tasks/{task_id}/history')
def history(task_id:str,db:Session=Depends(session)):
    get_task(db,task_id,True)
    return [{'id':h.id,'at':h.at,'action':h.action,'snapshot':h.snapshot} for h in db.scalars(select(History).where(History.task_id==task_id).order_by(History.at.desc())).all()]
@app.get('/api/backup')
def backup(db:Session=Depends(session)):
    tasks=[output(db,t) for t in db.scalars(select(Task)).all()]
    db.commit()
    return {'version':2,'tasks':[TaskInput.model_validate(t).model_dump(mode='json') for t in tasks if not t['deleted_at']]}
@app.post('/api/import')
def import_backup(payload:Backup,db:Session=Depends(session)):
    for task in payload.tasks:add_task(db,task)
    db.commit();return {'imported':len(payload.tasks)}
