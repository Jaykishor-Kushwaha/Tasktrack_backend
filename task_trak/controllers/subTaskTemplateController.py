from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists
from flask import jsonify, request, session

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.SubTaskTemplate import (SubTaskTemplate as SubTaskTemplate)
from task_trak.db.models.TaskTemplate import (TaskTemplate as TaskTemplate)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker

from task_trak.controllers.taskTemplateController import get_task_template_object, parse_duration
from task_trak.controllers.projectTemplateController import get_project_template_object
from task_trak.controllers.attachmentController import get_attachments, delete_attachments
from task_trak.controllers.userActivityController import createUserActivity

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TranType, e_ActionType

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@admin_or_owner
def addNewSubTaskTemplate(user_type, task_template_id=None):
    """
    Add a new sub-task template.

    **POST**: Creates a new sub-task template in the database.

    :return: JSON response with status message and appropriate HTTP status code.
    """
    if request.method == 'POST':
        subtask_template_data = request.get_json()
        try:
            subtask_add_status = add_subtask_template_object(subtask_template_data)
            if not subtask_add_status:
                return jsonify({"status":"error", "message":f"Task Template with the ID {subtask_template_data['TaskTmplID']} is not found."}), 404
            elif subtask_add_status["status"]:
                return jsonify({"status":"success", "message":"Added sub-task successfully.", "data":subtask_add_status["subtask_info"]}), 201
            else:
                return jsonify({"status":"error", "message":"Approx duration exceeding total duration of parent task."}), 400
        except Exception as e:
            app.logger.error(e)
            error_message = str(e.orig)
            if 'UNIQUE constraint failed: sub_task_template.Name' in error_message:
                return jsonify({"status":"error", "message":"SubTask Name already exists"}), 409
            elif 'UNIQUE constraint failed: sub_task_template.OrdNo' in error_message:
                return jsonify({"status":"error", "message":"Order Number already exists"}), 409
            elif 'UNIQUE constraint failed: sub_task_template.TaskTmplID, sub_task_template.Name' in error_message:
                return jsonify({"status":"error", "message":f"Task with Name {subtask_template_data['Name']} already exists for project template."}), 409
            else:
                return jsonify({"status":"error", "message":"Failed to add sub-task."}), 500
    else:
        task_template = get_task_template_object(task_template_id)
        if task_template:
            last_ordno = get_max_ordno_task(task_template_id)
            return jsonify({"status":"success", "data":last_ordno+1}), 200
        else:
            return jsonify({"status":"error", "message":f"Task Template with ID {task_template_id} doesn't exists."}), 200

@admin_or_owner
def editSubTaskTemplate(user_type, subtask_template_id):
    """
    Edit an existing sub-task template.

    **POST**: Updates an existing sub-task template in the database.

    :param subtask_template_id: ID of the sub-task template to edit.
    :return: JSON response with status message and appropriate HTTP status code.
    """
    subtask_template = get_subtask_template_object(subtask_template_id)
    if subtask_template is None:
        return jsonify({"status":"error", "message":f"Sub-task with ID {subtask_template_id} does not exist."}), 404
    if request.method == 'POST':
        subtask_template_data = request.get_json()
        try:
            response = edit_subtask_template_object(subtask_template, subtask_template_data)
            if not response:
                return jsonify({"status":"error", "message":"Approx duration exceeding total duration of parent task."}), 400
            return response
        except Exception as e:
            app.logger.error(e)
            error_message = str(e.orig)
            if 'UNIQUE constraint failed: sub_task_template.TaskTmplID, sub_task_template.Name' in error_message:
                return jsonify({"status":"error", "message":"SubTask Name already exists"}), 409
            return jsonify({"status":"error", "message":"Failed to edit sub-task."}), 500
    else:
        subtask_template_data = subtask_template.to_dict()
        parent_task_template = get_task_template_object(subtask_template.TaskTmplID)
        if parent_task_template is None:
            parent_task_template_name, parent_project_template_name = "", ""
        else:
            parent_task_template_name = parent_task_template.Name #get the parent_task_template_name
            parent_project_of_task_template = get_project_template_object(int(parent_task_template.ProjTmplID)) if parent_task_template.ProjTmplID is not None else None
            if parent_project_of_task_template: #if parent_project_template is found for the parent_task_template then set the name
                parent_project_template_name = parent_project_of_task_template.Name
            else:
                parent_project_template_name = ""
        subtask_template_data['parent_task_template_name'] = parent_task_template_name
        subtask_template_data['parent_project_template_name'] = parent_project_template_name
        subtask_template_data['attachments_no'] = len(get_attachments(subtask_template.ID, e_TranType.SubTaskTmpl.idx))
        return jsonify(subtask_template_data), 200
        
    
