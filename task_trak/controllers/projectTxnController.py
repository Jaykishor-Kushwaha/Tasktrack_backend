from task_trak import app, admin_only, admin_or_owner_on_post, login_required, company_master_exists, system_admin_exists, user_authorized_project, project_allocby_or_admin
from flask import jsonify, request, session

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.ProjectTemplate import (ProjectTemplate as ProjectTemplate)
from task_trak.db.models.ProjectTransaction import (ProjectTransaction as ProjectTransaction)
from task_trak.db.models.TaskTransaction import (TaskTransaction as TaskTransaction)
from task_trak.db.models.AttachmentDetails import (AttachmentDetails as AttachmentDetails)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker

from task_trak.controllers.projectTemplateController import get_project_template_object, update_project_template_aprx_duration, get_project_template_aprx_duration_total, timedelta_to_days_hours_minutes
from task_trak.controllers.taskTemplateController import list_task_templates_all, task_template_with_subtask_templates, parse_duration
from task_trak.controllers.taskTxnController import save_attachments_for_task, save_subtask_for_task, add_project_rejection_child_task
from task_trak.controllers.staffController import get_users_list,get_user_object, get_all_admin_users
from task_trak.controllers.attachmentController import get_attachments, delete_attachments
from task_trak.controllers.communicationCenterController import generateNotification, get_notification_trantype_tranmid, clear_out_notifications_linkage
from task_trak.controllers.userActivityController import createUserActivity

# utils import
from task_trak.common.utils import format_timedelta

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_ProjStatus, e_TaskStatus, e_SubTaskStatus, e_Priority, e_TranType, e_NotificationStatus, e_ActionType

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)


@login_required
@admin_or_owner_on_post #TODO: make get of this controller avaialble to staff users as well
def addNewProject(user_type=None, project_template_id=None):
    if request.method == 'POST':
        project_data = request.get_json()
        try:
            project_info = add_project_object(project_data, project_template_id=project_template_id)
            if not project_info:
                return jsonify({"status":"error", "message":f"Project with ID {project_data['ProjTranID']} not found."}), 404
            elif "status" in project_info.keys() and project_info["status"] == "error":
                return jsonify({"status":"error", "message":project_info["message"], "data":project_info["data"]}), 404

            loggedin_user = get_user_object(addNewProject.user_loginid)
            created_project = get_project_object(project_info['ID'])
            subject = f"New Project Assigned : {created_project.Name} : {created_project.StartDtTm.strftime('%d-%m-%y %I:%M %p')} : {created_project.EndDtTm.strftime('%d-%m-%y %I:%M %p')}"
            sent_to_users = [
                created_project.ProjLead,
                *[admin.Code for admin in get_all_admin_users() if admin.Code != loggedin_user.Code]
            ]
            sent_to_users = list(set(filter(None, sent_to_users)))  # Remove duplicates and None values
            notification_status = generateNotification(From=loggedin_user.Code, To=sent_to_users, tranType=e_TranType.ProjectTran.idx, tranMID=created_project.ID, Subject=subject, Description=created_project.Dscr)
            if not notification_status:
                return jsonify({"status":"error", "message":"Failed to send notification."}), 500
            
            return jsonify({"status":"success", "message":"Added Project successfully.", "data":project_info}), 201
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":f"Error occured - {e}"}), 500

    else:  # Handling GET request for preparing a new task
        users_list = [user.Code for user in get_users_list(addNewProject.user_type, current_user=addNewProject.user_loginid) if user.IsActive]
        status_list, priority_list = enum_to_list(e_ProjStatus), enum_to_list(e_Priority)
        return jsonify({"status": "success", "data": {"users_list":users_list, "priority_list": priority_list, "status_list": status_list}})


