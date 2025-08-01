from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists, user_authorized_task, tasklead_user_only, task_allocatedby_user_only
from flask import jsonify, request, session

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.TaskTemplate import (TaskTemplate as TaskTemplate)
from task_trak.db.models.ProjectTransaction import (ProjectTransaction as ProjectTransaction)
from task_trak.db.models.TaskTransaction import (TaskTransaction as TaskTransaction)
from task_trak.db.models.SubTaskTransaction import (SubTaskTransaction as SubTaskTransaction)
from task_trak.db.models.SubTaskTemplate import (SubTaskTemplate as SubTaskTemplate)
from task_trak.db.models.AttachmentDetails import (AttachmentDetails as AttachmentDetails)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker

from task_trak.controllers.projectTemplateController import get_project_template_object, update_project_template_aprx_duration, get_project_template_aprx_duration_total, timedelta_to_days_hours_minutes
from task_trak.controllers.taskTemplateController import list_task_templates_all, task_template_with_subtask_templates, parse_duration, get_task_template_object
from task_trak.controllers.staffController import get_users_list,get_user_object, get_user_by_code, get_all_admin_users
from task_trak.controllers.attachmentController import get_attachments, delete_attachments
from task_trak.controllers.communicationCenterController import generateNotification, get_notification_trantype_tranmid, clear_out_notifications_linkage
from task_trak.controllers.userActivityController import createUserActivity

# utils import
from task_trak.common.utils import format_timedelta

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TaskStatus, e_SubTaskStatus, e_Priority, e_TranType, e_NotificationStatus, e_ActionType

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta
import math

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@login_required
def addNewTask(task_template_id=None):
    from task_trak.controllers.projectTxnController import get_project_object
    if request.method == 'POST':
        task_data = request.get_json()
        try:
            task_info = add_task_object(task_data, task_template_id=task_template_id)
            if not task_info:
                return jsonify({"status":"error", "message":f"Project with ID {task_data['ProjTranID']} not found."}), 404
            elif "status" in task_info.keys() and task_info["status"] == "error":
                return jsonify({"status":"error", "message":task_info["message"], "data":task_info["data"]}), 404

            # send the notification of task created            
            loggedin_user = get_user_object(addNewTask.user_loginid)
            created_task = get_task_object(task_info['ID'])
            sent_to_users = [
                created_task.TaskLead,
                created_task.AllocBy,
                get_project_object(created_task.ProjTranID).ProjLead if get_project_object(created_task.ProjTranID) else None,
                get_project_object(created_task.ProjTranID).AllocBy if get_project_object(created_task.ProjTranID) else None,
                *[admin.Code for admin in get_all_admin_users() if admin.Code != loggedin_user.Code]
            ]
            sent_to_users = list(set(filter(None, [user for user in sent_to_users if user != loggedin_user.Code])))
            subject = f"{'New Project Task Assigned' if created_task.ProjTranID else 'New Task Assigned'} : {created_task.Name} : {created_task.StartDtTm.strftime('%d-%m-%y %I:%M %p')} : {created_task.EndDtTm.strftime('%d-%m-%y %I:%M %p')}"
            notification_status = generateNotification(From=loggedin_user.Code, To=sent_to_users, tranType=e_TranType.TaskTran.idx, tranMID=created_task.ID, Subject=subject, Description=created_task.Dscr)
            if not notification_status:
                return jsonify({"status":"error", "message":"Failed to send notification."}), 500

            return jsonify({"status":"success", "message":"Added Task successfully.", "data":task_info}), 201
        except Exception as e:
            app.logger.error(e)
            error_message = str(e.orig)
            if 'UNIQUE constraint failed: task_transaction.Name' in error_message:
                return jsonify({"status":"error", "message":"Task Name already exists"}), 409
            elif 'UNIQUE constraint failed: task_transaction.OrdNo' in error_message:
                return jsonify({"status":"error", "message":"Order Number already exists"}), 409
            elif 'UNIQUE constraint failed: task_transaction.ProjTmplID, task_transaction.Name' in error_message:
                return jsonify({"status":"error", "message":f"Task with Name {task_data['Name']} already exists for project."}), 409
            else:
                return jsonify({"status":"error", "message":f"Integrity error occurred"}), 500
    else:  # Handling GET request for prepare a new task
        from task_trak.controllers.projectTxnController import get_project_object
        project_id = request.args.get('project_id', None)
        users_list = [user.Code for user in get_users_list(addNewTask.user_type, current_user=addNewTask.user_loginid, bypass_check=True) if user.IsActive]
        status_list, priority_list = enum_to_list(e_TaskStatus), enum_to_list(e_Priority)
        data = {"users_list":users_list, "priority_list": priority_list, "status_list": status_list}
        if project_id:
            parent_project = get_project_object(int(project_id))
            max_ordno = get_max_ordno_project_txn(project_id)
            if max_ordno is False:
                return jsonify({"status":"error", "message":f"Project with ID {project_id} not found."}), 404
            else:
                data["parent_project_info"] = {
                    "ord_no": max_ordno+1,
                    "name": parent_project.Name,
                    "description": parent_project.Dscr,
                    "lead": parent_project.ProjLead
                }
                
        return jsonify({"status": "success", "data": data})

