from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists, user_authorized_task, tasklead_user_only, task_allocatedby_user_only
from flask import jsonify, request, session

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.TaskTemplate import (TaskTemplate as TaskTemplate)
from task_trak.db.models.StaffMaster import (StaffMaster as StaffMaster)
from task_trak.db.models.ProjectTransaction import (ProjectTransaction as ProjectTransaction)
from task_trak.db.models.TaskTransaction import (TaskTransaction as TaskTransaction)
from task_trak.db.models.SubTaskTransaction import (SubTaskTransaction as SubTaskTransaction)
from task_trak.db.models.CommunicationCenter import (CommunicationCenter as CommunicationCenter)
from task_trak.db.models.SystemConfig import (SystemConfig as SystemConfig)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker

from task_trak.controllers.projectTemplateController import get_project_template_object, update_project_template_aprx_duration, get_project_template_aprx_duration_total, timedelta_to_days_hours_minutes
from task_trak.controllers.taskTemplateController import list_task_templates_all, task_template_with_subtask_templates, parse_duration, get_task_template_object
from task_trak.controllers.projectTxnController import get_project_object
from task_trak.controllers.staffController import get_users_list, get_user_object, get_user_by_code
from task_trak.controllers.attachmentController import get_attachments

# utils import
from task_trak.common.utils import format_timedelta

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TaskStatus, e_SubTaskStatus, e_Priority, e_TranType, e_SysConfig

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta
import math

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@login_required
def overDue(user_code):
    try:
        all_param = request.args.get('all', type=bool, default=False)
        session = DBSession()
        current_dt = datetime.now()
        current_user = get_user_by_code(user_code)
        current_user_type = current_user.Type

        if all_param and overDue.user_type in [e_UserType.Admin.textval, e_UserType.SysAdm.textval]:
            tasks_list = session.query(TaskTransaction).filter(
                or_(
                    (TaskTransaction.Status == e_TaskStatus.Pending.idx) & (current_dt > TaskTransaction.StartDtTm),
                    (TaskTransaction.Status == e_TaskStatus.Inprocess.idx) & (current_dt > TaskTransaction.EndDtTm)
                )
            ).all()
        else:
            if current_user_type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx, e_UserType.Staff.idx]:  # if admin or sys_admin
                tasks_list = session.query(TaskTransaction).filter(
                    (or_(
                        (TaskTransaction.TaskLead == current_user.Code),
                        (TaskTransaction.AllocBy == current_user.Code)
                    )) &
                    or_(
                        (TaskTransaction.Status == e_TaskStatus.Pending.idx) & (current_dt > TaskTransaction.StartDtTm),
                        (TaskTransaction.Status == e_TaskStatus.Inprocess.idx) & (current_dt > TaskTransaction.EndDtTm)
                    )
                ).all()
            else:  # if not any of the above, then don't show any task
                tasks_list = []
        
        result = [
            {
                **task.to_dict(),
                "sub_tasks_list": [
                    sub_task.to_dict() for sub_task in sorted(task.subtask_transaction, key=lambda sub_task: sub_task.OrdNo)
                ],
                "attachments_no": len(get_attachments(task.ID, e_TranType.TaskTran.idx))
            }
            for task in tasks_list
        ]
            
        session.close()
        return jsonify({"status":"success", "task_count":len(tasks_list), "data":result}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to retrieve overdue tasks."}), 500

@login_required
def onGoing(user_code):
    try:
        all_param = request.args.get('all', type=bool, default=False)
        session = DBSession()
        current_user = get_user_by_code(user_code)
        current_user_type = current_user.Type

        if all_param and onGoing.user_type in [e_UserType.Admin.textval, e_UserType.SysAdm.textval]:
            tasks_list = session.query(TaskTransaction).filter(
                    TaskTransaction.Status == e_TaskStatus.Inprocess.idx
                ).all()
        else:
            if current_user_type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx, e_UserType.Staff.idx]:  # if admin or sys_admin
                tasks_list = session.query(TaskTransaction).filter(
                    (or_(
                        (TaskTransaction.TaskLead == current_user.Code),
                        (TaskTransaction.AllocBy == current_user.Code)
                    )) &
                    (TaskTransaction.Status == e_TaskStatus.Inprocess.idx)
                ).all()
            else:  # if not any of the above, then don't show any task
                tasks_list = []

        result = [
            {
                **task.to_dict(),
                "sub_tasks_list": [
                    sub_task.to_dict() for sub_task in sorted(task.subtask_transaction, key=lambda sub_task: sub_task.OrdNo)
                ],
                "attachments_no": len(get_attachments(task.ID, e_TranType.TaskTran.idx))
            }
            for task in tasks_list
        ]
        
        session.close()
        return jsonify({"status":"success", "task_count":len(tasks_list), "data":result}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to retrieve ongoing tasks."}), 500

@login_required
def underReview(user_code):
    try:
        all_param = request.args.get('all', type=bool, default=False)
        session = DBSession()
        current_user = get_user_by_code(user_code)
        current_user_type = current_user.Type

        if all_param and underReview.user_type in [e_UserType.Admin.textval, e_UserType.SysAdm.textval]:
            tasks_list = session.query(TaskTransaction).filter(
                TaskTransaction.Status == e_TaskStatus.PendReview.idx
            ).all()
        else:
            if current_user_type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx, e_UserType.Staff.idx]:  # if admin or sys_admin
                tasks_list = session.query(TaskTransaction).filter(
                    (or_(
                        (TaskTransaction.TaskLead == current_user.Code),
                        (TaskTransaction.AllocBy == current_user.Code)
                    )) &
                    (TaskTransaction.Status == e_TaskStatus.PendReview.idx)
                ).all()
            else:  # if not any of the above, then don't show any task
                tasks_list = []
        
        result = [
            {
                **task.to_dict(),
                "sub_tasks_list": [
                    sub_task.to_dict() for sub_task in sorted(task.subtask_transaction, key=lambda sub_task: sub_task.OrdNo)
                ],
                "attachments_no": len(get_attachments(task.ID, e_TranType.TaskTran.idx))
            }
            for task in tasks_list
        ]

        session.close()
        return jsonify({"status":"success", "task_count":len(tasks_list), "data":result}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to retrieve tasks under review."}), 500

@login_required
def upComing(user_code):
    try:
        all_param = request.args.get('all', type=bool, default=False)
        session = DBSession()
        current_dt = datetime.now()
        current_user = get_user_by_code(user_code)
        current_user_type = current_user.Type

        if all_param and upComing.user_type in [e_UserType.Admin.textval, e_UserType.SysAdm.textval]:
            tasks_list = session.query(TaskTransaction).filter(
                (TaskTransaction.Status == e_TaskStatus.Pending.idx) & (TaskTransaction.StartDtTm >= current_dt) & (TaskTransaction.StartDtTm <= current_dt + timedelta(days=int(session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.UpcomingDay.Key).first().Value)))
            ).all()
        else:
            if current_user_type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx, e_UserType.Staff.idx]:  # if admin or sys_admin
                tasks_list = session.query(TaskTransaction).filter(
                    (or_(
                        (TaskTransaction.TaskLead == current_user.Code),
                        (TaskTransaction.AllocBy == current_user.Code)
                    )) &
                    (TaskTransaction.Status == e_TaskStatus.Pending.idx) & (TaskTransaction.StartDtTm >= current_dt) & (TaskTransaction.StartDtTm <= current_dt + timedelta(days=int(session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.UpcomingDay.Key).first().Value)))
                ).all()
            else:  # if not any of the above, then don't show any task
                tasks_list = []

        result = [
            {
                **task.to_dict(),
                "sub_tasks_list": [
                    sub_task.to_dict() for sub_task in sorted(task.subtask_transaction, key=lambda sub_task: sub_task.OrdNo)
                ],
                "attachments_no": len(get_attachments(task.ID, e_TranType.TaskTran.idx))
            }
            for task in tasks_list
        ]
        
        session.close()
        return jsonify({"status":"success", "task_count":len(tasks_list), "data":result}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to retrieve upcoming tasks."}), 500
    
@login_required
def unreadNotifications(user_code):
    try:
        notifications = get_unread_notifications(user_code)
        notifications_list = [notification.to_dict() for notification in notifications]
        return jsonify({"status":"success", "data": notifications_list}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to retrieve unread notifications."}), 500

@login_required
def taskCountsDashboard(user_code=None):
    try:
        session = DBSession()
        upcoming_days_upto = session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.UpcomingDay.Key).first().Value
        session.close()
        all_param = request.args.get('all', type=bool, default=False)
        current_dt = datetime.now()
        if user_code:
            current_user = get_user_by_code(user_code)
        else:
            current_user = get_user_object(taskCountsDashboard.user_loginid)
        current_user_type = current_user.Type
        current_user_loginid = current_user.LoginId

        if all_param and taskCountsDashboard.user_type in [e_UserType.Admin.textval, e_UserType.SysAdm.textval]:
            overdue_conditions = [
                or_(
                    (TaskTransaction.Status == e_TaskStatus.Pending.idx) & (current_dt > TaskTransaction.StartDtTm),
                    (TaskTransaction.Status == e_TaskStatus.Inprocess.idx) & (current_dt > TaskTransaction.EndDtTm)
                )
            ]
            ongoing_conditions = [(TaskTransaction.Status == e_TaskStatus.Inprocess.idx)]
            under_review_conditions = [(TaskTransaction.Status == e_TaskStatus.PendReview.idx)]
            upcoming_conditions = [
                (TaskTransaction.Status == e_TaskStatus.Pending.idx) & (TaskTransaction.StartDtTm >= current_dt) & (TaskTransaction.StartDtTm <= current_dt + timedelta(days=int(upcoming_days_upto)))
            ]
        else:
            if current_user_type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx, e_UserType.Staff.idx]:
                current_user = get_user_object(current_user_loginid)
                overdue_conditions = [
                    or_(
                        (TaskTransaction.TaskLead == current_user.Code),
                        (TaskTransaction.AllocBy == current_user.Code)
                    ),
                    or_(
                        (TaskTransaction.Status == e_TaskStatus.Pending.idx) & (current_dt > TaskTransaction.StartDtTm),
                        (TaskTransaction.Status == e_TaskStatus.Inprocess.idx) & (current_dt > TaskTransaction.EndDtTm)
                    )
                ]
                ongoing_conditions = [
                    (TaskTransaction.TaskLead == current_user.Code),
                    (TaskTransaction.Status == e_TaskStatus.Inprocess.idx)
                ]
                under_review_conditions = [
                    (TaskTransaction.TaskLead == current_user.Code),
                    (TaskTransaction.Status == e_TaskStatus.PendReview.idx)
                ]
                upcoming_conditions = [
                    (TaskTransaction.TaskLead == current_user.Code),
                    (TaskTransaction.Status == e_TaskStatus.Pending.idx) & (TaskTransaction.StartDtTm >= current_dt) & (TaskTransaction.StartDtTm <= current_dt + timedelta(days=int(upcoming_days_upto)))
                ]
            else:
                overdue_conditions = ongoing_conditions = under_review_conditions = upcoming_conditions = []

        overdue_count = get_task_count(overdue_conditions)
        ongoing_count = get_task_count(ongoing_conditions)
        under_review_count = get_task_count(under_review_conditions)
        upcoming_count = get_task_count(upcoming_conditions)
        unread_notification_count = get_unread_notifications(current_user.Code)

        return jsonify({
            "status": "success",
            "data": {
                "overdue_count": overdue_count,
                "ongoing_count": ongoing_count,
                "under_review_count": under_review_count,
                "upcoming_count": upcoming_count,
                "unread_notification_count": len(unread_notification_count)
            }
        }), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status":"error", "message":"Failed to retrieve task counts."}), 500
    
def get_task_count(status_conditions, additional_conditions=None):
    session = DBSession()
    query = session.query(TaskTransaction).filter(*status_conditions)
    if additional_conditions:
        query = query.filter(*additional_conditions)
    session.close()
    return query.count()

def get_unread_notifications(loggedin_user_code):
    session = DBSession()
    notifications = session.query(CommunicationCenter).filter(CommunicationCenter.SentTo == loggedin_user_code).filter(CommunicationCenter.ReadDtTm == None).all()
    session.close()
    return notifications