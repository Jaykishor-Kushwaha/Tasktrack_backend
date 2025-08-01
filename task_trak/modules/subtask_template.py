from task_trak import app

# controller import
from task_trak.controllers.subTaskTemplateController import addNewSubTaskTemplate, editSubTaskTemplate, listSubTaskTemplates, deleteSubTaskTemplate

app.route('/add_new_subtask_template', methods=['POST'])(addNewSubTaskTemplate)
app.route('/add_new_subtask_template/<task_template_id>', methods=['GET'])(addNewSubTaskTemplate)

app.route('/subtask_template/<subtask_template_id>', methods=['GET','POST'])(editSubTaskTemplate)

app.route('/list_subtask_templates', methods=['GET'])(listSubTaskTemplates)
app.route('/list_subtask_templates/<task_id>', methods=['GET'])(listSubTaskTemplates)

app.route('/delete_subtask_template/<subtask_template_id>', methods=['POST'])(deleteSubTaskTemplate)