@login_required
@user_authorized_task
def editTask(task_id):
    from task_trak.controllers.projectTxnController import get_project_object
    loggedin_user = get_user_object(editTask.user_loginid)
    task = get_task_object(task_id)
    if task is None:
        return jsonify({"status":"error", "message":f"Task with ID {task_id} not exists"}), 500
    if request.method == 'POST':
        task_data = request.get_json()
        try:
            response = edit_task_object(task, task_data)
            return response
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to edit template."}), 500
    else:
        task_data = task.to_dict()
        parent_project = get_project_object(task.ProjTranID)
        if parent_project is None:
            parent_project_name = ""
            parent_project_description = ""
            parent_project_lead = ""
            parent_project_status = ""
        else:
            parent_project_name = parent_project.Name
            parent_project_description = parent_project.Dscr
            parent_project_lead = parent_project.ProjLead
            parent_project_status = parent_project.Status
        task_data['parent_project_name'] = parent_project_name
        task_data['parent_project_description'] = parent_project_description
        task_data['parent_project_lead'] = parent_project_lead
        task_data['parent_project_status'] = parent_project_status
        if task.ActualStDtTm:
            if task.ActualEndDtTm:
                actual_duration = task.ActualEndDtTm - task.ActualStDtTm
            else:
                actual_duration = datetime.now() - task.ActualStDtTm
            # Check if the actual duration is zero then use EndDtTm
            if actual_duration == timedelta(0):
                actual_duration = task.EndDtTm - task.ActualStDtTm
        else:
            actual_duration = timedelta(0)
        task_data['actual_duration'] = format_timedelta(actual_duration)
        task_data['planned_duration'] = format_timedelta(task.EndDtTm - task.StartDtTm) if task.StartDtTm and task.EndDtTm else format_timedelta(timedelta(0)) # difference between StartDtTm and EndDtTm
        task_data['attachments_no'] = len(get_attachments(task_id, e_TranType.TaskTran.idx)) #return the length of attachments associated with the task
        task_data['notifications'] = {
            "total": len([notification for notification in get_notification_trantype_tranmid(task.ID, e_TranType.TaskTran.idx) if notification.SentTo==loggedin_user.Code]), #return the length of notifications associated with the task
            "unread": len([notification for notification in get_notification_trantype_tranmid(task.ID, e_TranType.TaskTran.idx) if notification.SentTo==loggedin_user.Code and notification.Status==e_NotificationStatus.Pending.idx and notification.ReadDtTm==None]) #return the length of unread notifications associated with the task
        }

        return jsonify(task_data)
        
@login_required
def listTasks(project_id=None):
    if request.method == 'GET':
        try:
            current_user = get_user_object(listTasks.user_loginid)
            task_list = list_tasks(project_id, current_user)
            task_status_list = enum_to_list(e_TaskStatus)
            if task_list:
                return jsonify({"status": "success", "data": task_list, "task_status_list":task_status_list}), 200
            else:
                return jsonify({"status":"success", "data":[]}), 200
        except ValueError as e:
            app.logger.error(e)
            return jsonify({"status": "error", "message": str(e)}), 404
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to list tasks."}), 500

