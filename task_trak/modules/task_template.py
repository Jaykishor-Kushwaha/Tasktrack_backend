from task_trak import app

# controller import
from task_trak.controllers.taskTemplateController import addNewTaskTemplate, editTaskTemplate, listTaskTemplates, deleteTaskTemplate, listTaskTemplatesAll, getTaskTemplateWithSubTasks

app.route('/add_new_task_template', methods=['POST'])(addNewTaskTemplate)
app.route('/add_new_task_template/<project_template_id>', methods=['GET'])(addNewTaskTemplate)

app.route('/task_template/<task_template_id>', methods=['GET','POST'])(editTaskTemplate)

# list standalone task templates only
app.route('/list_task_templates', methods=['GET'])(listTaskTemplates)
app.route('/list_task_templates/<project_id>', methods=['GET'])(listTaskTemplates)

app.route('/delete_task_template/<task_template_id>', methods=['POST'])(deleteTaskTemplate)

# list standalone + parential Task templates
app.route('/list_task_templates_all', methods=['GET'])(listTaskTemplatesAll)

# get task template with sub task templates list
app.route('/get_task_template/<task_template_id>', methods=['GET'])(getTaskTemplateWithSubTasks)