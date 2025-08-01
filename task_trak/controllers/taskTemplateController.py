from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists
from flask import jsonify, request, session

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.TaskTemplate import (TaskTemplate as TaskTemplate)
from task_trak.db.models.ProjectTemplate import (ProjectTemplate as ProjectTemplate)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker

from task_trak.controllers.projectTemplateController import get_project_template_object, update_project_template_aprx_duration, get_project_template_aprx_duration_total, timedelta_to_days_hours_minutes
from task_trak.controllers.attachmentController import get_attachments, delete_attachments
from task_trak.controllers.userActivityController import createUserActivity

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TranType, e_ActionType

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta
import math

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@admin_or_owner
def addNewTaskTemplate(user_type, project_template_id=None):
    """
    Add a new task template.

    :return: JSON response indicating the status of the operation.
    """
    if request.method == 'POST':
        task_template_data = request.get_json()
        try:
            task_info = add_task_template_object(task_template_data)
            if not task_info:
                return jsonify({"status":"error", "message":f"Project with ID {task_template_data['ProjTmplID']} not found."}), 404
            return jsonify({"status":"success", "message":"Added Task template successfully.", "data":task_info}), 201
        except Exception as e:
            app.logger.error(e)
            error_message = str(e.orig)
            if 'UNIQUE constraint failed: task_template.Name' in error_message:
                return jsonify({"status":"error", "message":"Task Name already exists"}), 409
            elif 'UNIQUE constraint failed: task_template.OrdNo' in error_message:
                return jsonify({"status":"error", "message":"Order Number already exists"}), 409
            elif 'UNIQUE constraint failed: task_template.ProjTmplID, task_template.Name' in error_message:
                return jsonify({"status":"error", "message":f"Task with Name {task_template_data['Name']} already exists for project template."}), 409
            else:
                return jsonify({"status":"error", "message":f"Integrity error occurred"}), 500
    else:
        project_template = get_project_template_object(project_template_id)
        if project_template:
            last_ordno = get_max_ordno_project(project_template_id)
            return jsonify({"status":"success", "data":last_ordno+1}), 200
        else:
            return jsonify({"status":"error", "message":f"Project Template with ID {project_template_id} doesn't exists."}), 200
            

@login_required
def editTaskTemplate(task_template_id):
    """
    Edit an existing task template.

    :param task_template_id: The ID of the task template to be edited.
    :return: JSON response indicating the status of the operation.
    """
    task_template = get_task_template_object(int(task_template_id))
    if task_template is None:
        return jsonify({"status":"error", "message":f"Task template with ID {task_template_id} not found."})
    if request.method == 'POST':
        task_template_data = request.get_json()
        try:
            response = edit_task_template_object(task_template, task_template_data)
            return response
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to edit template."}), 500
    else:
        task_template_data = task_template.to_dict()
        parent_project_template = get_project_template_object(task_template.ProjTmplID)
        if parent_project_template is None:
            parent_project_template_name = ""
        else:
            parent_project_template_name = parent_project_template.Name
        task_template_data['parent_project_template_name'] = parent_project_template_name
        task_template_data['attachments_no'] = len(get_attachments(task_template.ID, e_TranType.TaskTmpl.idx))
        return jsonify(task_template_data)
        
    
@login_required
def listTaskTemplates(project_id=None):
    """
    List all task templates.

    :return: JSON response containing the list of task templates.
    """
    if request.method == 'GET':
        try:
            task_list = list_task_templates(project_id)
            if task_list:
                return jsonify({"status": "success", "data": task_list}), 200
            else:
                return jsonify({"status":"success", "data":[]}), 200
        except ValueError as e:
            app.logger.error(e)
            return jsonify({"status": "error", "message": str(e)}), 404
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to list tasks."}), 500