@task_allocatedby_user_only
def deleteTask(task_id):
    from task_trak.controllers.projectTxnController import get_project_object
    task = get_task_object(task_id)
    if task is None:
        return jsonify({"status":"error", "message":f"Task with ID {task_id} not exists"}), 500
    try:
        db_session = DBSession()
        # Delete attachments related to the task
        # db_session.query(AttachmentDetails).filter(AttachmentDetails.TranMID == task_id, AttachmentDetails.TranType == e_TranType.TaskTran.idx).delete(synchronize_session=False)

        if task.Status != e_TaskStatus.Pending.idx:
            return jsonify({"status":"error", "message":"Task is not in pending state."}), 400
        if not delete_attachments(task.ID, e_TranType.TaskTran.idx):
            return jsonify({"status":"error", "message":"Error occured while deleting the attachments."}), 500
        
        loggedin_user = get_user_object(deleteTask.user_loginid)
        sent_to_users = [
            task.TaskLead,
            task.AllocBy,
            get_project_object(task.ProjTranID).ProjLead if get_project_object(task.ProjTranID) else None,
            get_project_object(task.ProjTranID).AllocBy if get_project_object(task.ProjTranID) else None,
            *[admin.Code for admin in get_all_admin_users() if admin.Code != loggedin_user.Code]
        ]
        sent_to_users = list(set(filter(None, [user for user in sent_to_users if user != loggedin_user.Code])))
        subject_prefix = "Project Task Deleted : " if task.ProjTranID else "Task Deleted : "
        notification_status = generateNotification(From=loggedin_user.Code, To=sent_to_users, tranType=e_TranType.TaskTran.idx, tranMID=task.ID, Subject=f"{subject_prefix}{task.Name} : {task.StartDtTm.strftime('%d-%m-%y %I:%M %p')} : {task.EndDtTm.strftime('%d-%m-%y %I:%M %p')}", Description=task.Dscr)
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send notification."}), 500

        # Log the user activity
        changelog = []
        ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
        for column in TaskTransaction.__table__.columns:
            if column.name not in ignored_fields:
                old_value = getattr(task, column.name)
                changelog.append(f"{column.name}: {old_value}=> NaN")
        createUserActivity(ActionType=e_ActionType.DeleteRecord.idx, ActionDscr=e_ActionType.DeleteRecord.textval, EntityType=e_TranType.TaskTran.idx, EntityID=task.ID, ChangeLog="\n".join(changelog))
        
        db_session.delete(task)
        db_session.commit()
        db_session.close()
        clear_out_notifications_linkage(task.ID, e_TranType.TaskTran.idx)
        return jsonify({"status":"success", "message":f"Task with ID {task_id} and its attachments deleted successfully."}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to delete task and its attachments."}), 500
        
def add_task_object(task_data, task_template_id=None):
    from task_trak.controllers.projectTxnController import get_project_object
    task = TaskTransaction()
    changelog = ""
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    if "ProjTranID" not in task_data.keys():
        task.OrdNo = 1 # if stand-alone task then set OrdNo to 1
        changelog += "OrdNo: NaN => 1\n"
    else:
        if "OrdNo" not in task_data.keys():
            parent_project = get_project_object(int(task_data["ProjTranID"]))
            if not parent_project:
                return False
            last_ordno = get_max_ordno_project_txn(task_data['ProjTranID'])
            task.OrdNo = int(last_ordno) + 1
            changelog += f"OrdNo: NaN => {task.OrdNo}\n"
        else:
            pass
    
    for key, value in task_data.items():
        # Skip fields that should be ignored
        if key in ignored_fields:
            continue
        if key == "Duration":
            days, hours, minutes = parse_duration(float(value))
            task.Duration = timedelta(days=days, hours=hours, minutes=minutes)
            changelog += f"Duration: NaN => {task.Duration}\n"
        elif key in ["StartDtTm", "EndDtTm", "ActualStDtTm", "ActualEndDtTm", "ClosureDtTm"]:
            date_value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            setattr(task, key, date_value)
            changelog += f"{key}: NaN => {value}\n"
        elif key in ["ProjTranID", "OrdNo"]:
            if value:
                setattr(task, key, int(value))
                changelog += f"{key}: NaN => {value}\n"
        else:
            setattr(task, key, value)
            changelog += f"{key}: NaN => {value}\n"

    task = set_models_attr.setCreatedInfo(task)
    task = set_models_attr.setTaskTxnOwnership(task)
    db_session = DBSession()
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    db_session.close()
    
    # Log the user activity
    createUserActivity(ActionType=e_ActionType.AddRecord.idx, ActionDscr=e_ActionType.AddRecord.textval, EntityType=e_TranType.TaskTran.idx, EntityID=task.ID, ChangeLog=changelog)
            
    if task_template_id: #if task is being created from task_template then save sub-tasks and attachments associated with it from the task_template
        try:
            added_subtask_list = save_subtask_for_task(task, task_template_id)
            added_attachments_list = save_attachments_for_task(task.ID, task_template_id)
            if added_attachments_list:
                return {"ID": task.ID, "ordNo": task.OrdNo, "subtasks_list":added_subtask_list}
            else:
                app.logger.error(e)
                return {"status": "error", "message": str(e), "data":{"ID": task.ID, "ordNo": task.OrdNo}}    
        except ValueError as e:
            app.logger.error(e)
            return {"status": "error", "message": str(e), "data":{"ID": task.ID, "ordNo": task.OrdNo}}
    return {"ID": task.ID, "ordNo": task.OrdNo}

@login_required
def edit_task_object(task, task_data):
    from task_trak.controllers.subTaskTxnController import update_subtask_lead_allocby
    from task_trak.controllers.projectTxnController import get_project_object
    loggedin_user = get_user_object(edit_task_object.user_loginid)
    notification_description = []
    sent_to_users = list(set(filter(None, [
        task.TaskLead,
        task.AllocBy,
        get_project_object(task.ProjTranID).ProjLead if get_project_object(task.ProjTranID) else None,
        get_project_object(task.ProjTranID).AllocBy if get_project_object(task.ProjTranID) else None,
        *[admin.Code for admin in get_all_admin_users() if admin.Code != loggedin_user.Code]
    ])))
    
    old_task_name = task.Name
    
    changelog = []  # Initialize changelog for user activity
    for key, value in task_data.items():
        if key == "Duration":
            days, hours, minutes = parse_duration(float(value))
            new_duration = timedelta(days=days, hours=hours, minutes=minutes)
            if new_duration != task.Duration:
                notification_description.append(f"Duration Changed from {task.Duration} to {new_duration}")
                changelog.append(f"Duration: {task.Duration} => {new_duration}")
                task.Duration = new_duration
        elif key in ["Name", "Dscr"]:
            if task.Status == e_TaskStatus.Pending.idx:
                old_value = getattr(task, key)
                if old_value != value:
                    if key == 'Name':
                        notification_description.append(f"Name changed from {task.Name} to {value}")
                    changelog.append(f"{key}: {old_value} => {value}")
                    setattr(task, key, value)
        elif key in ["ActualStDtTm", "ActualEndDtTm", "ClosureDtTm"]:
            date_value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").date()
            old_value = getattr(task, key, None)
            if old_value.replace(microsecond=0) != date_value.replace(microsecond=0):
                changelog.append(f"{key}: {old_value} => {date_value}")
                setattr(task, key, date_value)
        elif key in ["StartDtTm", "EndDtTm"]:
            if task.Status == e_TaskStatus.Pending.idx or (task.Status == e_TaskStatus.Inprocess.idx and key == "EndDtTm"):
                new_date = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                old_date = getattr(task, key)
                if new_date.replace(microsecond=0) != old_date.replace(microsecond=0):
                    notification_description.append(f"{key} changed from {old_date.strftime('%d-%m-%y %I:%M %p')} to {new_date.strftime('%d-%m-%y %I:%M %p')}")
                    changelog.append(f"{key}: {old_date.strftime('%d-%m-%y %I:%M %p')} => {new_date.strftime('%d-%m-%y %I:%M %p')}")
                    setattr(task, key, new_date)
        elif key in ["ProjTranID", "OrdNo"]:
            if value:
                old_value = getattr(task, key)
                if old_value != int(value):
                    changelog.append(f"{key}: {old_value} => {int(value)}")
                    setattr(task, key, int(value))
        else:
            if key == 'TaskLead':
                if getattr(task, key) != value:
                    old_lead = getattr(task, key)
                    if not update_subtask_lead_allocby(task.ID, value, loggedin_user.Code):
                        return jsonify({"status":"error", "message":"Failed to change the subtask lead and allocated by."}), 500
                    project_prefix = "Project " if task.ProjTranID or get_project_object(task.ProjTranID) else ""
                    notification_description.append(f"{project_prefix}Task Lead changed from {old_lead} to {value}")
                    changelog.append(f"TaskLead: {old_lead} => {value}")  # Log for user activity
                    if task.AllocBy != loggedin_user.Code:
                        notification_description.append(f"Allocated By changed from {task.AllocBy} to {loggedin_user.Code}")
                        changelog.append(f"AllocBy: {task.AllocBy} => {loggedin_user.Code}")  # Log for user activity
                    task.AllocBy = loggedin_user.Code
                    sent_to_users.append(old_lead) #add old task lead to the sent_to_users list
                    sent_to_users.append(value) #add new task lead to the sent_to_users list
                    setattr(task, key, value)
            if key in ['Priority']:
                current_value = getattr(task, key)
                old_enum_value = (
                    'NaN' if current_value in [None, '', ' '] else get_enum_info_by_idx(e_Priority, int(current_value))
                )
                new_enum_value = get_enum_info_by_idx(e_Priority, int(value)) if value not in [None, '', ' '] else 'NaN'
                if old_enum_value[1] != new_enum_value[1]:
                    changelog.append(f"Priority: {old_enum_value[0]} => {new_enum_value[0]}")
                setattr(task, key, value)
            elif key != "AllocBy" and 'parent' not in key:
                old_value = getattr(task, key)
                if old_value != value:
                    setattr(task, key, value)
                    changelog.append(f"{key}: {old_value} => {value}")  # Log for user activity
    
    tasklead_change = [desc for desc in notification_description if "Task Lead changed" in desc or "Allocated By changed" in desc]
    other_changes = [desc for desc in notification_description if "Task Lead changed" not in desc and "Allocated By changed" not in desc]

    sent_to_users = list(set([user for user in sent_to_users if user != loggedin_user.Code]))

    if tasklead_change:
        notification_message = "\n".join(tasklead_change)
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=sent_to_users,
            tranType=e_TranType.TaskTran.idx,
            tranMID=task.ID,
            Subject=f"{'Project ' if task.ProjTranID else ''}Task Lead Changed : {old_task_name}",
            Description=notification_message
        )
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send task lead change notification."}), 500

    if other_changes:
        notification_message = "\n".join(other_changes)
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=sent_to_users,
            tranType=e_TranType.TaskTran.idx,
            tranMID=task.ID,
            Subject=f"{'Project ' if task.ProjTranID else ''}Task Details Changed : {old_task_name}",
            Description=notification_message
        )
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send task details change notification."}), 500

    task = set_models_attr.setUpdatedInfo(task)
    db_session = DBSession()
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    db_session.close()
    
    # Log the user activity
    if changelog:
        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.TaskTran.idx, EntityID=task.ID, ChangeLog="\n".join(changelog))
    
    return jsonify({"status": "success", "message": "Updated Task successfully.", "notifications_no": len(get_notification_trantype_tranmid(task.ID, e_TranType.TaskTran.idx))}), 200