@login_required
@user_authorized_project
def editProject(project_id):
    loggedin_user = get_user_object(editProject.user_loginid)
    project = get_project_object(project_id)
    if project is None:
        return jsonify({"status":"error", "message":f"Project with ID {project_id} not exists"}), 500
    if request.method == 'POST':
        project_data = request.get_json()
        try:
            response = edit_project_object(project, project_data)
            return response
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to edit Project."}), 500
    else:
        project_data = project.to_dict()
        if project.ActualStDtTm:
            if project.ActualEndDtTm:
                actual_duration = project.ActualEndDtTm - project.ActualStDtTm
            else:
                actual_duration = datetime.now() - project.ActualStDtTm
            # Check if the actual duration is zero then use EndDtTm
            if actual_duration == timedelta(0):
                actual_duration = project.EndDtTm - project.ActualStDtTm
        else:
            actual_duration = timedelta(0)
        project_data['actual_duration'] = format_timedelta(actual_duration)
        project_data['planned_duration'] = format_timedelta(project.EndDtTm - project.StartDtTm) # difference between StartDtTm and EndDtTm
        project_data['attachments_no'] = len(get_attachments(project_id, e_TranType.ProjectTran.idx)) #return the length of attachments associated with the task
        project_data['notifications_no'] = len(get_notification_trantype_tranmid(project_id, e_TranType.ProjectTran.idx)) #return the length of notifications associated with the task
        project_data['notifications'] = {
            "total": len([notification for notification in get_notification_trantype_tranmid(project.ID, e_TranType.ProjectTran.idx) if notification.SentTo==loggedin_user.Code]),
            "unread": len([notification for notification in get_notification_trantype_tranmid(project.ID, e_TranType.ProjectTran.idx) if notification.SentTo==loggedin_user.Code and notification.Status==e_NotificationStatus.Pending.idx and notification.ReadDtTm==None]) #return the length of unread notifications associated with the task
        }
        return jsonify(project_data)
    
@login_required
def listProjects():
    if request.method == 'GET':
        try:
            all = request.args.get('all', 'false').lower() in ['true', 'True']
            user_code = request.args.get('user_code', None)
            projects_list = list_projects(user_code, all_projects=all)
            return jsonify({"status":"success", "data":projects_list})
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to fetch projects."}), 500
    else:
        return jsonify({"status":"error", "message":"Method not supported."}), 405
    
@login_required
@project_allocby_or_admin
def acceptProject(project_id):
    loggedin_user = get_user_object(acceptProject.user_loginid)
    if request.method == 'POST':
        data = request.get_json()
        session = DBSession()
        project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == int(project_id)).one_or_none()
        if project is None:
            session.close()
            return jsonify({"status":"error", "message":f"Project with ID {project_id} not exists"}), 500
        if project.Status != e_ProjStatus.PendReview.idx:
            session.close()
            return jsonify({"status":"error", "message":f"Project with ID {project_id} is not in 'Pending Review' status."}), 400
        child_tasks = project.task_transactions
        task_status = [task.Status for task in child_tasks]
        
        if not all(status in [e_TaskStatus.Done.idx, e_TaskStatus.Cancelled.idx] for status in task_status):
            session.close()
            return jsonify({"status":"error", "message":"Project should have all its child tasks in 'Done' or 'Cancelled' status."}), 400
        project = set_models_attr.setProjectTxnAcptdBy(project)
        project = set_models_attr.setUpdatedInfo(project)
        project.AcptdDtTm = datetime.now()
        project.Status = e_ProjStatus.Done.idx
        project.ClosingComment = data['ClosingComment']
        project.ActualEndDtTm = max(task.ActualEndDtTm for task in child_tasks if task.ActualEndDtTm) #set this to the actual-end-dttm of last task marked accepted

        # as project is being accepted, set the closureBy and closureDtTm
        project = set_models_attr.setProjectTxnClosureBy(project)
        project.ClosureDtTm = datetime.now().replace(microsecond=0)

        # if project's actual datetime is exceeding the planned end date time then ask for the delay reason
        if project.ActualEndDtTm > project.EndDtTm:
            if 'DelayReason' in data:
                project.DelayReason = data['DelayReason']
            else:
                session.close()
                return jsonify({"status":"error", "message":"Delay reason is required for delayed projects."}), 400
        session.add(project)
        session.commit()
        
        notification_to = list(set([
            project.ProjLead,
            project.AllocBy,
            *[user.Code for user in get_all_admin_users() if user.Code != loggedin_user.Code]
        ]))
        notification_text = f"{loggedin_user.Code} Accepted the project completion.\nComment: {project.ClosingComment}"
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=notification_to,
            tranType=e_TranType.ProjectTran.idx,
            tranMID=project.ID,
            Subject=f"Project Accepted : {project.Name}",
            Description=notification_text
        )
        session.close()
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        
        return jsonify({"status": "success", "message": "Project has been accepted successfully."}), 200
    else:
        return jsonify({"status":"error", "message":"Method not supported."}), 405