@admin_or_owner
def deleteTaskTemplate(user_type, task_template_id):
    session = DBSession()
    try:
        # Query the task template
        task_template = session.query(TaskTemplate).filter(TaskTemplate.ID == int(task_template_id)).one_or_none()

        if task_template is None:
            return jsonify({"status":"error", "message":f"Task template with ID {task_template_id} not found."}), 404

        # Update the project template's AprxDuration by subtracting the task template's duration
        if task_template.ProjTmplID is not None:
            parent_project = get_project_template_object(int(task_template.ProjTmplID))
            if parent_project:
                # Convert timedelta to days, hours, and minutes
                parent_days, parent_hours, parent_minutes = timedelta_to_days_hours_minutes(parent_project.AprxDuration)
                task_days, task_hours, task_minutes = timedelta_to_days_hours_minutes(task_template.AprxDuration)

                total_minutes = parent_minutes - task_minutes
                total_hours = parent_hours - task_hours
                total_days = parent_days - task_days

                if total_minutes < 0:
                    total_hours -= 1
                    total_minutes += 60

                if total_hours < 0:
                    total_days -= 1
                    total_hours += 24

                # Set the updated duration back to the parent project
                parent_project.AprxDuration = timedelta(days=total_days, hours=total_hours, minutes=total_minutes)

                update_project_template_aprx_duration(parent_project)
            else:
                pass # Do nothing as no parent project has been found

        if not delete_attachments(task_template.ID, e_TranType.TaskTmpl.idx):
            return jsonify({"status":"error", "message":"Error occured while deleting the attachments."}), 500

        # Log the user activity
        changelog = []
        ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
        for column in TaskTemplate.__table__.columns:
            old_value = getattr(task_template, column.name)
            if column.name not in ignored_fields:
                changelog.append(f"{column.name}: {old_value} => NaN")
        createUserActivity(ActionType=e_ActionType.DeleteRecord.idx, ActionDscr=e_ActionType.DeleteRecord.textval, EntityType=e_TranType.TaskTmpl.idx, EntityID=task_template.ID, ChangeLog="\n".join(changelog))
        
        # Deleting the task template will cascade delete its associated subtasks
        session.delete(task_template)
        session.commit()
        session.close()


        return jsonify({"status":"success", "message":"Task template and associated sub-tasks deleted successfully."}), 200
    except Exception as e:
        session.rollback()
        print(e)
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to delete Task template."}), 500
    
