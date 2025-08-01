from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists, user_authorized_subtask, tasklead_user_only, subtask_allocatedby_user_only, tasklead_or_allocby_user_only
from flask import jsonify, request, session

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.TaskTemplate import (TaskTemplate as TaskTemplate)
from task_trak.db.models.ProjectTransaction import (ProjectTransaction as ProjectTransaction)
from task_trak.db.models.TaskTransaction import (TaskTransaction as TaskTransaction)
from task_trak.db.models.SubTaskTransaction import (SubTaskTransaction as SubTaskTransaction)
from task_trak.db.models.AttachmentDetails import (AttachmentDetails as AttachmentDetails)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker

from task_trak.controllers.projectTemplateController import get_project_template_object, update_project_template_aprx_duration, get_project_template_aprx_duration_total, timedelta_to_days_hours_minutes
from task_trak.controllers.taskTemplateController import list_task_templates_all, task_template_with_subtask_templates, parse_duration
from task_trak.controllers.projectTxnController import get_project_object
from task_trak.controllers.taskTxnController import get_task_object
from task_trak.controllers.staffController import get_users_list
from task_trak.controllers.attachmentController import get_attachments, delete_attachments
from task_trak.controllers.userActivityController import createUserActivity

# utils import
from task_trak.common.utils import format_timedelta

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TaskStatus, e_Priority, e_SubTaskStatus, e_TranType, e_ActionType

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta
import math

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@login_required
@tasklead_or_allocby_user_only
def addNewSubTask(task_id):
    parent_task = get_task_object(task_id)
    if request.method == 'POST':
        if parent_task.Status not in [e_TaskStatus.Pending.idx, e_TaskStatus.Inprocess.idx]:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} is not in pending or in process state."}), 400
        subtask_data = request.get_json()
        try:
            subtask_add_status = add_subtask_object(subtask_data)
            if not subtask_add_status:
                return jsonify({"status":"error", "message":f"Task with the ID {subtask_data['TaskTranID']} is not found."}), 404
            elif subtask_add_status["status"]:
                return jsonify({"status":"success", "message":"Added SubTask successfully.", "data":subtask_add_status["subtask_info"]}), 201
            else:
                return jsonify({"status":"error", "message":f"Approx duration exceeding total duration of parent task by {subtask_add_status['exceeding_by']}."}), 400
        except Exception as e:
            app.logger.error(e)
            error_message = str(e.orig)
            if 'UNIQUE constraint failed: subtask_Transaction.Name' in error_message:
                return jsonify({"status":"error", "message":"Task Name already exists"}), 409
            elif 'UNIQUE constraint failed: subtask_Transaction.OrdNo' in error_message:
                return jsonify({"status":"error", "message":"Order Number already exists"}), 409
            elif 'UNIQUE constraint failed: subtask_Transaction.TaskTmplID, subtask_Transaction.Name' in error_message:
                return jsonify({"status":"error", "message":f"SubTask with Name {subtask_data['Name']} already exists for project."}), 409
            else:
                return jsonify({"status":"error", "message":f"Integrity error occurred"}), 500
    else: # Expecting a GET request to prepare for adding a new subtask
        parent_task_name = parent_task.Name
        last_ordno = get_max_ordno_task_txn(task_id)
        status_list, priority_list = enum_to_list(e_TaskStatus), enum_to_list(e_Priority)
        next_ordno = last_ordno + 1
        response_data = {
            "status": "success",
            "data": {
                "OrdNo": next_ordno,
                "task_name": parent_task_name,
                "priority_list": priority_list,
                "status_list": status_list
            }
        }
        return jsonify(response_data)