@login_required
@project_allocby_or_admin
def rejectProject(project_id):
    loggedin_user = get_user_object(rejectProject.user_loginid)
    if request.method == 'POST':
        data = request.get_json()

        if not data or not data["RejectReason"]:
            return jsonify({"status":"error", "message":f"Couldn't found the reject reason."}), 400
            
        session = DBSession()
        project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == int(project_id)).one_or_none()
        session.close()
        if project is None:
            return jsonify({"status":"error", "message":f"Project with ID {project_id} not exists"}), 500
        if project.Status != e_ProjStatus.PendReview.idx:
            return jsonify({"status":"error", "message":f"Project with ID {project_id} is not in 'Pending Review' status."}), 400
        
        project = set_models_attr.setUpdatedInfo(project)
        project.ActualEndDtTm = None
        project.Status = e_ProjStatus.Inprocess.idx
        project.RejectReason = data["RejectReason"]
        
        # add notification for rejection of project
        notification_to = list(set([
            project.ProjLead,
            project.AllocBy,
            *[user.Code for user in get_all_admin_users() if user.Code != loggedin_user.Code]
        ]))
        notification_text = f"{loggedin_user.Code} Rejected the project completion.\nReason: {project.RejectReason}"
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=notification_to,
            tranType=e_TranType.ProjectTran.idx,
            tranMID=project.ID,
            Subject=f"Project Rejected : {project.Name}",
            Description=notification_text
        )
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        
        
        child_task_status = add_project_rejection_child_task(project_id, project.ProjLead, project.AllocBy, project.RejectReason)

        if not child_task_status:
            return jsonify({"status":"error","message":"Something went wrong while adding project rejection child task."}), 500
        
        session = DBSession()
        session.add(project)
        session.commit()
        session.close()
        
        return jsonify({"status": "success", "message": "Project has been rejected successfully."}), 200
    else:
        return jsonify({"status":"error","message":"Method not supported"}), 405


@login_required
@project_allocby_or_admin
def cancelProject(project_id):
    loggedin_user = get_user_object(cancelProject.user_loginid)
    if request.method == 'POST':
        data = request.get_json()
        session = DBSession()
        project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == int(project_id)).one_or_none()
        if project is None:
            return jsonify({"status":"error", "message":f"Project with ID {project_id} not exists"}), 500
        
        child_tasks = project.task_transactions
        task_status = [task.Status for task in child_tasks]
        if not all(status in [e_TaskStatus.Pending.idx, e_TaskStatus.Cancelled.idx, e_TaskStatus.Done.idx] for status in task_status):
            return jsonify({"status":"error", "message":"All child tasks must be either 'Pending', 'Cancelled' or 'Done."}), 400

        project = set_models_attr.setProjectTxnAcptdBy(project)
        project = set_models_attr.setProjectTxnClosureBy(project)
        project.ClosureDtTm = datetime.now().replace(microsecond=0)
        project = set_models_attr.setUpdatedInfo(project)
        
        changelog = []
        changelog.append(f"Status: {get_enum_info_by_idx(e_ProjStatus, int(project.Status))[0]} => {get_enum_info_by_idx(e_TaskStatus, int(e_ProjStatus.Cancelled.idx))[0]}")
        project.Status = e_ProjStatus.Cancelled.idx
        # set all the child task's status to cancelled which are in the pending state
        for task in child_tasks:
            if task.Status == e_TaskStatus.Pending.idx:
                task.Status = e_TaskStatus.Cancelled.idx
                task.CancReason = data['CancReason'] 
                task.ClosureBy = loggedin_user.Code
                task.ClosureDtTm = datetime.now().replace(microsecond=0)
                session.add(task)
        
        changelog.append(f"CancReason: {'NaN' if project.CancReason in [None, '', ' '] else project.CancReason} => {data['CancReason']}")
        changelog.append(f"AcptdDtTm: {'NaN' if project.AcptdDtTm is None else project.AcptdDtTm} => {datetime.now().strftime('%d-%m-%y %I:%M %p')}")
        
        project.CancReason = data['CancReason']
        project.AcptdDtTm = datetime.now().replace(microsecond=0)

        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.ProjectTran.idx, EntityID=project.ID, ChangeLog="\n".join(changelog))
        
        notification_to = list(set([
            project.ProjLead,
            project.AllocBy,
            *[admin.Code for admin in get_all_admin_users() if admin.Code != loggedin_user.Code]
        ]))
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=notification_to,
            tranType=e_TranType.ProjectTran.idx,
            tranMID=project.ID,
            Subject=f"Project Cancelled : {project.Name}",
            Description=f"{loggedin_user.Code} Cancelled the project.\nReason: {project.CancReason}"
        )

        session.add(project)
        session.commit()
        session.close()
        
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        
        return jsonify({"status": "success", "message": "Project has been Canacelled successfully."}), 200
    else:
        return jsonify({"status":"error","message":"Method not supported"}), 405
    

