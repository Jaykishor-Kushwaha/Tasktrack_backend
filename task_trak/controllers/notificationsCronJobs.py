from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists, user_authorized_task, tasklead_user_only, task_allocatedby_user_only
from flask import jsonify, request, session
import socket
import platform

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.TaskTemplate import (TaskTemplate as TaskTemplate)
from task_trak.db.models.StaffMaster import (StaffMaster as StaffMaster)
from task_trak.db.models.ProjectTransaction import (ProjectTransaction as ProjectTransaction)
from task_trak.db.models.TaskTransaction import (TaskTransaction as TaskTransaction)
from task_trak.db.models.SubTaskTransaction import (SubTaskTransaction as SubTaskTransaction)
from task_trak.db.models.CommunicationCenter import (CommunicationCenter as CommunicationCenter)
from task_trak.db.models.CompanyMaster import (CompanyMaster as CompanyMaster)
from task_trak.db.models.SystemConfig import (SystemConfig as SystemConfig)
from task_trak.db.models.UserActivity import (UserActivity as UserActivity)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker, scoped_session
import re


# utils import
from task_trak.common.utils import format_timedelta

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TaskStatus, e_SubTaskStatus, e_Priority, e_TranType, e_SysConfig, e_NotificationStatus, e_ActionType

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta
import math

my_system = platform.uname()

# engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], connect_args={"check_same_thread": False})
Base.metadata.bind = engine
# DBSession = sessionmaker(bind=engine)
DBSession = scoped_session(sessionmaker(bind=engine))

# @app.cli.command("generate_task_notifications")
# def createTaskNotification():
#     """Run scheduled job for creating task statuses."""
#     with app.app_context():
#         print('starting jobs')
#         generate_task_notifications()
#     print('scheduled jobs executed at '+ str(datetime.now()))
#     return

def generate_task_notifications():
    session = DBSession()
    auto_notification_enabled = session.query(CompanyMaster).first().AutoNotification
    if not auto_notification_enabled:
        print("Auto Notification is disabled")
        session.close()
        return
    upcoming_days_upto = int(session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.UpcomingDay.Key).first().Value)
    
    current_dt = datetime.now().date()  # Only use the date portion (no time)

    # Overdue tasks
    overdue_conditions = [
        (TaskTransaction.Status == e_TaskStatus.Inprocess.idx) & (current_dt > func.date(TaskTransaction.EndDtTm))
    ]

    # Upcoming tasks
    upcoming_conditions = [
        (TaskTransaction.Status == e_TaskStatus.Pending.idx) &
        (func.date(TaskTransaction.StartDtTm) >= current_dt) &
        (func.date(TaskTransaction.StartDtTm) <= current_dt + timedelta(days=upcoming_days_upto))
    ]

    # Today's tasks
    today_conditions = [
        func.date(TaskTransaction.StartDtTm) == current_dt
    ]

    # Delayed tasks
    delayed_conditions = [
        (TaskTransaction.Status == e_TaskStatus.Pending.idx) &
        (current_dt > func.date(TaskTransaction.StartDtTm))
    ]

    overdue_task = get_filtered_task(session, overdue_conditions)
    upcoming_task = get_filtered_task(session, upcoming_conditions)
    todays_task = get_filtered_task(session, today_conditions)
    delayed_task = get_filtered_task(session, delayed_conditions)

    result_count = {
        "Today": 0,
        "Overdue": 0,
        "Upcoming": 0,
        "Delayed": 0
    }

    if todays_task:
        result_count = send_notification(session, todays_task, 'Today', result_count)
    
    if overdue_task:
        result_count = send_notification(session, overdue_task, 'Overdue', result_count)

    if upcoming_task:
        result_count = send_notification(session, upcoming_task, 'Upcoming', result_count)
    
    if delayed_task:
        result_count = send_notification(session, delayed_task, 'Delayed', result_count)

    create_user_activity_for_notifications(session, result_count)
    session.close()
    return


def get_filtered_task(session, status_conditions, additional_conditions=None):
    query = session.query(TaskTransaction).filter(*status_conditions)
    if additional_conditions:
        query = query.filter(*additional_conditions)
    return query