@login_required
def list_tasks(project_id, current_user=None):
    """
    List all task templates.

    :return: JSON response containing the list of task templates.
    """
    session = DBSession()
    loggedin_user = get_user_object(list_tasks.user_loginid)
    if project_id:
        # Check if the project template exists
        project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == int(project_id)).one_or_none()
        if not project:
            session.close()
            raise ValueError(f"Project with ID {project_id} not found.")
        # Get task templates for the given project ID
        # if current_user:
        #     if current_user.Type in [e_UserType.SysAdm.idx, e_UserType.Admin.idx]:
        #         tasks = session.query(TaskTransaction).filter(TaskTransaction.ProjTranID == int(project_id)).order_by(TaskTransaction.OrdNo.asc()).all()
        #     else:
        #         tasks = session.query(TaskTransaction).filter(TaskTransaction.ProjTranID == int(project_id)).filter(or_(TaskTransaction.TaskLead == current_user.Code, TaskTransaction.AllocBy == current_user.Code)).order_by(TaskTransaction.OrdNo.asc()).all()
        # else:
        tasks = session.query(TaskTransaction).filter(TaskTransaction.ProjTranID == int(project_id)).order_by(TaskTransaction.OrdNo.asc()).all()
        parent_project_name = project.Name
    else:
        if current_user:
            if current_user.Type in [e_UserType.SysAdm.idx, e_UserType.Admin.idx]:
                tasks = session.query(TaskTransaction).order_by(TaskTransaction.StartDtTm.asc()).all()
            else:
                tasks = session.query(TaskTransaction).filter(or_(TaskTransaction.TaskLead == current_user.Code, TaskTransaction.AllocBy == current_user.Code)).order_by(TaskTransaction.StartDtTm.asc()).all()
        else:
            tasks = session.query(TaskTransaction).order_by(TaskTransaction.StartDtTm.asc()).all() #show standalone txns only
        parent_project_name = "" #if standalone task then don't set parent_project_name
    tasks_list = []
    for task in tasks:
        task_data = task.to_dict()
        # get the sub_tasks_templates associated with the task
        sorted_sub_tasks = sorted(task.subtask_transaction, key=lambda sub_task: sub_task.OrdNo)
        task_data['sub_tasks_list'] = [sub_task.to_dict() for sub_task in sorted_sub_tasks]
        task_data['parent_project_name'] = parent_project_name
        task_data['attachments_no'] = len(get_attachments(task.ID, e_TranType.TaskTran.idx))
        task_data['notifications'] = {
            "total": len([notification for notification in get_notification_trantype_tranmid(task.ID, e_TranType.TaskTran.idx) if notification.SentTo==loggedin_user.Code]), #return the length of notifications associated with the task
            "unread": len([notification for notification in get_notification_trantype_tranmid(task.ID, e_TranType.TaskTran.idx) if notification.SentTo==loggedin_user.Code and notification.Status==e_NotificationStatus.Pending.idx and notification.ReadDtTm==None]) #return the length of unread notifications associated with the task
        }
        #Difference between ActualStartDtTm and ActualEndDtTm if present or CurrentDtTm
        if task.ActualStDtTm:
            if task.ActualEndDtTm:
                actual_duration = task.ActualEndDtTm - task.ActualStDtTm
            else:
                actual_duration = datetime.now() - task.ActualStDtTm
            # Check if the actual duration is zero then use EndDtTm
            if actual_duration == timedelta(0):
                actual_duration = task.EndDtTm - task.ActualStDtTm
        else:
            actual_duration = timedelta(0)
        task_data['actual_duration'] = format_timedelta(actual_duration)
        task_data['planned_duration'] = format_timedelta(task.EndDtTm - task.StartDtTm) if task.StartDtTm and task.EndDtTm else format_timedelta(timedelta(0)) # difference between StartDtTm and EndDtTm
        tasks_list.append(task_data)
    session.close()
    return tasks_list

def list_all_tasks():
    session = DBSession()
    tasks = session.query(TaskTransaction).all()
    session.close()
    return tasks