@admin_or_owner
def listSubTaskTemplates(user_type, task_id=None):
    """
    List all sub-task templates.

    **GET**: Retrieves a list of all sub-task templates from the database.

    :return: JSON response with list of sub-task templates and appropriate HTTP status code.
    """
    if request.method == 'GET':
        try:
            subtask_list = list_subtask_templates(task_id)
            if subtask_list:
                return jsonify({"status": "success", "data": subtask_list}), 200
            else:
                return jsonify({"status":"success", "data": []}), 200
        except ValueError as e:
            app.logger.error(e)
            return jsonify({"status": "error", "message": str(e)}), 404
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to list sub-task templates."}), 500

@admin_or_owner
def deleteSubTaskTemplate(user_type, subtask_template_id):
    session = DBSession()
    try:
        # Query the subtask template
        subtask_template = session.query(SubTaskTemplate).filter(SubTaskTemplate.ID == int(subtask_template_id)).one_or_none()

        if subtask_template is None:
            return jsonify({"status": f"Sub-Task template with ID {subtask_template_id} not found."}), 404

        if not delete_attachments(subtask_template.ID, e_TranType.SubTaskTmpl.idx):
            return jsonify({"status":"error", "message":"Error occured while deleting the attachments."}), 500

        change_log = ""
        ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
        for column in subtask_template.__table__.columns:
            if column.name not in ignored_fields:
                change_log += f"{column.name}: {getattr(subtask_template, column.name)} => NaN\n"
        createUserActivity(ActionType=e_ActionType.DeleteRecord.idx, ActionDscr=e_ActionType.DeleteRecord.textval, EntityType=e_TranType.SubTaskTmpl.idx, EntityID=subtask_template.ID, ChangeLog=change_log)

        session.delete(subtask_template)
        session.commit()
        session.close()
        return jsonify({"status":"success", "message":"Sub-Task template deleted successfully."}), 200
    except Exception as e:
        session.rollback()
        print(e)
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to delete Sub-Task template."}), 500        
        
def add_subtask_template_object(subtask_template_data):
    """
    Add a new sub-task template to the database.

    :param subtask_template_data: Data of the sub-task template to add.
    :return: Dictionary indicating the status of the operation and subtask information.
    """
    subtask_template = SubTaskTemplate()
    change_log = ""
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    if 'TaskTmplID' in subtask_template_data.keys():
        parent_task_template = get_task_template_object(subtask_template_data['TaskTmplID'])
        if not parent_task_template:
            return False
        else: #if parent_task_template found with the TaskTmplID passed in payload then proceeed ahead
            pass
    if 'OrdNo' not in subtask_template_data.keys():
        last_ordno = get_max_ordno_task(subtask_template_data['TaskTmplID'])
        change_log += f"OrdNo: NaN => {int(last_ordno) + 1}\n"
        setattr(subtask_template, 'OrdNo', int(last_ordno) + 1)

    for key, value in subtask_template_data.items():
        # Skip fields that should be ignored
        if key in ignored_fields:
            continue
        if key == "AprxDuration":
            if exceeding_task_aprx_duration(subtask_template_data, subtask_template_data['TaskTmplID']):
                return {"status": False, "subtask_ID": None}
            else:
                subtask_duration_days, subtask_duration_hours, subtask_duration_minutes = parse_duration(float(value))
                subtask_template.AprxDuration = timedelta(days=subtask_duration_days, hours=subtask_duration_hours, minutes=subtask_duration_minutes)
                change_log += f"AprxDuration: NaN => {subtask_template.AprxDuration}\n"
        elif key in ["TaskTmplID", "OrdNo"]:
            change_log += f"{key}: NaN => {value}\n"
            setattr(subtask_template, key, int(value))
        else:
            if value not in [None, '', ' ']:
                change_log += f"{key}: NaN => {value}\n"
            setattr(subtask_template, key, value)

    subtask_template = set_models_attr.setCreatedInfo(subtask_template)
    db_session = DBSession()
    db_session.add(subtask_template)
    db_session.commit()
    db_session.refresh(subtask_template)
    db_session.close()
    createUserActivity(ActionType=e_ActionType.AddRecord.idx, ActionDscr=e_ActionType.AddRecord.textval, EntityType=e_TranType.SubTaskTmpl.idx, EntityID=subtask_template.ID, ChangeLog=change_log)
    return {"status": True, "subtask_info": {"ID": subtask_template.ID, "ordNo": subtask_template.OrdNo}}


