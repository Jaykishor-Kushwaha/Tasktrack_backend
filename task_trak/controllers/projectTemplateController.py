from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists
from flask import jsonify, request, session

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.ProjectTemplate import (ProjectTemplate as ProjectTemplate)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, DataError

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TranType, e_ActionType

from task_trak.controllers.attachmentController import get_attachments, delete_attachments
from task_trak.controllers.userActivityController import createUserActivity

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@admin_or_owner
def addNewProjectTemplate(user_type):
    """
    Adds a new project template to the database.

    :return: A JSON response indicating the status of the operation.
    :rtype: flask.Response
    """
    if request.method == 'POST':
        project_template_data = request.get_json()
        try:
            project_info = add_project_template_object(project_template_data)
            return jsonify({"status":"success", "messgae":"Added project template.", "data":project_info}), 201
        except IntegrityError as e:
            return jsonify({"status": "error", "message": f"Project with name {project_template_data['Name']} already exists."}), 500
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message": "Failed to add project template."}), 500

@admin_or_owner
def editProjectTemplate(user_type,project_template_id):
    """
    Edits an existing project template in the database.

    :param project_template_id: The ID of the project template to be edited.
    :type project_template_id: int
    :return: A JSON response indicating the status of the operation.
    :rtype: flask.Response
    """
    project_template = get_project_template_object(project_template_id)
    if request.method == 'POST':
        project_template_data = request.get_json()
        try:
            if project_template:
                response = edit_project_template_object(project_template, project_template_data)
                return response, 200
            else:
                return jsonify({"status":"error", "message": f"Project Template with ID {str(project_template_id)} not found."}), 404
        except IntegrityError as e:
            return jsonify({"status": "error", "message": f"Project with name {project_template_data['Name']} already exists."}), 409
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message": "Failed to edit project template."}), 500
    else:
        project_template_data = project_template.to_dict()
        project_template_data['total_aprx_duration'] = get_project_template_aprx_duration_total(int(project_template.ID))
        project_template_data['attachments_no'] = len(get_attachments(project_template.ID, e_TranType.ProjectTmpl.idx))
        return jsonify(project_template_data), 200
        
    
@admin_or_owner
def listProjectTemplates(user_type):
    """
    Lists all project templates from the database.

    :return: A JSON response with the list of project templates or an error message.
    :rtype: flask.Response
    """
    if request.method == 'GET':
        try:
            templates_list = list_project_templates()
            return jsonify({"status": "success", "data": templates_list}), 200
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message": "Failed to list project templates."}), 500
        
@admin_or_owner
def deleteProjectTemplate(user_type,project_template_id):
    """
    Deletes an existing project template from the database.

    :param project_template_id: The ID of the project template to be deleted.
    :type project_template_id: int
    :return: A JSON response indicating the status of the operation.
    :rtype: flask.Response
    """
    session = DBSession()
    try:
        # Query the project template
        project_template = session.query(ProjectTemplate).filter(ProjectTemplate.ID == int(project_template_id)).one_or_none()

        if project_template is None:
            return jsonify({"status":"error", "message":f"Project template with ID {project_template_id} not found."}), 404

        if not delete_attachments(project_template.ID, e_TranType.ProjectTmpl.idx):
            return jsonify({"status":"error", "message":"Error occured while deleting the attachments."}), 500
            
        # Deleting the project template will cascade delete its associated tasks and subtasks
        # Create a change log, excluding specific fields
        ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
        change_log = ""
        for column in project_template.__table__.columns:
            if column.name not in ignored_fields:
                change_log += f"{column.name}: {getattr(project_template, column.name)} => NaN\n"
        session.delete(project_template)
        # Log the user activity
        createUserActivity(ActionType=e_ActionType.DeleteRecord.idx, ActionDscr=e_ActionType.DeleteRecord.textval, EntityType=e_TranType.ProjectTmpl.idx, EntityID=project_template.ID, ChangeLog=change_log)
        session.commit()
        session.close()
        return jsonify({"status":"success", "message":"Project template and associated tasks deleted successfully."}), 200
    except Exception as e:
        session.rollback()
        print(e)
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to delete project template."}), 500
        
