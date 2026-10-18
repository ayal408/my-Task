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
        assert backup['version']==1
        assert c.post('/api/import',json={'version':1,'tasks':[{'title':'valid'},{'title':''}]}).status_code==422
        assert len(c.get('/api/tasks').json())==1
        assert c.delete('/api/tasks/'+task['id']).status_code==204
        assert c.delete('/api/tasks/'+task['id']).status_code==404
        assert c.post('/api/import',json=backup).json()['imported']==1
        assert c.get('/api/tasks').json()[0]['status']=='done'