@login_required
@user_authorized_subtask
def editSubTask(subtask_id):
    subtask = get_subtask_object(subtask_id)
    if subtask is None:
        return jsonify({"status":"error", "message":f"SubTask with ID {subtask_id} not exists"}), 500
    if request.method == 'POST':
        subtask_data = request.get_json()
        try:
            response = edit_subtask_object(subtask, subtask_data)
            if not response[0]:
                return jsonify({"status":"error", "message":f"Approx duration exceeding total duration of parent task by {response[1]}."}), 400
            return response
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to edit SubTask."}), 500
    else: # Expecting a GET request to retrieve the subtask details
        subtask_data = subtask.to_dict()
        parent_task = get_task_object(subtask.TaskTranID)
        if parent_task is None:
            parent_task_name = ""
            parent_task_lead = ""
        else:
            parent_task_name = parent_task.Name
            parent_task_lead = parent_task.TaskLead
        subtask_data['parent_task_name'] = parent_task_name
        subtask_data['parent_task_lead'] = parent_task_lead
        subtask_data['attachments_no'] = len(get_attachments(subtask.ID, e_TranType.SubTaskTran.idx))
        return jsonify(subtask_data)
        
@login_required
def listSubTasks(task_id):
    if request.method == 'GET':
        try:
            subtask_list = list_subtasks(task_id)
            if subtask_list:
                return jsonify({"status": "success", "data": subtask_list}), 200
            else:
                return jsonify({"status":"success", "data":[]}), 200
        except ValueError as e:
            app.logger.error(e)
            return jsonify({"status": "error", "message": str(e)}), 404
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to list SubTasks."}), 500

@login_required
@user_authorized_subtask
def deleteSubTask(subtask_id):
    subtask = get_subtask_object(subtask_id)
    if subtask is None:
        return jsonify({"status":"error", "message":f"SubTask with ID {subtask_id} not exists"}), 500
    try:
        db_session = DBSession()
        # Delete attachments associated with the subtask
        # db_session.query(AttachmentDetails).filter(AttachmentDetails.TranMID == subtask_id, AttachmentDetails.TranType == e_TranType.SubTaskTran.idx).delete(synchronize_session=False)

        if not delete_attachments(subtask.ID, e_TranType.SubTaskTran.idx):
            return jsonify({"status":"error", "message":"Error occured while deleting the attachments."}), 500
        
        change_log = ""
        ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
        for column in subtask.__table__.columns:
            if column.name not in ignored_fields:
                change_log += f"{column.name}: {getattr(subtask, column.name)} => NaN\n"
        createUserActivity(ActionType=e_ActionType.DeleteRecord.idx, ActionDscr=e_ActionType.DeleteRecord.textval, EntityType=e_TranType.SubTaskTran.idx, EntityID=subtask.ID, ChangeLog=change_log)
        
        db_session.delete(subtask)
        db_session.commit()
        db_session.close()
        return jsonify({"status":"success", "message":f"SubTask and its attachments deleted successfully."}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to delete SubTask and its attachments."}), 500
        
def add_subtask_object(subtask_data):
    subtask = SubTaskTransaction()

    change_log = ""
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}

    if 'TaskTranID' in subtask_data.keys():
        parent_task = get_task_object(subtask_data['TaskTranID'])
        if not parent_task: #if parent_task not found with the TaskTranID passed in payload then don't proceeed ahead
            return False
        
    if "OrdNo" not in subtask_data.keys(): #if OrdNo not passed in payload then increment the max by 1; and if it's there then move ahead and set while setting other attributes
        parent_task = get_task_object(int(subtask_data["TaskTranID"]))
        if not parent_task:
            return False
        last_ordno = get_max_ordno_task_txn(subtask_data['TaskTranID'])
        change_log += f"OrdNo: NaN => {int(last_ordno) + 1}\n"
        subtask.OrdNo = int(last_ordno) + 1
    
    for key, value in subtask_data.items():
        if key == "Duration":
            is_exceeding_duration = exceeding_task_txn_aprx_duration(subtask_data, subtask_data['TaskTranID'])
            if is_exceeding_duration:
                return {"status": False, "subtask_ID": None, "exceeding_by":is_exceeding_duration}
            else:
                days, hours, minutes = parse_duration(float(value))
                subtask.Duration = timedelta(days=days, hours=hours, minutes=minutes)
                change_log += f"AprxDuration: NaN => {subtask.Duration}\n"
        elif key in ["StartDtTm", "EndDtTm", "ActualStDtTm", "ActualEndDtTm", "ClosureDtTm"]:
            date_value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").date()
            change_log += f"{key}: NaN => {value}\n"
            setattr(subtask, key, date_value)
        elif key in ["TaskTranID", "OrdNo"]:
            if value:
                change_log += f"{key}: NaN => {value}\n"
                setattr(subtask, key, int(value))
        else:
            old_value = getattr(subtask, key)
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
            # change_log += f"{key}: NaN => {value}\n"
            setattr(subtask, key, value)

    # set start date as current date and end date as start date + duration
    subtask.StartDtTm = datetime.now().replace(microsecond=0)
    subtask.EndDtTm = subtask.StartDtTm + subtask.Duration
    
    # set SubTaskLead same as Tasklead
    parent_task = get_task_object(subtask_data['TaskTranID'])
    subtask.SubTaskLead = parent_task.TaskLead

    subtask = set_models_attr.setCreatedInfo(subtask)
    subtask = set_models_attr.setSubTaskTxnOwnership(subtask)
    db_session = DBSession()
    db_session.add(subtask)
    db_session.commit()
    db_session.refresh(subtask)
    db_session.close()
    createUserActivity(ActionType=e_ActionType.AddRecord.idx, ActionDscr=e_ActionType.AddRecord.textval, EntityType=e_TranType.SubTaskTran.idx, EntityID=subtask.ID, ChangeLog=change_log)
    return {"status": True, "subtask_info":{"ID": subtask.ID, "ordNo": subtask.OrdNo}}

