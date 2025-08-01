from task_trak import app

# controller import
from task_trak.controllers.projectTemplateController import addNewProjectTemplate, editProjectTemplate, listProjectTemplates, deleteProjectTemplate

app.route('/add_new_project_template', methods=['POST'])(addNewProjectTemplate)

app.route('/project_template/<project_template_id>', methods=['GET','POST'])(editProjectTemplate)

app.route('/list_project_templates', methods=['GET'])(listProjectTemplates)

app.route('/delete_project_template/<project_template_id>', methods=['POST'])(deleteProjectTemplate)