@login_required
@project_allocby_or_admin
def deleteProject(project_id):
    if request.method == 'POST':
        session = DBSession()
        project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == int(project_id)).one_or_none()
        if project is None:
            return jsonify({"status":"error", "message":f"Project with ID {project_id} not exists"}), 500
        
        if project.task_transactions:
            return jsonify({"status":"error", "message":"Cannot delete project with existing tasks."}), 400
        
        if not delete_attachments(project.ID, e_TranType.ProjectTran.idx):
            return jsonify({"status":"error", "message":"Error occured while deleting the attachments."}), 500
        
        loggedin_user = get_user_object(deleteProject.user_loginid)
        sent_to_users = list(set([
            project.ProjLead,
            project.AllocBy,
            *[admin.Code for admin in get_all_admin_users()]
        ]) - {loggedin_user.Code})
        subject = f"Project Deleted : {project.Name} : {project.StartDtTm.strftime('%d-%m-%y %I:%M %p')} : {project.EndDtTm.strftime('%d-%m-%y %I:%M %p')}"
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=sent_to_users,
            tranType=e_TranType.ProjectTran.idx,
            tranMID=project.ID,
            Subject=subject,
            Description=project.Dscr
        )
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send notification."}), 500

        # Log user activity
        changelog = []
        ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
        for column in ProjectTransaction.__table__.columns:
            if column.name not in ignored_fields:
                old_value = getattr(project, column.name)
                new_value = "NaN" if old_value is None else old_value
                changelog.append(f"{column.name}: {old_value} => {new_value}")
        createUserActivity(ActionType=e_ActionType.DeleteRecord.idx, ActionDscr=e_ActionType.DeleteRecord.textval, EntityType=e_TranType.ProjectTran.idx, EntityID=project.ID, ChangeLog="\n".join(changelog))
        
        # once user activity is logged then delete the project txn
        session.delete(project)
        session.commit()
        session.close()
        clear_out_notifications_linkage(project.ID, e_TranType.ProjectTran.idx)
        return jsonify({"status": "success", "message": "Project has been deleted successfully."}), 200
    else:
        return jsonify({"status":"error","message":"Method not supported"}), 405
    