def edit_subtask_object(subtask, subtask_data):
    change_log = ""
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    for key, value in subtask_data.items():
        if key not in ['ParentTaskLead', 'SubTaskLead']:
            print(key, getattr(subtask, key), subtask_data[key])
            if getattr(subtask, key) != subtask_data[key]:
                if key == "Duration":
                    is_exceeding_duration = exceeding_task_txn_aprx_duration(subtask_data, subtask.TaskTranID, subtask)
                    if is_exceeding_duration:
                        return [False, is_exceeding_duration]
                    days, hours, minutes = parse_duration(float(value))
                    calculated_aprx_duration = timedelta(days=days, hours=hours, minutes=minutes)
                    if subtask.Duration != calculated_aprx_duration:
                        change_log += f"{key}: {subtask.Duration} => {calculated_aprx_duration}\n"
                        subtask.Duration = calculated_aprx_duration
                elif key in ["Name", "Dscr"]:
                    change_log += f"{key}: {getattr(subtask, key)} => {value}\n"
                    setattr(subtask, key, value)
                elif key in ["ActualStDtTm", "ActualEndDtTm", "ClosureDtTm"]:
                    date_value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").date()
                    change_log += f"{key}: {getattr(subtask, key)} => {value}\n"
                    setattr(subtask, key, date_value)
                elif key in ["StartDtTm", "EndDtTm"]:
                    if subtask.Status == e_TaskStatus.Pending.idx: #can be changed only when task is in pending state
                        change_log += f"{key}: {getattr(subtask, key)} => {value}\n"
                        setattr(subtask, key, datetime.strptime(value, '%Y-%m-%d %H:%M:%S'))
                    elif subtask.Status == e_TaskStatus.Inprocess.idx and key == "EndDtTm": #only end date can be changed when task in in_process
                        change_log += f"{key}: {getattr(subtask, key)} => {value}\n"
                        setattr(subtask, key, datetime.strptime(value, '%Y-%m-%d %H:%M:%S'))
                    else:
                        pass
                elif key in ["TaskTranID", "OrdNo"]:
                    if value:
                        if int(getattr(subtask, key)) != int(value):
                            change_log += f"{key}: {getattr(subtask, key)} => {value}\n"
                        setattr(subtask, key, int(value))
                else:
                    old_value = getattr(subtask, key)
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
                    # change_log += f"{key}: {getattr(subtask, key)} => {value}\n"
                    setattr(subtask, key, value)
            else:
                pass
            
    subtask = set_models_attr.setUpdatedInfo(subtask)
    db_session = DBSession()
    db_session.add(subtask)
    db_session.commit()
    db_session.refresh(subtask)
    if change_log and change_log != "":
        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.SubTaskTran.idx, EntityID=subtask.ID, ChangeLog=change_log)
    db_session.close()
    return jsonify({"status": "success", "message": "Updated SubTask successfully."}), 200