def send_notification(session, tasks_list, task_type, result_count):
    current_dt = datetime.now().date()  # Only use the date portion (no time)
    if task_type == 'Today':
        for task in tasks_list:
            notification = CommunicationCenter()
            notification.SentBy = task.AllocBy
            notification.SentTo = task.TaskLead
            notification.TranType = e_TranType.TaskTran.idx
            notification.TranMID = task.ID
            notification.Subject = f"Today's Task: {task.Name}"
            notification.Description = task.Dscr
            notification.DtTime = datetime.now()
            notification.CrBy = "SYS-GENERATED"
            notification.CrFrom = str(my_system.node)
            session.add(notification)
            result_count['Today'] += 1
    elif task_type == 'Overdue':
        days_list = get_days_list(session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.OverdueTaskRepetition.Key).first().Value)
        for task in tasks_list:
            days_diff = (current_dt - task.StartDtTm.date()).days if task.Status == e_TaskStatus.Pending.idx else (current_dt - task.EndDtTm.date()).days
            if days_diff in days_list:
                notification = CommunicationCenter()
                notification.SentBy = task.AllocBy
                notification.SentTo = task.TaskLead
                notification.TranType = e_TranType.TaskTran.idx
                notification.TranMID = task.ID
                notification.Subject = f"Overdue Task ({days_diff} Days): {task.Name}"
                notification.Description = task.Dscr
                notification.DtTime = datetime.now()
                notification.CrBy = "SYS-GENERATED"
                notification.CrFrom = str(my_system.node)
                session.add(notification)
                result_count['Overdue'] += 1
    elif task_type == 'Upcoming':
        days_list = get_days_list(session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.UpcomingTaskRepetition.Key).first().Value)
        for task in tasks_list:
            days_diff = (task.StartDtTm.date() - current_dt).days
            if days_diff in days_list:
                notification = CommunicationCenter()
                notification.SentBy = task.AllocBy
                notification.SentTo = task.TaskLead
                notification.TranType = e_TranType.TaskTran.idx
                notification.TranMID = task.ID
                notification.Subject = f"Upcoming Task ({days_diff} Days): {task.Name}"
                notification.Description = task.Dscr
                notification.DtTime = datetime.now()
                notification.CrBy = "SYS-GENERATED"
                notification.CrFrom = str(my_system.node)
                session.add(notification)
                result_count['Upcoming'] += 1
    elif task_type == 'Delayed':
        days_list = get_days_list(session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.DelayedTaskRepetition.Key).first().Value)
        for task in tasks_list:
            days_diff = (current_dt - task.StartDtTm.date()).days
            if days_diff in days_list:
                notification = CommunicationCenter()
                notification.SentBy = task.AllocBy
                notification.SentTo = task.TaskLead
                notification.TranType = e_TranType.TaskTran.idx
                notification.TranMID = task.ID
                notification.Subject = f"Delayed Task ({days_diff} Days): {task.Name}"
                notification.Description = task.Dscr
                notification.DtTime = datetime.now()
                notification.CrBy = "SYS-GENERATED"
                notification.CrFrom = str(my_system.node)
                session.add(notification)
                result_count['Delayed'] += 1
    else:
        pass
    session.commit()
    return result_count

def get_days_list(config_value):
    days_list = []
    entries = [entry.strip() for entry in config_value.split(',')]
    for entry in entries:
        if '{' in entry:
            match = re.match(r'(\d+)\{(\d+)\}', entry)
            if match:
                base_value = int(match.group(1))
                step = int(match.group(2))
                current_day = days_list[-1] if days_list else 0
                while current_day + step <= base_value:
                    current_day += step
                    days_list.append(current_day)
        else:
            days_list.append(int(entry))
    return sorted(days_list)

def create_user_activity_for_notifications(session, result_count):
    # session = DBSession()
    change_log_for_audit_log = f"Today: {result_count['Today']}\nOverdue: {result_count['Overdue']}\nUpcoming: {result_count['Upcoming']}\nDelayed: {result_count['Delayed']}"
    user_activity = UserActivity()
    user_activity.StaffCode = "SYS-GENERATED"
    user_activity.ActionDtTm = datetime.now()
    user_activity.ActionType = e_ActionType.AddRecord.idx
    user_activity.ActionDscr = e_ActionType.AddRecord.textval
    user_activity.EntityType = 0
    user_activity.EntityID = 0
    user_activity.ChangeLog = change_log_for_audit_log
    try:
        # Try to resolve the system's hostname
        ip_address = socket.gethostbyname(my_system.node)
    except socket.gaierror:
        # If the hostname resolution fails, use 'localhost' or '127.0.0.1'
        ip_address = socket.gethostbyname('localhost')
    user_activity.FromIP = ip_address
    user_activity.FromDeviceNm = my_system.node
    # user_activity = set_models_attr.setCreatedInfo(user_activity)
    user_activity.CrBy = "SYS-GENERATED"
    user_activity.CrFrom = str(my_system.node)
    session.add(user_activity)
    session.commit()
    # session.close()