@login_required
def listTaskTemplatesAll():
    try:
        task_templates_list = list_task_templates_all()
        return jsonify({"status": "success", "data": task_templates_list}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status": "error", "message": "Error in fetching Task Templates List."}), 500
    
@admin_or_owner
def getTaskTemplateWithSubTasks(user_type, task_template_id):
    try:
        task_template = task_template_with_subtask_templates(task_template_id)
        if task_template:
            return jsonify({"status": "success", "data": task_template}), 200
        else:
            return jsonify({"status": "error", "messgae": f"Task Template with ID {task_template_id} not found."}), 404
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status": "error", "message": "Error in fetching Task Template."}), 500
        
def add_task_template_object(task_template_data):
    """
    Add a task template object to the database.

    :param task_template_data: Dictionary containing task template information.
    """
    task_template = TaskTemplate()

    if 'ProjTmplID' not in task_template_data.keys() or task_template_data['ProjTmplID']=="":
        task_template.OrdNo = 1  # if stand-alone task then set OrdNo to 1
    else:
        if "OrdNo" not in task_template_data.keys():
            last_ordno = get_max_ordno_project(task_template_data['ProjTmplID'])
            task_template.OrdNo = int(last_ordno) + 1
            # if not standalone task then update parent project's approx duration
        else:
            pass
        parent_project_aprx_duration_total = get_project_template_aprx_duration_total(int(task_template_data['ProjTmplID']))
        parent_project_template = get_project_template_object(int(task_template_data['ProjTmplID']))
        if parent_project_template:
            pass
        else:
            return False
        parent_project_aprx_duration_total_days, parent_project_aprx_duration_hours, parent_project_aprx_duration_minutes = parse_duration(parent_project_aprx_duration_total)
        current_task_aprx_duration_days, current_task_aprx_duration_hours, current_task_aprx_duration_minutes = parse_duration(float(task_template_data['AprxDuration']))
        total_days = parent_project_aprx_duration_total_days + current_task_aprx_duration_days
        total_hours = parent_project_aprx_duration_hours + current_task_aprx_duration_hours
        total_minutes = parent_project_aprx_duration_minutes + current_task_aprx_duration_minutes

        if total_minutes >= 60:
            total_hours += total_minutes // 60
            total_minutes %= 60

        if total_hours >= 24:
            total_days += total_hours // 24
            total_hours %= 24

        parent_project_template.AprxDuration = timedelta(days=total_days, hours=total_hours, minutes=total_minutes)
        # parent_project_template.AprxDurationHours = total_hours
        # parent_project_template.AprxDurationMinutes = total_minutes
        update_project_template_aprx_duration(parent_project_template)
    
    for key, value in task_template_data.items():
        if key == "AprxDuration":
            days, hours, minutes = parse_duration(float(value))
            task_template.AprxDuration = timedelta(days=days, hours=hours, minutes=minutes)
        elif key in ["ProjTmplID", "OrdNo"]:
            if value:
                setattr(task_template, key, int(value))
        else:
            setattr(task_template, key, value)

    task_template = set_models_attr.setCreatedInfo(task_template)
    db_session = DBSession()
    db_session.add(task_template)
    db_session.commit()
    db_session.refresh(task_template)
    db_session.close()

    # Log the user activity
    changelog = []
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    for column in TaskTemplate.__table__.columns:
        old_value = getattr(task_template, column.name)
        if column.name not in ignored_fields:
            changelog.append(f"{column.name}: NaN => {old_value}")
    createUserActivity(ActionType=e_ActionType.AddRecord.idx, ActionDscr=e_ActionType.AddRecord.textval, EntityType=e_TranType.TaskTmpl.idx, EntityID=task_template.ID, ChangeLog="\n".join(changelog))

    return {"ID": task_template.ID, "ordNo": task_template.OrdNo}

def edit_task_template_object(selected_template, update_data):
    """
    Edit an existing task template object.

    :param selected_template: The task template object to be edited.
    :param update_data: Dictionary containing updated task template information.
    :return: JSON response indicating the status of the operation.
    """
    changelog = []
    for key, value in update_data.items():
        if getattr(selected_template, key) != update_data[key]:
            # db_session = DBSession()
            if key == "AprxDuration":
                # if "ProjTmplID" in update_data.keys(): # If task's AprxDuration is changed then update parent_project's AprxDuration
                if selected_template.ProjTmplID: # If task's AprxDuration is changed then update parent_project's AprxDuration
                    db_session = DBSession()
                    parent_project_template = db_session.query(ProjectTemplate).filter(ProjectTemplate.ID == int(selected_template.ProjTmplID)).one_or_none()
                    if parent_project_template:
                        sorted_tasks = parent_project_template.task_templates
                        db_session.close()
                        total_subtask_duration = sum([template.AprxDuration for template in sorted_tasks if template.ID != selected_template.ID], timedelta())
                        current_task_duration_days, current_task_duration_hours, current_task_duration_minutes = parse_duration(float(value))
                        total_subtask_duration += timedelta(days=current_task_duration_days, hours=current_task_duration_hours, minutes=current_task_duration_minutes)

                        total_days = total_subtask_duration.days
                        total_seconds = total_subtask_duration.seconds
                        total_hours = total_seconds // 3600
                        total_minutes = (total_seconds % 3600) // 60

                        parent_project_template.AprxDuration = timedelta(days=total_days, hours=total_hours, minutes=total_minutes)
                        update_project_template_aprx_duration(parent_project_template)

                        new_duration = timedelta(days=current_task_duration_days, hours=current_task_duration_hours, minutes=current_task_duration_minutes)
                        if new_duration != selected_template.AprxDuration:
                            changelog.append(f"AprxDuration: {selected_template.AprxDuration} => {new_duration}")
                        selected_template.AprxDuration = new_duration
                    else:
                        db_session.close()
                        # return jsonify({"status": "error", "message": "Parent project template not found."}), 404
                        pass
                else:
                    total_subtask_duration = get_task_template_aprx_duration_total(int(selected_template.ID))
                    total_subtask_duration_days = total_subtask_duration.days
                    total_subtask_duration_seconds = total_subtask_duration.seconds
                    total_subtask_duration_hours = total_subtask_duration_seconds // 3600
                    total_subtask_duration_minutes = (total_subtask_duration_seconds % 3600) // 60

                    current_task_duration_days, current_task_duration_hours, current_task_duration_minutes = parse_duration(float(value))
                    # print(timedelta(days=current_task_duration_days, hours=current_task_duration_hours, minutes=current_task_duration_minutes), total_subtask_duration)
                    if timedelta(days=current_task_duration_days, hours=current_task_duration_hours, minutes=current_task_duration_minutes) < total_subtask_duration:
                        return jsonify({"status": "error", "message": "Task Template Approx duration can't be less than total of Sub-task's Approx duration."}), 500
                    else:
                        new_duration = timedelta(days=current_task_duration_days, hours=current_task_duration_hours, minutes=current_task_duration_minutes)
                        if new_duration != selected_template.AprxDuration:
                            changelog.append(f"AprxDuration: {selected_template.AprxDuration} => {new_duration}")
                        selected_template.AprxDuration = new_duration
            elif key == "ProjTmplID":
                if getattr(selected_template, key):
                    changelog.append(f"{key}: {getattr(selected_template, key)} => {value}")
                    setattr(selected_template, key, int(value))
            else:
                # if key not in ['OrdNo']: # Don't let user change OrdNo
                #     setattr(selected_template, key, value)
                old_value = getattr(selected_template, key)
                if getattr(selected_template, key):
                    # changelog.append(f"{key}: {getattr(selected_template, key)} => {value}")
                    if old_value in [None, '', ' '] and value in [None, '', ' ']:
                        # Both current and new values are empty or None; no change, no log.
                        pass
                    elif old_value not in [None, '', ' '] and value not in [None, '', ' '] and old_value != value:
                        # Both current and new values have data, and they are different.
                        changelog.append(f"{key}: {old_value} => {value}")
                    elif old_value in [None, '', ' '] and value not in [None, '', ' ']:
                        # Current value is empty, new value has data.
                        changelog.append(f"{key}: NaN => {value}")
                    elif old_value not in [None, '', ' '] and value in [None, '', ' ']:
                        # Current value has data, new value is empty.
                        changelog.append(f"{key}: {old_value} => NaN")
                    setattr(selected_template, key, value)
        else:
            pass # If no data change then nothing to do

    selected_template = set_models_attr.setUpdatedInfo(selected_template)
    db_session = DBSession()
    db_session.add(selected_template)
    db_session.commit()
    if changelog:
        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.TaskTmpl.idx, EntityID=selected_template.ID, ChangeLog="\n".join(changelog))
    db_session.close()
    return jsonify({"status": "success", "message": "Updated Task template successfully."}), 200