def updateProjectStatus(project_id):
    try:
        session = DBSession()
        project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == int(project_id)).one_or_none()
        if project is None:
            return {"status":"error", "message":f"Project with ID {project_id} not exists"}
        
        child_tasks = project.task_transactions
        task_status = [task.Status for task in child_tasks]
        changedata = []
        if all(status in [e_TaskStatus.Pending.idx, e_TaskStatus.Cancelled.idx] for status in task_status):
            changedata.append(f"Status: {'NaN' if project.Status in [None, '', ' '] else get_enum_info_by_idx(e_ProjStatus, int(project.Status))} => {get_enum_info_by_idx(e_ProjStatus, int(e_ProjStatus.Pending.idx))}")
            project.Status = e_ProjStatus.Pending.idx
        elif e_TaskStatus.Inprocess.idx in task_status:
            if project.ActualStDtTm is None:
                changedata.append(f"ActualStDtTm: {'NaN' if project.ActualStDtTm is None else project.ActualStDtTm.strftime('%d-%m-%y %I:%M %p')} => {datetime.now().strftime('%d-%m-%y %I:%M %p')}")
                project.ActualStDtTm = datetime.now().replace(microsecond=0)
            changedata.append(f"Status: {'NaN' if project.Status in [None, '', ' '] else get_enum_info_by_idx(e_ProjStatus, int(project.Status))} => {get_enum_info_by_idx(e_ProjStatus, int(e_ProjStatus.Inprocess.idx))}")
            project.Status = e_ProjStatus.Inprocess.idx
        elif all(status in [e_TaskStatus.Done.idx, e_TaskStatus.Cancelled.idx] for status in task_status):
            changedata.append(f"Status: {'NaN' if project.Status in [None, '', ' '] else get_enum_info_by_idx(e_ProjStatus, int(project.Status))} => {get_enum_info_by_idx(e_ProjStatus, int(e_ProjStatus.PendReview.idx))}")
            project.Status = e_ProjStatus.PendReview.idx
        elif project.AcptdBy and project.AcptdDtTm:
            done_child_tasks = [task for task in child_tasks if task.Status == e_TaskStatus.Done.idx]
            if done_child_tasks:
                max_done_child_task = max(done_child_tasks, key=lambda task: task.ActualEndDtTm)
                changedata.append(f"ActualEndDtTm: {'NaN' if project.ActualEndDtTm is None else project.ActualEndDtTm.strftime('%d-%m-%y %I:%M %p')} => {max_done_child_task.ActualEndDtTm.strftime('%d-%m-%y %I:%M %p')}")
                project.ActualEndDtTm = max_done_child_task.ActualEndDtTm
            changedata.append(f"Status: {'NaN' if project.Status in [None, '', ' '] else get_enum_info_by_idx(e_ProjStatus, int(project.Status))} => {get_enum_info_by_idx(e_ProjStatus, int(e_ProjStatus.Done.idx))}")
            changedata.append(f"ClosureDtTm: {'NaN' if project.ClosureDtTm is None else project.ClosureDtTm.strftime('%d-%m-%y %I:%M %p')} => {datetime.now().strftime('%d-%m-%y %I:%M %p')}")
            project.Status = e_ProjStatus.Done.idx
            project = set_models_attr.setProjectTxnClosureBy(project)
            project.ClosureDtTm = datetime.now().replace(microsecond=0)
        elif project.CancReason not in ['', None]:
            changedata.append(f"Status: {'NaN' if project.Status in [None, '', ' '] else get_enum_info_by_idx(e_ProjStatus, int(project.Status))} => {get_enum_info_by_idx(e_ProjStatus, int(e_ProjStatus.Cancelled.idx))}")
            project.Status = e_ProjStatus.Cancelled.idx
            project = set_models_attr.setProjectTxnClosureBy(project)
        else:
            return {"status": "success", "message": "Project is upto date"}

        if changedata:
            createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.ProjectTran.idx, EntityID=project_id, ChangeLog="\n".join(changedata))

        session.add(project)
        session.commit()
        session.close()
        return {"status": "success", "message": "Project status has been updated successfully."}
    except Exception as e:
        app.logger.error(e)
        return {"status":"error", "message":f'Error occured while updating project status - {str(e)}'}
        
# Model functions    

