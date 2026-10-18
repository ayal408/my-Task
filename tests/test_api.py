import os
import sys
import tempfile
from pathlib import Path
os.environ['DATABASE_URL']='sqlite:///'+str(Path(tempfile.mkdtemp())/'test.db')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from fastapi.testclient import TestClient
from app.main import app

def test_task_lifecycle_and_backup():
    with TestClient(app) as c:
        assert c.get('/api/health').status_code==200
        assert c.get('/api/tasks').json()==[]
        assert c.post('/api/tasks',json={'title':'   '}).status_code==422
        assert c.post('/api/tasks',json={'title':'x','status':'unknown'}).status_code==422
        task=c.post('/api/tasks',json={'title':'בדיקת משימה','due_date':'2026-10-20','project':'Amandex'}).json()
        assert task['title']=='בדיקת משימה'
        task['status']='done'
        assert c.put('/api/tasks/'+task['id'],json=task).json()['status']=='done'
        backup=c.get('/api/backup').json()
        assert backup['version']==2
        assert c.post('/api/import',json={'version':1,'tasks':[{'title':'valid'},{'title':''}]}).status_code==422
        assert len(c.get('/api/tasks').json())==1
        assert c.delete('/api/tasks/'+task['id']).status_code==204
        assert c.delete('/api/tasks/'+task['id']).status_code==404
        assert c.post('/api/import',json=backup).json()['imported']==1
        assert c.get('/api/tasks').json()[0]['status']=='done'

def test_checklist_recurrence_trash_history_and_order():
    with TestClient(app) as c:
        assert c.post('/api/tasks',json={'title':'missing date','recurrence':'daily'}).status_code==422
        t=c.post('/api/tasks',json={'title':'חודשי','due_date':'2027-01-31','recurrence':'monthly','checklist':[{'text':'שלב ראשון','done':True}]}).json()
        done=c.put('/api/tasks/'+t['id'],json={**t,'status':'done'}).json()
        all_tasks=c.get('/api/tasks').json()
        next_task=next(x for x in all_tasks if x['title']=='חודשי' and x['id']!=t['id'])
        assert next_task['due_date']=='2027-02-28'
        assert next_task['checklist'][0]['done'] is False
        c.put('/api/tasks/'+t['id'],json={**t,'status':'todo'})
        c.put('/api/tasks/'+t['id'],json={**t,'status':'done'})
        assert len([x for x in c.get('/api/tasks').json() if x['title']=='חודשי'])==2
        c.put('/api/tasks/'+next_task['id'],json={**next_task,'status':'done'})
        march=next(x for x in c.get('/api/tasks').json() if x['title']=='חודשי' and x['status']=='todo')
        assert march['due_date']=='2027-03-31'
        assert c.delete('/api/tasks/'+t['id']).status_code==204
        assert t['id'] not in [x['id'] for x in c.get('/api/tasks').json()]
        assert t['id'] in [x['id'] for x in c.get('/api/tasks?trash=true').json()]
        assert len(c.get('/api/tasks/'+t['id']+'/history').json())>=5
        assert c.post('/api/tasks/'+t['id']+'/restore').json()['deleted_at'] is None
        assert c.post('/api/reorder',json={'ids':[t['id']],'status':'doing'}).status_code==409
        assert c.post('/api/reorder',json={'ids':[t['id'],t['id']],'status':'done'}).status_code==422
        assert c.post('/api/reorder',json={'ids':[t['id']],'status':'done'}).status_code==200
        assert c.get('/api/backup').json()['tasks']

def test_legacy_tasks_survive_upgrade():
    from app.main import engine
    from sqlalchemy import text
    with TestClient(app) as c:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO tasks (id,title,description,project,status,priority,due_date,created_at,updated_at) VALUES ('legacy','legacy','','כללי','todo','medium',NULL,'2026','2026')"))
        item=next(t for t in c.get('/api/tasks').json() if t['id']=='legacy')
        assert item['checklist']==[] and item['recurrence']=='none'
        assert c.put('/api/tasks/legacy',json={**item,'checklist':[{'text':'new'}]}).status_code==200

def test_daily_weekly_and_old_backup_import():
    with TestClient(app) as c:
        for rule,expected in [('daily','2028-01-01'),('weekly','2028-01-07')]:
            t=c.post('/api/tasks',json={'title':rule,'recurrence':rule,'due_date':'2027-12-31'}).json()
            assert c.put('/api/tasks/'+t['id'],json={**t,'status':'done'}).status_code==200
            assert any(x['title']==rule and x['due_date']==expected for x in c.get('/api/tasks').json())
        assert c.post('/api/import',json={'version':1,'tasks':[{'title':'old backup'}]}).status_code==200
        t=c.post('/api/tasks',json={'title':'order one'}).json()
        u=c.post('/api/tasks',json={'title':'order two'}).json()
        assert c.post('/api/reorder',json={'ids':[u['id'],t['id']],'status':'todo'}).status_code==200
        result=c.get('/api/tasks').json()
        assert next(x for x in result if x['id']==u['id'])['position']<next(x for x in result if x['id']==t['id'])['position']
