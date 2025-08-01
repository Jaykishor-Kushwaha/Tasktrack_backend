from task_trak import app

# controller import
from task_trak.controllers.subTaskTxnController import addNewSubTask, editSubTask, doneSubTask, incompleteSubTask, listSubTasks, deleteSubTask

app.route('/add_new_subtask/<task_id>', methods=['GET','POST'])(addNewSubTask)

app.route('/subtask/<subtask_id>', methods=['GET','POST'])(editSubTask)

# app.route('/start_task/<task_id>', methods=['POST'])(startTask)

app.route('/done_subtask/<subtask_id>', methods=['POST'])(doneSubTask)

app.route('/incomplete_subtask/<subtask_id>', methods=['POST'])(incompleteSubTask)

# app.route('/reject_task/<task_id>', methods=['POST'])(rejectTask)

# app.route('/cancel_task/<task_id>', methods=['POST'])(cancelTask)

# app.route('/list_tasks', methods=['GET'])(listTasks)
app.route('/list_subtasks/<task_id>', methods=['GET'])(listSubTasks)

app.route('/delete_subtask/<subtask_id>', methods=['POST'])(deleteSubTask)