import test from 'node:test';
import assert from 'node:assert/strict';
import {dueMatches,sortTasks} from '../src/taskView.js';
const tasks=[{title:'ב',priority:'low',due_date:null,position:1,created_at:'2026-10-10'},{title:'א',priority:'high',due_date:'2026-10-21',position:0,created_at:'2026-10-11'}];
test('sorting keeps unplanned tasks after dated tasks and does not mutate source',()=>{assert.equal(sortTasks(tasks,'due')[0].title,'א');assert.equal(sortTasks(tasks,'priority')[0].priority,'high');assert.equal(sortTasks(tasks,'manual')[0].position,0);assert.equal(tasks[0].title,'ב')});
test('upcoming filter is inclusive and excludes overdue and undated tasks',()=>{assert.equal(dueMatches(tasks[1],'week','2026-10-19','2026-10-25'),true);assert.equal(dueMatches({due_date:'2026-10-18'},'week','2026-10-19','2026-10-25'),false);assert.equal(dueMatches(tasks[0],'week','2026-10-19','2026-10-25'),false);assert.equal(dueMatches(tasks[0],'none','2026-10-19','2026-10-25'),true)});
