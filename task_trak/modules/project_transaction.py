from task_trak import app

# controller import
from task_trak.controllers.projectTxnController import addNewProject, editProject, listProjects, acceptProject, rejectProject, cancelProject, deleteProject


app.route('/add_new_project', methods=['GET','POST'])(addNewProject)
app.route('/add_new_project/<project_template_id>', methods=['GET','POST'])(addNewProject)

app.route('/project/<project_id>', methods=['GET','POST'])(editProject)

app.route('/list_projects', methods=['GET','POST'])(listProjects)

app.route('/accept_project/<project_id>', methods=['GET','POST'])(acceptProject)

app.route('/reject_project/<project_id>', methods=['GET','POST'])(rejectProject) #before calling these API, call the create new notification API; send description of that notification to this API with key "notification_text"

app.route('/cancel_project/<project_id>', methods=['GET','POST'])(cancelProject)

app.route('/delete_project/<project_id>', methods=['GET','POST'])(deleteProject)