def add_project_template_object(project_template_data):
    """
    Adds a new project template object to the database and logs the activity.

    :param project_template_data: A dictionary containing the project template data.
    :type project_template_data: dict
    """
    project_template = ProjectTemplate()
    
    change_log = ""
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    for key, value in project_template_data.items():
        # Skip fields that should be ignored
        if key in ignored_fields:
            continue
        if key == "AprxDuration":
            setattr(project_template, key, timedelta(days=int(value)))
            change_log += f"AprxDuration: NaN => {value} days\n"
        else:
            setattr(project_template, key, value)
            change_log += f"{key}: NaN => {value}\n"
        
    project_template = set_models_attr.setCreatedInfo(project_template)
    db_session = DBSession()
    db_session.add(project_template)
    db_session.commit()
    db_session.refresh(project_template)
    db_session.close()
    
    # Log the user activity
    createUserActivity(ActionType=e_ActionType.AddRecord.idx, ActionDscr=e_ActionType.AddRecord.textval, EntityType=e_TranType.ProjectTmpl.idx, EntityID=project_template.ID, ChangeLog=change_log)
    
    return {"ID":project_template.ID}

def edit_project_template_object(selected_template, update_data):
    """
    Edits an existing project template object in the database.

    :param selected_template: The current project template object.
    :type selected_template: ProjectTemplate
    :param update_data: A dictionary containing the updated project template data.
    :type update_data: dict
    :return: A JSON response indicating the status of the operation.
    :rtype: flask.Response
    """
    change_log = ""
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    for key, value in update_data.items():
        if getattr(selected_template, key) != update_data[key]:
            # Skip fields that should be ignored
            if key in ignored_fields:
                continue
            if key == "AprxDuration":
                change_log += f"{key}: {getattr(selected_template, key)} => {value}\n"
                setattr(selected_template, key, timedelta(days=int(value)))
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
            pass #if no data change then nothing to do
    
    selected_template = set_models_attr.setUpdatedInfo(selected_template)
    db_session = DBSession()
    db_session.add(selected_template)
    db_session.commit()
    if change_log:
        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.ProjectTmpl.idx, EntityID=selected_template.ID, ChangeLog=change_log)
    db_session.close()
    return jsonify({"status":"success", "message":"Project template updated successfully."})

def get_project_template_object(selected_template_id):
    """
    Retrieves a project template object from the database.

    :param selected_template_id: The ID of the project template to retrieve.
    :type selected_template_id: int
    :return: The project template object or None if not found.
    :rtype: ProjectTemplate or None
    """
    session = DBSession()
    template = session.query(ProjectTemplate).filter(ProjectTemplate.ID == selected_template_id).one_or_none()
    session.close()
    return template

def update_project_template_aprx_duration(project_template):
    """
    Updates the approximate duration of a project template in the database.

    :param project_template: The project template object to update.
    :type project_template: ProjectTemplate
    """
    session = DBSession()
    session.add(project_template)
    session.commit()
    session.close()

def list_project_templates():
    """
    Lists all project templates from the database.

    :return: A JSON response with the list of project templates.
    :rtype: flask.Response
    """
    session = DBSession()
    project_templates = session.query(ProjectTemplate).order_by(func.lower(ProjectTemplate.Name).asc()).all()
    project_templates_list = []
    for project_template in project_templates:
        project_data = project_template.to_dict()
        # get the tasks_templates associated with the project_template
        sorted_tasks = sorted(project_template.task_templates, key=lambda task: task.OrdNo)
        project_data['tasks_list'] = [task.to_dict() for task in sorted_tasks]
        project_data['total_aprx_duration'] = get_project_template_aprx_duration_total(int(project_template.ID))
        project_templates_list.append(project_data)
    session.close()
    return project_templates_list
    
def get_project_template_aprx_duration_total(parent_project_template_id):
    """
    Get the total approximate duration of tasks for a given project template.

    :param parent_project_template_id: The ID of the parent project template.
    :return: The total approximate duration of tasks in days, including fractional days for hours and minutes.
    """
    session = DBSession()
    parent_project = session.query(ProjectTemplate).filter(ProjectTemplate.ID == parent_project_template_id).one_or_none()
    if parent_project is None:
        session.close()
        return False

    if parent_project.AprxDuration is None:
        return 0

    total_days = 0
    total_hours = 0
    total_minutes = 0

    for task in parent_project.task_templates:
        task_days, task_hours, task_minutes = timedelta_to_days_hours_minutes(task.AprxDuration)
        total_days += task_days
        total_hours += task_hours
        total_minutes += task_minutes

    if total_minutes >= 60:
        total_hours += total_minutes // 60
        total_minutes %= 60

    if total_hours >= 24:
        total_days += total_hours // 24
        total_hours %= 24

    session.close()
    return total_days + (total_hours / 24) + (total_minutes / 1440)

def timedelta_to_days_hours_minutes(td):
    total_seconds = int(td.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    return days, hours, minutes