def add_project_object(project_data, project_template_id=None):
    project = ProjectTransaction()
    
    changelog = []
    # Fields to ignore when generating the changelog
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    for key, value in project_data.items():
        if key in ignored_fields:
            continue
        if key == "Duration":
            days, hours, minutes = parse_duration(float(value))
            project.Duration = timedelta(days=days, hours=hours, minutes=minutes)
            changelog.append(f"{key}: NaN => {project.Duration}")
        elif key in ["StartDtTm", "EndDtTm", "ActualStDtTm", "ActualEndDtTm"]:
            date_value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            setattr(project, key, date_value)
            changelog.append(f"{key}: NaN => {date_value}")
        else:
            setattr(project, key, value)
            changelog.append(f"{key}: NaN => {value}")

    project = set_models_attr.setCreatedInfo(project)
    # project = set_models_attr.setProjectTxnOwnership(project)
    db_session = DBSession()
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    db_session.close()
            
    if project_template_id: #if project is being created from project_template then save tasks + sub-tasks and attachments associated with it from the project_template
        try:
            added_attachments = save_attachments_for_project(project.ID, project_template_id)
            added_task_list = save_task_for_project(project, project_template_id)
            if added_task_list and added_attachments:
                createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.ProjectTran.idx, EntityID=project.ID, ChangeLog="\n".join(changelog))
                return {"ID": project.ID}
            else:
                return {"status": "error", "message": "Error occured while adding attachment for project or adding task for project", "data":{"ID": project.ID}}
        except ValueError as e:
            app.logger.error(e)
            return {"status": "error", "message": str(e), "data":{"ID": project.ID}}
    return {"ID": project.ID}

@login_required
def save_task_for_project(project_txn, project_template_id):
    try:
        session = DBSession()
        project_template = session.query(ProjectTemplate).filter(ProjectTemplate.ID == int(project_template_id)).one_or_none()
        if not project_template:
            session.close()
            raise ValueError(f"Project Template with ID {project_template_id} not found. Project added but, Failed to add Tasks.")
        tasks = project_template.task_templates
        for task in tasks:
            task_txn = TaskTransaction()
            task_txn.ProjTranID = project_txn.ID
            task_txn.OrdNo = task.OrdNo
            task_txn.Name = task.Name
            task_txn.Dscr = task.Dscr
            task_txn.Duration = task.AprxDuration
            task_txn.StartDtTm = datetime.now() #based on the duraion present in task-template of a parent project template, calculate the start date & end date
            task_txn.EndDtTm = task_txn.StartDtTm + task_txn.Duration
            task_txn.Other1 = task.Other1
            task_txn.TaskLead = project_txn.ProjLead
            task_txn.AllocBy = project_txn.AllocBy
            task_txn = set_models_attr.setCreatedInfo(task_txn)
            session.add(task_txn)
            session.commit()
            session.refresh(task_txn)
            
            # save the attachments for task created from the task_template
            save_attachments_for_task(task_txn.ID, task.ID)
            # save subtask for task created from task_template
            save_subtask_for_task(task_txn, task.ID)
            
            # Send notification for the new added task
            loggedin_user = get_user_object(save_task_for_project.user_loginid)
            sent_to_users = [
                task_txn.TaskLead,
                project_txn.ProjLead if project_txn.ProjLead != loggedin_user.Code else None,
                project_txn.AllocBy if project_txn.AllocBy != loggedin_user.Code else None,
                *[admin.Code for admin in get_all_admin_users() if admin.Code != loggedin_user.Code]
            ]
            sent_to_users = list(set(filter(None, [user for user in sent_to_users if user != loggedin_user.Code])))
            subject = f"New Task Assigned : {task_txn.Name} : {task_txn.StartDtTm.strftime('%d-%m-%y %I:%M %p')} : {task_txn.EndDtTm.strftime('%d-%m-%y %I:%M %p')}"
            notification_status = generateNotification(From=loggedin_user.Code, To=sent_to_users, tranType=e_TranType.TaskTran.idx, tranMID=task_txn.ID, Subject=subject, Description=task_txn.Dscr)
            if not notification_status:
                return jsonify({"status":"error", "message":"Failed to send notification."}), 500
                
        session.close()
        return True
    except Exception as e:
        app.logger.error(e)
        return False
        