def get_task_template_object(selected_template_id):
    """
    Retrieve a task template object by its ID.

    :param selected_template_id: The ID of the task template.
    :return: The task template object.
    """
    session = DBSession()
    template = session.query(TaskTemplate).filter(TaskTemplate.ID == selected_template_id).one_or_none()
    session.close()
    return template

def list_task_templates(project_id):
    """
    List all task templates.

    :return: JSON response containing the list of task templates.
    """
    session = DBSession()
    if project_id:
        # Check if the project template exists
        project_template = session.query(ProjectTemplate).filter(ProjectTemplate.ID == int(project_id)).one_or_none()
        if not project_template:
            session.close()
            raise ValueError(f"Project template with ID {project_id} not found.")
        # Get task templates for the given project ID
        task_templates = session.query(TaskTemplate).filter(TaskTemplate.ProjTmplID == int(project_id)).order_by(func.lower(TaskTemplate.OrdNo).asc()).all()
        parent_project_template_name = project_template.Name
    else:
        task_templates = session.query(TaskTemplate).filter(TaskTemplate.ProjTmplID == None).order_by(func.lower(TaskTemplate.Name).asc()).all() #show standalone templates only
        parent_project_template_name = "" #if standalone task then don't set parent_project_template_name
    task_templates_list = []
    for task_template in task_templates:
        task_data = task_template.to_dict()
        # get the sub_tasks_templates associated with the task_template
        sorted_sub_tasks = sorted(task_template.subtask_templates, key=lambda sub_task: sub_task.OrdNo)
        task_data['sub_tasks_list'] = [sub_task.to_dict() for sub_task in sorted_sub_tasks]
        task_data['parent_project_template_name'] = parent_project_template_name
        task_templates_list.append(task_data)
    session.close()
    return task_templates_list

