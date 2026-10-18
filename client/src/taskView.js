export function dueMatches(task,filter,today,weekEnd){
 if(filter==='today')return task.due_date===today;
 if(filter==='week')return !!task.due_date&&task.due_date>=today&&task.due_date<=weekEnd;
 if(filter==='none')return !task.due_date;
 return true;
}
export function sortTasks(tasks,mode){
 const rank={high:0,medium:1,low:2};
 return [...tasks].sort((a,b)=>mode==='due'?(a.due_date||'9999').localeCompare(b.due_date||'9999'):mode==='priority'?rank[a.priority]-rank[b.priority]:mode==='title'?a.title.localeCompare(b.title,'he'):mode==='newest'?b.created_at.localeCompare(a.created_at):a.position-b.position);
}