def save_subtask_for_task(task_txn, task_template_id):
    session = DBSession()
    task_template = session.query(TaskTemplate).filter(TaskTemplate.ID == int(task_template_id)).one_or_none()
    if not task_template:
        session.close()
        raise ValueError(f"Task Template with ID {task_template_id} not found. Task added but, Failed to add SubTasks.")
    sub_tasks = task_template.subtask_templates
    for sub_task in sub_tasks:
        subtask_txn = SubTaskTransaction()
        subtask_txn.TaskTranID = task_txn.ID
        subtask_txn.OrdNo = sub_task.OrdNo
        subtask_txn.Name = sub_task.Name
        subtask_txn.Dscr = sub_task.Dscr
        subtask_txn.Duration = sub_task.AprxDuration
        subtask_txn.Other1 = sub_task.Other1
        subtask_txn.SubTaskLead = task_txn.TaskLead
        subtask_txn.AllocBy = task_txn.AllocBy
        # set start date as current date and end date as start date + duration
        subtask_txn.StartDtTm = datetime.now().replace(microsecond=0)
        subtask_txn.EndDtTm = subtask_txn.StartDtTm + subtask_txn.Duration
        subtask_txn = set_models_attr.setCreatedInfo(subtask_txn)
        session.add(subtask_txn)
        session.commit()
        session.refresh(subtask_txn)
        # save the attachments for subtask created from the subtask_template
        save_attachments_for_subtask(subtask_txn.ID, sub_task.ID)
    # session.refresh(task_txn)
    parent_task_name = task_txn.Name
    subtasks = session.query(SubTaskTransaction).filter(SubTaskTransaction.TaskTranID == int(task_txn.ID)).order_by(SubTaskTransaction.OrdNo.asc()).all()
    subtasks_list = []
    for subtask in subtasks:
        subtask_data = subtask.to_dict()
        subtask_data['parent_task_name'] = parent_task_name
        subtasks_list.append(subtask_data)
    session.close()
    return subtasks_list

def save_attachments_for_task(task_txn_id, task_template_id):
    try:
        session = DBSession()
        task_template = session.query(TaskTemplate).filter(TaskTemplate.ID == int(task_template_id)).one_or_none()
        if not task_template:
            session.close()
            raise ValueError(f"Task Template with ID {task_template_id} not found. Task added but, Failed to add Attachments.")
        attachments = session.query(AttachmentDetails).filter(AttachmentDetails.TranMID == int(task_template_id)).filter(AttachmentDetails.TranType == e_TranType.TaskTmpl.idx).all()
        for attachment in attachments:
            attachment_obj = AttachmentDetails()
            attachment_obj.TranType = e_TranType.TaskTran.idx
            attachment_obj.TranMID = int(task_txn_id)
            attachment_obj.AttchType = attachment.AttchType #as of now this will be fixed as we are not going to use it anywhere
            attachment_obj.DocNm = attachment.DocNm
            attachment_obj.Attchment = attachment.Attchment
            attachment_obj.FileNm = attachment.FileNm
            attachment_obj.Dscr = attachment.Dscr
            attachment_obj = set_models_attr.setCreatedInfo(attachment_obj)
            session.add(attachment_obj)
        session.commit()
        session.close()
        return True
    except Exception as e:
        app.logger.error(e)
        return False

def save_attachments_for_subtask(subtask_txn_id, subtask_template_id):
    try:
        session = DBSession()
        subtask_template = session.query(SubTaskTemplate).filter(SubTaskTemplate.ID == int(subtask_template_id)).one_or_none()
        if not subtask_template:
            session.close()
            raise ValueError(f"SubTask Template with ID {subtask_template_id} not found. Task added but, Failed to add SubTasks.")
        attachments = session.query(AttachmentDetails).filter(AttachmentDetails.TranMID == int(subtask_template_id)).filter(AttachmentDetails.TranType == e_TranType.SubTaskTmpl.idx).all()
        for attachment in attachments:
            attachment_obj = AttachmentDetails()
            attachment_obj.TranType = e_TranType.SubTaskTran.idx
            attachment_obj.TranMID = int(subtask_txn_id)
            attachment_obj.AttchType = attachment.AttchType #as of now this will be fixed as we are not going to use it anywhere
            attachment_obj.DocNm = attachment.DocNm
            attachment_obj.Attchment = attachment.Attchment
            attachment_obj.FileNm = attachment.FileNm
            attachment_obj.Dscr = attachment.Dscr
            attachment_obj = set_models_attr.setCreatedInfo(attachment_obj)
            session.add(attachment_obj)
        session.commit()
        session.close()
        return True
    except Exception as e:
        app.logger.error(e)
        return False