def edit_subtask_template_object(selected_template, update_data):
    """
    Edit an existing sub-task template in the database.

    :param selected_template: Sub-task template object to update.
    :param update_data: Updated data of the sub-task template.
    :return: JSON response with status message and appropriate HTTP status code.
    """
    change_log = ""
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    for key, value in update_data.items():
        if getattr(selected_template, key) != update_data[key]:
            # Skip fields that should be ignored
            if key in ignored_fields:
                continue
            if key == "AprxDuration":
                if exceeding_task_aprx_duration(update_data, selected_template.TaskTmplID, selected_template):
                    return False
                
                # Parse and set the new AprxDuration
                subtask_duration_days, subtask_duration_hours, subtask_duration_minutes = parse_duration(float(value))
                calculated_aprx_duration = timedelta(days=subtask_duration_days, hours=subtask_duration_hours, minutes=subtask_duration_minutes)
                if selected_template.AprxDuration != calculated_aprx_duration:
                    change_log += f"{key}: {selected_template.AprxDuration} => {calculated_aprx_duration}\n"
                    selected_template.AprxDuration = calculated_aprx_duration
            elif key == "TaskTmplID":
                change_log += f"{key}: {selected_template.TaskTmplID} => {value}\n"
                setattr(selected_template, key, int(value))
            else:
                if key == "OrdNo" and int(selected_template.OrdNo) != int(value):
                    change_log += f"{key}: {selected_template.OrdNo} => {value}\n"
                else:
                    old_value = getattr(selected_template, key)
                    if old_value in [None, '', ' '] and value in [None, '', ' ']:
                        # Both current and new values are empty or None; no change, no log.
                        pass
                    elif old_value not in [None, '', ' '] and value not in [None, '', ' '] and old_value != value:
                        # Both current and new values have data, and they are different.
                        change_log += f"{key}: {old_value} => {value}\n"
                    elif old_value in [None, '', ' '] and value not in [None, '', ' ']:
                        # Current value is empty, new value has data.
                        change_log += f"{key}: NaN => {value}\n"
                    elif old_value not in [None, '', ' '] and value in [None, '', ' ']:
                        # Current value has data, new value is empty.
                        change_log += f"{key}: {old_value} => NaN\n"
                    # change_log += f"{key}: {getattr(selected_template, key)} => {value}\n"
                setattr(selected_template, key, value)
        else:
            pass # If no data change then nothing to do
    
    selected_template = set_models_attr.setUpdatedInfo(selected_template)
    db_session = DBSession()
    db_session.add(selected_template)
    db_session.commit()
    if change_log:
        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.SubTaskTmpl.idx, EntityID=selected_template.ID, ChangeLog=change_log)
    db_session.close()
    return jsonify({"status": "success", "message": "Updated sub-task template successfully."}), 200


