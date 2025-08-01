from task_trak import app

# controller import
from task_trak.controllers.taskTxnController import addNewTask, editTask, startTask, doneTask, acceptTask, rejectTask, cancelTask, listTasks, deleteTask, checkSubtaskStatus

app.route('/add_new_task', methods=['GET','POST'])(addNewTask)
app.route('/add_new_task/<task_template_id>', methods=['GET','POST'])(addNewTask)

app.route('/task/<task_id>', methods=['GET','POST'])(editTask)

app.route('/start_task/<task_id>', methods=['POST'])(startTask)

app.route('/check_subtask_status/<task_id>', methods=['POST'])(checkSubtaskStatus)
app.route('/done_task/<task_id>', methods=['POST'])(doneTask)

app.route('/accept_task/<task_id>', methods=['POST'])(acceptTask)

app.route('/reject_task/<task_id>', methods=['POST'])(rejectTask)

app.route('/cancel_task/<task_id>', methods=['POST'])(cancelTask)

app.route('/list_tasks', methods=['GET'])(listTasks)
app.route('/list_tasks/<project_id>', methods=['GET'])(listTasks)

app.route('/delete_task/<task_id>', methods=['POST'])(deleteTask)