@login_required
@tasklead_user_only
def startTask(task_id):
    from task_trak.controllers.projectTxnController import updateProjectStatus, get_project_object
    loggedin_user = get_user_object(startTask.user_loginid)
    try:
        task = get_task_object(task_id)
        if task is None:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} not exists."}), 500
        if task.Status != e_TaskStatus.Pending.idx:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} is not in pending state."}), 400

        changelog = []
        current_value = task.Status
        old_enum_value = (
            'NaN' if current_value in [None, '', ' '] else get_enum_info_by_idx(e_TaskStatus, int(current_value))
        )
        new_enum_value = get_enum_info_by_idx(e_TaskStatus, int(e_TaskStatus.Inprocess.idx))
        if old_enum_value[1] != new_enum_value[1]:
            changelog.append(f"Status: {old_enum_value[0]} => {new_enum_value[0]}")
        for key in ["ActualStDtTm"]:
            old_date = getattr(task, key)
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
            createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.TaskTran.idx, EntityID=task.ID, ChangeLog="\n".join(changelog))
        
        task.Status = e_TaskStatus.Inprocess.idx
        task.ActualStDtTm = datetime.now().replace(microsecond=0)
        task = set_models_attr.setUpdatedInfo(task)
        db_session = DBSession()
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        db_session.close()
        
        # Update project status if task is associated with a project
        parent_project = None
        if task.ProjTranID:
            project_status = updateProjectStatus(task.ProjTranID)
            if project_status['status'] == 'error':
                return jsonify({"status": "error", "message": "Error occurred while updating project status"}), 500
            parent_project = get_project_object(task.ProjTranID)

        # Prepare notification recipients
        notification_to = [task.TaskLead, task.AllocBy]
        if parent_project:
            notification_to.extend([parent_project.ProjLead, parent_project.AllocBy])
            # Get all tasks associated with the parent project
            associated_tasks = get_task_txns_for_parent_project_txn(parent_project.ID)
            # Add task leads of tasks that are not in 'Done' or 'Cancelled' status
            notification_to.extend([t.TaskLead for t in associated_tasks if t.Status not in [e_TaskStatus.Done.idx, e_TaskStatus.Cancelled.idx] and t.ID != task.ID])
        notification_to.extend([admin.Code for admin in get_all_admin_users()])
        
        # Remove duplicates and exclude the sender (loggedin_user)
        notification_to = list(set(notification_to) - {loggedin_user.Code})

        # Prepare subject and description
        if parent_project:
            subject = f"Project Task Started : {task.Name}"
            description = f"Project Task Started : {task.TaskLead} : {task.Name}"
        else:
            subject = f"Task Started : {task.Name}"
            description = f"Task Started : {task.TaskLead} : {task.Name}"

        # Generate and send notification
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=notification_to,
            tranType=e_TranType.TaskTran.idx,
            tranMID=task.ID,
            Subject=subject,
            Description=description
        )

        if not notification_status:
            return jsonify({"status": "error", "message": "Failed to send notification."}), 500

        return jsonify({"status": "success", "message": "Task has been started successfully"}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to start task."}), 500

@login_required
@tasklead_user_only
def doneTask(task_id):
    from task_trak.controllers.projectTxnController import updateProjectStatus, get_project_object
    loggedin_user = get_user_object(doneTask.user_loginid)
    try:
        task = get_task_object(task_id)
        if task is None:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} not exists."}), 500
        if task.Status != e_TaskStatus.Inprocess.idx:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} is not in process."}), 400
        db_session = DBSession()
        task = db_session.query(TaskTransaction).filter(TaskTransaction.ID == task_id).first()
        
        # if atucalDtTime(current time) is greater than startDtTime then check for delay_reaon
        changelog = []
        if datetime.now() > task.EndDtTm:
            reason_data = request.get_json()
            if reason_data and 'DelayReason' in reason_data.keys():
                changelog.append(f"DelayReason: {task.DelayReason} => {reason_data['DelayReason']}")
                task.DelayReason = reason_data['DelayReason']
            else:
                return jsonify({"status":"error", "message":f"Delay Reason is required as Actual Start DateTime is more than Start DateTime."}), 400
        
        current_value = task.Status
        old_enum_value = (
            'NaN' if current_value in [None, '', ' '] else get_enum_info_by_idx(e_TaskStatus, int(current_value))
        )
        new_enum_value = get_enum_info_by_idx(e_TaskStatus, int(e_TaskStatus.PendReview.idx))
        if old_enum_value[1] != new_enum_value[1]:
            changelog.append(f"Status: {old_enum_value[0]} => {new_enum_value[0]}")
        for key in ["ActualEndDtTm"]:
            old_date = getattr(task, key)
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
            createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.TaskTran.idx, EntityID=task.ID, ChangeLog="\n".join(changelog))

        task.Status = e_TaskStatus.PendReview.idx
        task.ActualEndDtTm = datetime.now().replace(microsecond=0)
        task = set_models_attr.setUpdatedInfo(task)
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        db_session.close()
        # Prepare notification recipients
        notification_to = [
            task.TaskLead,
            task.AllocBy
        ]
        
        if task.ProjTranID:
            project = get_project_object(task.ProjTranID)
            notification_to.extend([
                project.ProjLead,
                project.AllocBy
            ])
        
        # Add all admin users
        notification_to.extend([admin.Code for admin in get_all_admin_users()])
        
        # Add all child task leads of the parent project (excluding done and cancelled tasks)
        if task.ProjTranID:
            associated_tasks = get_task_txns_for_parent_project_txn(task.ProjTranID)
            notification_to.extend([task.TaskLead for task in associated_tasks if task.Status not in [e_TaskStatus.Done.idx, e_TaskStatus.Cancelled.idx]])
        
        # Remove the logged-in user from the notification recipients
        notification_to = [user for user in notification_to if user != loggedin_user.Code]
        
        # Remove duplicates and None values
        notification_to = list(set(filter(None, notification_to)))

        # Prepare notification subject and description
        subject = f"Project Task for Review : {task.Name}" if task.ProjTranID else f"Task for Review : {task.Name}"
        description = f"{get_user_by_code(task.AllocBy).Name} to review task."
        if task.DelayReason:
            description += f"\nDelay Reason: {task.DelayReason}"

        # Generate and send notification
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=notification_to,
            tranType=e_TranType.TaskTran.idx,
            tranMID=task.ID,
            Subject=subject,
            Description=description
        )

        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send notification."}), 500
            
        return jsonify({"status": "success", "message": "Task has been done and submitted for review successfully."}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to done task."}), 500

@login_required
@tasklead_user_only
def checkSubtaskStatus(task_id):
    try:
        task = get_task_object(task_id)
        if task is None:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} not exists."}), 500
        db_session = DBSession()
        task = db_session.query(TaskTransaction).filter(TaskTransaction.ID == task_id).first()
        associated_subtasks_status = set([str(sub_task.Status) for sub_task in  task.subtask_transaction])

        # If ANY sub-task of the Task is not “Done” then message and stop process. 
        if associated_subtasks_status != set(str(e_SubTaskStatus.Done.idx)) and associated_subtasks_status:
            db_session.close()
            return jsonify({"status":"error", "message":f"Subtask pending. Can not proceed."}), 400
        db_session.close()
        return jsonify({"status": "success", "message": "All subtasks are done."}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to check subtask status."}), 500

@login_required
@task_allocatedby_user_only
def acceptTask(task_id):
    from task_trak.controllers.projectTxnController import updateProjectStatus, get_project_object
    loggedin_user = get_user_object(acceptTask.user_loginid)
    try:
        data = request.get_json()
        task = get_task_object(task_id)
        if task is None:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} not exists."}), 500
        if task.Status != e_TaskStatus.PendReview.idx:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} is not pending for review."}), 400

        if not data['ClosingComment']:
            return jsonify({"status":"error", "message":f"Closing Comment is required for accepting task."}), 400
        
        changelog = []
        changelog.append(f"ClosingComment: {task.ClosingComment} => {data['ClosingComment']}")
        changelog.append(f"Status: {get_enum_info_by_idx(e_TaskStatus, int(task.Status))[0]} => {get_enum_info_by_idx(e_TaskStatus, int(e_TaskStatus.Done.idx))[0]}")
        changelog.append(f"ClosureDtTm: {task.ClosureDtTm} => {datetime.now().strftime('%d-%m-%y %I:%M %p')}")

        # Log the user activity
        if changelog:
            createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.TaskTran.idx, EntityID=task.ID, ChangeLog="\n".join(changelog))

        task.ClosingComment = data['ClosingComment']
        task.Status = e_TaskStatus.Done.idx
        task.ClosureDtTm = datetime.now()
        task = set_models_attr.setTaskTxnClosureBy(task)
        task = set_models_attr.setUpdatedInfo(task)
        db_session = DBSession()
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        db_session.close()
        if task.ProjTranID:
            project_status = updateProjectStatus(task.ProjTranID)
            if project_status['status'] == 'error':
                return jsonify({"status": "error", "message": "Error occured while updating project status"}), 200
            else: #add notification for the project that project has been accepted
                parent_project = get_project_object(task.ProjTranID)
                associated_tasks = [task for task in get_task_txns_for_parent_project_txn(task.ProjTranID) if task.Status not in [e_TaskStatus.Done.idx, e_TaskStatus.Cancelled.idx]]
                notification_to = [task.TaskLead for task in associated_tasks if task.Status not in [e_TaskStatus.Done.idx, e_TaskStatus.Cancelled.idx]]
                notification_to.append(parent_project.ProjLead)
                notification_to.append(parent_project.AllocBy)
                notification_to.extend([admin.Code for admin in get_all_admin_users()])
                notification_to = list(set([user for user in notification_to if user != loggedin_user.Code]))
                notification_status = generateNotification(From=loggedin_user.Code, To=notification_to, tranType=e_TranType.TaskTran.idx, tranMID=task.ID, Subject=f"Project Task Accepted : {parent_project.Name}", Description=f"{loggedin_user.Code} user Accepted Task : {task.Name}\nComment: {task.ClosingComment}")
                if not notification_status:
                    return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        else: #add notification for the task that task has been accepted
            notification_to = list(set([task.TaskLead, task.AllocBy] + [user.Code for user in get_all_admin_users() if user.Code != loggedin_user.Code]))
            notification_status = generateNotification(
                From=loggedin_user.Code,
                To=notification_to,
                tranType=e_TranType.TaskTran.idx,
                tranMID=task.ID,
                Subject=f"Task Accepted : {task.Name}",
                Description=f"{loggedin_user.Code} Accepted the task completion.\nComment: {task.ClosingComment}"
            )
            if not notification_status:
                return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        return jsonify({"status": "success", "message": "Task has been accepted successfully."}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to accept task."}), 500

@login_required
@task_allocatedby_user_only
def rejectTask(task_id):
    from task_trak.controllers.projectTxnController import updateProjectStatus, get_project_object
    loggedin_user = get_user_object(rejectTask.user_loginid)
    try:
        task = get_task_object(task_id)
        if task is None:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} not exists."}), 500
        if task.Status != e_TaskStatus.PendReview.idx:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} is not pending for review."}), 400
        
        task_data = request.get_json()
        if "RejectReason" not in task_data.keys() or task_data["RejectReason"] == "":
            return jsonify({"status":"error", "message":f"Reject reason required."}), 400
        
        changelog = []
        changelog.append(f"RejectReason: {'NaN' if task.RejectReason in [None, '', ' '] else task.RejectReason} => {task_data['RejectReason']}")
        changelog.append(f"Status: {get_enum_info_by_idx(e_TaskStatus, int(task.Status))[0]} => {get_enum_info_by_idx(e_TaskStatus, int(e_TaskStatus.Inprocess.idx))[0]}")
        changelog.append(f"ActualEndDtTm: {task.ActualEndDtTm} => {datetime.now().strftime('%d-%m-%y %I:%M %p')}")

        # Log the user activity
        if changelog:
            createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.TaskTran.idx, EntityID=task.ID, ChangeLog="\n".join(changelog))

        task.RejectReason = task_data["RejectReason"]
        task.Status = e_TaskStatus.Inprocess.idx
        task.ActualEndDtTm = None
        task = set_models_attr.setUpdatedInfo(task)
        db_session = DBSession()
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        db_session.close()
        if task.ProjTranID:
            project_status = updateProjectStatus(task.ProjTranID)
            if project_status['status'] == 'error':
                return jsonify({"status": "error", "message": "Error occured while updating project status"}), 200
            else: #add notification for the project that project has been rejected
                parent_project = get_project_object(task.ProjTranID)
                notification_to = list(set([
                    task.TaskLead,
                    task.AllocBy,
                    parent_project.ProjLead,
                    parent_project.AllocBy,
                    *[admin.Code for admin in get_all_admin_users()]
                ]) - {loggedin_user.Code})
                notification_status = generateNotification(From=loggedin_user.Code, To=notification_to, tranType=e_TranType.TaskTran.idx, tranMID=task.ID, Subject=f"Project Task Rejected : {parent_project.Name}", Description=f"{loggedin_user.Code} user Rejected Task : {task.Name}\nReason: {task.RejectReason}")
                if not notification_status:
                    return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        else: #add notification for the task that task has been rejected
            notification_to = list(set([task.TaskLead, task.AllocBy] + [user.Code for user in get_all_admin_users() if user.Code != loggedin_user.Code]))
            notification_status = generateNotification(
                From=loggedin_user.Code,
                To=notification_to,
                tranType=e_TranType.TaskTran.idx,
                tranMID=task.ID,
                Subject=f"Task Rejected : {task.Name}",
                Description=f"{loggedin_user.Code} Rejected the task completion\nReason: {task.RejectReason}"
            )
            if not notification_status:
                return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        return jsonify({"status": "success", "message": "Task has been rejected and shifted to in process successfully."}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to reject task."}), 500

@login_required
@task_allocatedby_user_only
def cancelTask(task_id):
    from task_trak.controllers.projectTxnController import updateProjectStatus, get_project_object
    loggedin_user = get_user_object(cancelTask.user_loginid)
    try:
        task = get_task_object(task_id)
        if task is None:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} not exists."}), 500
        if task.Status not in [e_TaskStatus.Pending.idx, e_TaskStatus.Inprocess.idx]:
            return jsonify({"status":"error", "message":f"Task with ID {task_id} should be in pending or in process state."}), 400
        
        task_data = request.get_json()
        if "CancReason" not in task_data.keys() or task_data["CancReason"] == "":
            return jsonify({"status":"error", "message":f"Cancel reason required."}), 400
        
        changelog = []
        changelog.append(f"CancReason: {'NaN' if task.CancReason in [None, '', ' '] else task.CancReason} => {task_data['CancReason']}")
        changelog.append(f"Status: {get_enum_info_by_idx(e_TaskStatus, int(task.Status))[0]} => {get_enum_info_by_idx(e_TaskStatus, int(e_TaskStatus.Cancelled.idx))[0]}")
        changelog.append(f"ClosureDtTm: {'NaN' if task.ClosureDtTm in [None, '', ' '] else task.ClosureDtTm} => {datetime.now().strftime('%d-%m-%y %I:%M %p')}")

        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.TaskTran.idx, EntityID=task.ID, ChangeLog="\n".join(changelog))

        task.Status = e_TaskStatus.Cancelled.idx
        task.CancReason = task_data["CancReason"]
        task.ClosureDtTm = datetime.now()
        task = set_models_attr.setTaskTxnClosureBy(task)
        task = set_models_attr.setUpdatedInfo(task)
        db_session = DBSession()
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        db_session.close()
        if task.ProjTranID:
            project_status = updateProjectStatus(task.ProjTranID)
            if project_status['status'] == 'error':
                return jsonify({"status": "error", "message": "Error occured while updating project status"}), 200
            else: #add notification for the project that project has been cancelled
                parent_project = get_project_object(task.ProjTranID)
                associated_tasks = get_task_txns_for_parent_project_txn(task.ProjTranID)
                notification_to = [task.TaskLead for task in associated_tasks if task.Status not in [e_TaskStatus.Done.idx, e_TaskStatus.Cancelled.idx]]
                notification_to.append(parent_project.ProjLead)
                notification_to.extend([admin.Code for admin in get_all_admin_users()])
                notification_to = list(set(notification_to))
                # Remove the logged-in user from the notification recipients
                notification_to = [user for user in notification_to if user != loggedin_user.Code]
                notification_status = generateNotification(From=loggedin_user.Code, To=notification_to, tranType=e_TranType.TaskTran.idx, tranMID=task.ID, Subject=f"Project Task Cancelled : {parent_project.Name}", Description=f"{loggedin_user.Code} Cancelled Task : {task.Name}\nReason: {task.CancReason}")
                if not notification_status:
                    return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        else: #add notification for the task that task has been cancelled
            notification_to = list(set([task.TaskLead, task.AllocBy] + [user.Code for user in get_all_admin_users()]) - {loggedin_user.Code})
            notification_status = generateNotification(
                From=loggedin_user.Code,
                To=notification_to,
                tranType=e_TranType.TaskTran.idx,
                tranMID=task.ID,
                Subject=f"Task Cancelled : {task.Name}",
                Description=f"{loggedin_user.Code} Cancelled the task\nReason: {task.CancReason}"
            )
            if not notification_status:
                return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        return jsonify({"status": "success", "message": "Task has been cancelled successfully."}), 200
    except Exception as e:
        print(e)
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to cancel task."}), 500