def list_task_templates_all():
    """
    List all task templates.

    :return: JSON response containing the list of task templates.
    """
    session = DBSession()
    task_templates = session.query(TaskTemplate).order_by(func.lower(TaskTemplate.Name).asc()).all()
    task_templates_list_all = []
    for task_template in task_templates:
        if task_template.ProjTmplID:
            project_template = session.query(ProjectTemplate).filter(ProjectTemplate.ID == int(task_template.ProjTmplID)).one_or_none()
            parent_project_template_name = project_template.Name
        else:
            parent_project_template_name = "Standalone Task Template"
            
        task_data = task_template.to_dict()
        # get the sub_tasks_templates associated with the task_template
        sorted_sub_tasks = sorted(task_template.subtask_templates, key=lambda sub_task: sub_task.OrdNo)
        task_data['sub_tasks_list'] = [sub_task.to_dict() for sub_task in sorted_sub_tasks]
        task_data['parent_project_template_name'] = parent_project_template_name
        task_templates_list_all.append(task_data)
    session.close()
    return task_templates_list_all

def task_template_with_subtask_templates(task_template_id):
    session = DBSession()
    task_template = session.query(TaskTemplate).filter(TaskTemplate.ID == int(task_template_id)).one_or_none()
    if task_template:
        if task_template.ProjTmplID:
            project_template = session.query(ProjectTemplate).filter(ProjectTemplate.ID == int(task_template.ProjTmplID)).one_or_none()
            parent_project_template_name = project_template.Name
        else:
            parent_project_template_name = "Standalone Task Template"
        task_data = task_template.to_dict()
        # get the sub_tasks_templates associated with the task_template
        sorted_sub_tasks = sorted(task_template.subtask_templates, key=lambda sub_task: sub_task.OrdNo)
        task_data['sub_tasks_list'] = [sub_task.to_dict() for sub_task in sorted_sub_tasks]
        task_data['parent_project_template_name'] = parent_project_template_name
        session.close()
        return task_data
    else:
        session.close()
        return dict()
        
    
def get_max_ordno_project(parent_project_template_id):
    """
    Get the maximum order number of tasks for a given project template.

    :param parent_project_template_id: The ID of the parent project template.
    :return: The maximum order number of tasks.
    """
    session = DBSession()
    # Ensure parent_task is within an active session
    parent_project = session.query(ProjectTemplate).filter(ProjectTemplate.ID == parent_project_template_id).one_or_none()
    # If parent_project is not found, handle appropriately
    if parent_project is None:
        session.close()
        return False
    task_list_for_project = parent_project.task_templates
    session.close()
    max_task_ordno = max([task.OrdNo for task in task_list_for_project]) if task_list_for_project else 0
    return max_task_ordno

def get_task_template_aprx_duration_total(parent_task_template_id):
    session = DBSession()
    # Ensure parent_task is within an active session
    parent_task = session.query(TaskTemplate).filter(TaskTemplate.ID == parent_task_template_id).one_or_none()
    if parent_task is None:
        session.close()
        return False
    total_subtask_aprx_duration = sum([sub_task.AprxDuration for sub_task in parent_task.subtask_templates], timedelta())
    session.close()
    return total_subtask_aprx_duration

def parse_duration(duration):
    days, fractional_day = divmod(duration, 1)
    hours, fractional_hour = divmod(fractional_day * 24, 1)
    minutes = fractional_hour * 60    
    # Use rounding to avoid subtracting 1 minute due to floating-point precision issues
    return int(days), int(hours), round(minutes)

# def parse_duration(duration):
#     days, fractional_day = divmod(duration, 1)
#     hours = fractional_day * 24
#     hours, fractional_hour = divmod(hours, 1)
#     minutes = (fractional_hour * 60) if days > 0 else math.ceil(fractional_hour * 60)
#     return int(days), int(hours), int(minutes)