def get_subtask_template_object(selected_template_id):
    """
    Retrieve a sub-task template object from the database.

    :param selected_template_id: ID of the sub-task template to retrieve.
    :return: Sub-task template object or None if not found.
    """
    session = DBSession()
    template = session.query(SubTaskTemplate).filter(SubTaskTemplate.ID == selected_template_id).one_or_none()
    session.close()
    return template

def list_subtask_templates(task_id):
    """
    List all sub-task templates from the database.

    :return: JSON response with list of sub-task templates.
    """
    session = DBSession()
    if task_id:
        # Check if the project template exists
        task_template = session.query(TaskTemplate).filter(TaskTemplate.ID == int(task_id)).one_or_none()
        if not task_template:
            session.close()
            raise ValueError(f"Task template with ID {task_id} not found.")
        subtask_templates = session.query(SubTaskTemplate).filter(SubTaskTemplate.TaskTmplID == int(task_id)).all()
        parent_task_template_name = task_template.Name #get the parent_task_template_name
        if task_template.ProjTmplID:
            parent_project_of_task_template = get_project_template_object(int(task_template.ProjTmplID))
            if parent_project_of_task_template: #if parent_project_template is found for the parent_task_template then set the name
                parent_project_template_name = parent_project_of_task_template.Name
            else:
                parent_project_template_name = ""
        else:
            parent_project_template_name = ""
    else:
        subtask_templates = session.query(SubTaskTemplate).order_by(desc(SubTaskTemplate.ID)).all()
        parent_task_template_name, parent_project_template_name = "", ""
    session.close()
    subtask_templates_list = []
    for task_template in subtask_templates:
        subtask_data = task_template.to_dict()
        subtask_data['parent_task_template_name'] = parent_task_template_name
        subtask_data['parent_project_template_name'] = parent_project_template_name
        subtask_templates_list.append(subtask_data)
    return subtask_templates_list

def exceeding_task_aprx_duration(template_data, parent_task_template_id, current_subtask_template=None):
    """
    Check if adding a sub-task template will exceed the approximate duration of its parent task.

    :param template_data: Dictionary containing sub-task template information.
    :param parent_task_template_id: ID of the parent task template.
    :return: True if adding the sub-task template will exceed the parent task's approximate duration, False otherwise.
    """
    session = DBSession()
    parent_task = session.query(TaskTemplate).filter(TaskTemplate.ID == parent_task_template_id).one_or_none()
    if parent_task is None:
        session.close()
        return False
    if current_subtask_template is None:
        total_subtask_duration = sum([sub_task.AprxDuration for sub_task in parent_task.subtask_templates], timedelta())
    else:
        total_subtask_duration = sum([sub_task.AprxDuration for sub_task in parent_task.subtask_templates if sub_task.ID!=current_subtask_template.ID], timedelta())
    subtask_duration_days, subtask_duration_hours, subtask_duration_minutes = parse_duration(float(template_data['AprxDuration']))

    total_subtask_duration += timedelta(days=subtask_duration_days, hours=subtask_duration_hours, minutes=subtask_duration_minutes)
    session.close()

    parent_task_duration = parent_task.AprxDuration
    return total_subtask_duration > parent_task_duration

    
def get_max_ordno_task(parent_task_template_id):
    """
    Get the maximum order number of sub-tasks for a given parent task template.

    :param parent_task_template_id: ID of the parent task template.
    :return: The maximum order number of sub-tasks for the parent task template.
    """
    session = DBSession()
    # Ensure parent_task is within an active session
    parent_task = session.query(TaskTemplate).filter(TaskTemplate.ID == parent_task_template_id).one_or_none()
    # If parent_task is not found, handle appropriately
    if parent_task is None:
        session.close()
        return False
    subtask_list_for_task = parent_task.subtask_templates
    session.close()
    max_subtask_ordno = max([sub_task.OrdNo for sub_task in subtask_list_for_task]) if subtask_list_for_task else 0
    return max_subtask_ordno