def list_subtasks(task_id):
    """
    List all task templates.

    :return: JSON response containing the list of task templates.
    """
    session = DBSession()
    # Check if the project template exists
    task = session.query(TaskTransaction).filter(TaskTransaction.ID == int(task_id)).one_or_none()
    if not task:
        session.close()
        raise ValueError(f"Task with ID {task_id} not found.")
    # Get task templates for the given project ID
    subtasks = session.query(SubTaskTransaction).filter(SubTaskTransaction.TaskTranID == int(task_id)).order_by(SubTaskTransaction.OrdNo.asc()).all()
    parent_task_name = task.Name
    subtasks_list = []
    for subtask in subtasks:
        subtask_data = subtask.to_dict()
        subtask_data['parent_task_name'] = parent_task_name
        subtasks_list.append(subtask_data)
    session.close()
    return subtasks_list


@login_required
@user_authorized_subtask
def doneSubTask(subtask_id):
    try:
        subtask = get_subtask_object(subtask_id)
        if subtask is None:
            return jsonify({"status":"error", "message":f"SubTask with ID {subtask_id} not exists."}), 500
        db_session = DBSession()
        subtask = db_session.query(SubTaskTransaction).filter(SubTaskTransaction.ID == subtask_id).first()
        changelog = []
        current_value = subtask.Status
        old_enum_value = (
            'NaN' if current_value in [None, '', ' '] else get_enum_info_by_idx(e_SubTaskStatus, int(current_value))
        )
        new_enum_value = get_enum_info_by_idx(e_SubTaskStatus, int(e_SubTaskStatus.Done.idx))
        if old_enum_value[1] != new_enum_value[1]:
            changelog.append(f"Status: {old_enum_value[0]} => {new_enum_value[0]}")
        for key in ["StartDtTm", "EndDtTm", "ActualStDtTm", "ActualEndDtTm"]:
            old_date = getattr(subtask, key)
            new_date = datetime.now()

            # Check if old_date is None or empty
            if old_date in [None, '', ' ']:
                old_date_display = "NaN"
            else:
                old_date_display = old_date.strftime('%d-%m-%y %I:%M %p')

            # Compare and log changes
            if old_date in [None, '', ' '] or new_date.replace(microsecond=0) != old_date.replace(microsecond=0):
                changelog.append(f"{key}: {old_date_display} => {new_date.strftime('%d-%m-%y %I:%M %p')}")
        # Log the user activity
        if changelog:
            createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.SubTaskTran.idx, EntityID=subtask.ID, ChangeLog="\n".join(changelog))

        subtask.Status = e_SubTaskStatus.Done.idx
        subtask.StartDtTm = datetime.now()
        subtask.EndDtTm = datetime.now()
        subtask.ActualStDtTm = datetime.now()
        subtask.ActualEndDtTm = datetime.now()
        subtask = set_models_attr.setUpdatedInfo(subtask)
        db_session.add(subtask)
        db_session.commit()
        db_session.close()
        return jsonify({"status": "success", "message": "SubTask has been done successfully."}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to done SubTask."}), 500

@login_required
@user_authorized_subtask
def incompleteSubTask(subtask_id):
    try:
        subtask = get_subtask_object(subtask_id)
        if subtask is None:
            return jsonify({"status":"error", "message":f"SubTask with ID {subtask_id} not exists."}), 500
        
        changelog = []
        current_value = subtask.Status
        old_enum_value = (
            'NaN' if current_value in [None, '', ' '] else get_enum_info_by_idx(e_SubTaskStatus, int(current_value))
        )
        new_enum_value = get_enum_info_by_idx(e_SubTaskStatus, int(e_SubTaskStatus.Pending.idx))
        if old_enum_value[1] != new_enum_value[1]:
            changelog.append(f"Status: {old_enum_value[0]} => {new_enum_value[0]}")
        for key in ["StartDtTm", "EndDtTm", "ActualStDtTm", "ActualEndDtTm"]:
            old_date = getattr(subtask, key)
            new_date = None  # new_date is explicitly set to None

            # Determine display for old_date
            if old_date in [None, '', ' ']:
                old_date_display = "NaN"
            else:
                old_date_display = old_date.strftime('%d-%m-%y %I:%M %p')

            # Determine display for new_date
            new_date_display = "NaN" if new_date in [None, '', ' '] else new_date.strftime('%d-%m-%y %I:%M %p')

            # Compare and log changes
            if old_date_display != new_date_display:
                changelog.append(f"{key}: {old_date_display} => {new_date_display}")

        # Log the user activity
        if changelog:
            createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.SubTaskTran.idx, EntityID=subtask.ID, ChangeLog="\n".join(changelog))

        subtask.Status = e_SubTaskStatus.Pending.idx
        subtask.StartDtTm = None
        subtask.EndDtTm = None
        subtask.ActualStDtTm = None
        subtask.ActualEndDtTm = None
        subtask = set_models_attr.setUpdatedInfo(subtask)
        db_session = DBSession()
        db_session.add(subtask)
        db_session.commit()
        db_session.close()
        return jsonify({"status": "success", "message": "SubTask has been marked incomplete successfully."}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to mark SubTask incomplete."}), 500

def get_subtask_object(subtask_id):
    session = DBSession()
    subtask = session.query(SubTaskTransaction).filter(SubTaskTransaction.ID == subtask_id).one_or_none()
    session.close()
    return subtask
    
def get_max_ordno_task_txn(parent_task_id):
    session = DBSession()
    # Ensure parent_task is within an active session
    parent_task = session.query(TaskTransaction).filter(TaskTransaction.ID == parent_task_id).one_or_none()
    # If parent_task is not found, handle appropriately
    if parent_task is None:
        session.close()
        return False
    subtask_list_for_task = parent_task.subtask_transaction
    session.close()
    max_subtask_ordno = max([task.OrdNo for task in subtask_list_for_task]) if subtask_list_for_task else 0
    return max_subtask_ordno

def exceeding_task_txn_aprx_duration(subtask_data, parent_task_id, current_subtask=None):
    """
    Check if adding a sub-task template will exceed the approximate duration of its parent task.

    :param subtask_data: Dictionary containing sub-task template information.
    :param parent_task_id: ID of the parent task template.
    :return: Formatted time difference if adding the sub-task template will exceed the parent task's approximate duration, False otherwise.
    """
    session = DBSession()
    parent_task = session.query(TaskTransaction).filter(TaskTransaction.ID == parent_task_id).one_or_none()
    if parent_task is None:
        session.close()
        return False
    if current_subtask is None:
        total_subtask_duration = sum([sub_task.Duration for sub_task in parent_task.subtask_transaction], timedelta())
    else:
        total_subtask_duration = sum([sub_task.Duration for sub_task in parent_task.subtask_transaction if sub_task.ID != current_subtask.ID], timedelta())
    
    subtask_duration_days, subtask_duration_hours, subtask_duration_minutes = parse_duration(float(subtask_data['Duration']))

    total_subtask_duration += timedelta(days=subtask_duration_days, hours=subtask_duration_hours, minutes=subtask_duration_minutes)
    session.close()

    parent_task_duration = parent_task.Duration
    if total_subtask_duration > parent_task_duration:
        return format_timedelta(total_subtask_duration - parent_task_duration)
    else:
        return False

def update_subtask_lead_allocby(task_id, lead, alloc_by):
    try:
        session = DBSession()
        subtask_list = session.query(SubTaskTransaction).filter(SubTaskTransaction.TaskTranID == task_id).filter(SubTaskTransaction.Status == e_TaskStatus.Pending.idx).all()
        for subtask in subtask_list:
            subtask.AllocBy = alloc_by
            subtask.SubTaskLead = lead
            session.add(subtask)
        session.commit()
        session.close()
        return True
    except Exception as e:
        app.logger.error(f"Error updating lead and allocation by for subtasks in task {task_id}: {e}")
        return False