@login_required
def edit_project_object(project, project_data):
    from task_trak.controllers.staffController import get_users_list, get_user_object, get_user_by_code
    loggedin_user = get_user_object(edit_project_object.user_loginid)
    changes = []
    old_proj_lead = project.ProjLead
    new_proj_lead = project_data.get('ProjLead', old_proj_lead)
    old_allocated_by = project.AllocBy
    updated_fields = []
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    for key, value in project_data.items():
        # Skip ignored fields
        if key in ignored_fields:
            continue
        if key == "Duration":
            if project.Status == e_ProjStatus.Pending.idx:
                days, hours, minutes = parse_duration(float(value))
                new_duration = timedelta(days=days, hours=hours, minutes=minutes)
                if new_duration != project.Duration:
                    updated_fields.append(f"Approx Days: {project.Duration} => {new_duration}")
                    project.Duration = new_duration
        elif key in ["Name", "Dscr"]:
            if project.Status == e_ProjStatus.Pending.idx:
                if getattr(project, key) != value:
                    updated_fields.append(f"{key}: {getattr(project, key)} => {value}")
                    setattr(project, key, value)
        elif key in ["ActualStDtTm", "ActualEndDtTm", "AcptdDtTm"]:
            date_value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            setattr(project, key, date_value)
            if date_value.replace(microsecond=0) != getattr(project, key).replace(microsecond=0):
                updated_fields.append(f"{key}: {getattr(project, key)} => {date_value}")
            updated_fields.append(f"{key}: {getattr(project, key)} => {date_value}")
        elif key in ["StartDtTm", "EndDtTm"]:
            if project.Status == e_ProjStatus.Pending.idx or (project.Status == e_ProjStatus.Inprocess.idx and key == "EndDtTm"):
                new_date = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                if new_date.replace(microsecond=0) != getattr(project, key).replace(microsecond=0):
                    updated_fields.append(f"{key[:-4]} Date: {getattr(project, key).strftime('%d-%m-%y %I:%M %p')} => {new_date.strftime('%d-%m-%y %I:%M %p')}")
                    setattr(project, key, new_date)
        elif key == 'ProjLead':
            if old_proj_lead != value:
                project.AllocBy = loggedin_user.Code
                setattr(project, key, value)
                updated_fields.append(f"ProjLead: {old_proj_lead} => {value}")
        elif key in ['Priority']:
            current_value = getattr(project, key)
            old_enum_value = (
                'NaN' if current_value in [None, '', ' '] else get_enum_info_by_idx(e_Priority, int(current_value))
            )
            new_enum_value = get_enum_info_by_idx(e_Priority, int(value)) if value not in [None, '', ' '] else 'NaN'
            if old_enum_value[1] != new_enum_value[1]:
                updated_fields.append(f"Priority: {old_enum_value[0]} => {new_enum_value[0]}")
            setattr(project, key, value)
        elif key != "AllocBy":
            if getattr(project, key) != value:
                updated_fields.append(f"{key}: {getattr(project, key)} => {value}")
                setattr(project, key, value)

    project = set_models_attr.setUpdatedInfo(project)
    db_session = DBSession()
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    db_session.close()

    # Log the user activity
    if updated_fields:
        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.ProjectTran.idx, EntityID=project.ID, ChangeLog="\n".join(updated_fields))

    # Send notification for project lead change
    if old_proj_lead != new_proj_lead:
        notification_to = [old_proj_lead, new_proj_lead]
        notification_to.extend([admin.Code for admin in get_all_admin_users() if admin.Code != loggedin_user.Code])
        notification_to = list(set(notification_to) - {loggedin_user.Code})
        
        description = f"Project Lead changed from {get_user_by_code(old_proj_lead).Name} to {get_user_by_code(new_proj_lead).Name}\nProject Allocated By changed from {old_allocated_by} to {get_user_by_code(loggedin_user.Code).Name}"
        
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=notification_to,
            tranType=e_TranType.ProjectTran.idx,
            tranMID=project.ID,
            Subject=f"Project Lead Changed : {project.Name}",
            Description=description
        )
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send notification for project lead change."}), 500

    # Send notification for other changes
    if updated_fields:
        notification_to = [project.ProjLead]
        notification_to.extend([admin.Code for admin in get_all_admin_users() if admin.Code != loggedin_user.Code])
        notification_to = list(set(notification_to) - {loggedin_user.Code})
        
        description = "\n".join(updated_fields)
        
        notification_status = generateNotification(
            From=loggedin_user.Code,
            To=notification_to,
            tranType=e_TranType.ProjectTran.idx,
            tranMID=project.ID,
            Subject=f"Project Details Changed : {project_data.get('Name', project.Name)}",
            Description=description
        )
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send notification for project changes."}), 500
            
    project = set_models_attr.setUpdatedInfo(project)
    db_session = DBSession()
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    db_session.close()
    return jsonify({"status": "success", "message": "Updated Project successfully."}), 200