def get_task_object(task_id):
    session = DBSession()
    task = session.query(TaskTransaction).filter(TaskTransaction.ID == task_id).one_or_none()
    session.close()
    return task
    
def get_max_ordno_project_txn(parent_project_id):
    session = DBSession()
    # Ensure parent_task is within an active session
    parent_project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == parent_project_id).one_or_none()
    # If parent_project is not found, handle appropriately
    if parent_project is None:
        session.close()
        return False
    task_list_for_project = parent_project.task_transactions
    session.close()
    max_task_ordno = max([task.OrdNo for task in task_list_for_project]) if task_list_for_project else 0
    return max_task_ordno

def add_project_rejection_child_task(project_id, project_lead, project_allocated_by, notification_text):
    from task_trak.controllers.projectTxnController import get_project_object
    project = get_project_object(project_id)
    try:
        task = TaskTransaction()
        task.ProjTranID = int(project_id)
        task.Name = f'Rejection Task from {project_allocated_by} to {project_lead}'
        task.Dscr = notification_text
        task.StartDtTm = datetime.now().replace(microsecond=0)
        task.Duration = timedelta(days=1)
        task.EndDtTm = task.StartDtTm + task.Duration
        task.Priority = e_Priority.High.idx
        task.AllocBy = project.AllocBy
        task.TaskLead = project.ProjLead
        task.OrdNo = 1
        session = DBSession()
        session.add(task)
        session.commit()
        session.close()
        return True
    except Exception as e:
        app.logger.error(e)
        return False
    
def get_task_txns_for_parent_project_txn(project_id):
    session = DBSession()
    parent_project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == int(project_id)).first()                
    associated_tasks = parent_project.task_transactions
    session.close()
    return associated_tasks