@login_required
def list_projects(user_code, all_projects=False):
    loggedin_user = get_user_object(list_projects.user_loginid)
    session = DBSession()

    if loggedin_user.Type == e_UserType.Staff.idx:
        # Fetch all projects where the logged-in user is ProjLead, AllocBy, or TaskLead of any task, and sort by Start Date
        projects = session.query(ProjectTransaction).filter(
            (ProjectTransaction.ProjLead == loggedin_user.Code) |  # Logged-in user is ProjLead
            (ProjectTransaction.AllocBy == loggedin_user.Code) |  # Logged-in user allocated the project
            ProjectTransaction.task_transactions.any(TaskTransaction.TaskLead == loggedin_user.Code) |  # Logged-in user is TaskLead of any task
            ProjectTransaction.task_transactions.any(TaskTransaction.AllocBy == loggedin_user.Code)
        ).order_by(ProjectTransaction.StartDtTm.asc()).all()
    else:
        if all_projects:
            # Fetch all projects and sort by Start Date in ascending order
            projects = session.query(ProjectTransaction).order_by(ProjectTransaction.StartDtTm.asc()).all()
        else:
            # Filter projects where the logged-in user is the ProjLead, AllocBy, or TaskLead of any task, and sort by Start Date
            projects = session.query(ProjectTransaction).filter(
                (ProjectTransaction.ProjLead == user_code) |  # Logged-in user is ProjLead
                (ProjectTransaction.AllocBy == user_code) |  # Logged-in user allocated the project
                ProjectTransaction.task_transactions.any(TaskTransaction.TaskLead == user_code) |  # Logged-in user is TaskLead of any task
                ProjectTransaction.task_transactions.any(TaskTransaction.AllocBy == loggedin_user.Code)
            ).order_by(ProjectTransaction.StartDtTm.asc()).all()

    projects_list = []
    for project in projects:
        project_data = project.to_dict()
        project_data['planned_duration'] = format_timedelta(project.EndDtTm - project.StartDtTm)  # difference between StartDtTm and EndDtTm
        project_data['attachments_no'] = len(get_attachments(project.ID, e_TranType.ProjectTran.idx))
        project_data['notifications'] = {
            "total": len([notification for notification in get_notification_trantype_tranmid(project.ID, e_TranType.ProjectTran.idx) if notification.SentTo==loggedin_user.Code]),
            "unread": len([notification for notification in get_notification_trantype_tranmid(project.ID, e_TranType.ProjectTran.idx) if notification.SentTo==loggedin_user.Code and notification.Status==e_NotificationStatus.Pending.idx and notification.ReadDtTm==None]) #return the length of unread notifications associated with the task
        }

        # Get tasks associated with the project
        associated_tasks = project.task_transactions
        project_data['tasks_list'] = [task.to_dict() for task in associated_tasks]
        
        projects_list.append(project_data)

    session.close()
    return projects_list

def list_all_projects():
    session = DBSession()
    projects = session.query(ProjectTransaction).all()
    session.close()
    return projects
        
def get_project_object(project_id):
    session = DBSession()
    project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == project_id).one_or_none()
    session.close()
    return project


def save_attachments_for_project(project_txn_id, project_template_id):
    try:
        session = DBSession()
        project_template = session.query(ProjectTemplate).filter(ProjectTemplate.ID == int(project_template_id)).one_or_none()
        if not project_template:
            session.close()
            raise ValueError(f"Project Template with ID {project_template_id} not found. Project added but, Failed to add Attachments.")
        attachments = session.query(AttachmentDetails).filter(AttachmentDetails.TranMID == int(project_template_id)).filter(AttachmentDetails.TranType == e_TranType.ProjectTmpl.idx).all()
        for attachment in attachments:
            attachment_obj = AttachmentDetails()
            attachment_obj.TranType = e_TranType.ProjectTran.idx
            attachment_obj.TranMID = int(project_txn_id)
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
        app.logger(e)
        return False