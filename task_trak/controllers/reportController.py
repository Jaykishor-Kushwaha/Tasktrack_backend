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
from task_trak.db.models.SystemConfig import (SystemConfig as SystemConfig)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker

from task_trak.controllers.projectTemplateController import get_project_template_object, update_project_template_aprx_duration, get_project_template_aprx_duration_total, timedelta_to_days_hours_minutes
from task_trak.controllers.taskTemplateController import list_task_templates_all, task_template_with_subtask_templates, parse_duration, get_task_template_object
from task_trak.controllers.staffController import get_users_list,get_user_object, get_user_by_code, get_all_admin_users
from task_trak.controllers.attachmentController import get_attachments, delete_attachments
from task_trak.controllers.taskTxnController import list_all_tasks
from task_trak.controllers.projectTxnController import list_all_projects,get_project_object
from task_trak.controllers.communicationCenterController import generateNotification, get_notification_trantype_tranmid, clear_out_notifications_linkage

# import enumerations
from task_trak.db import enumerations

# utils import
from task_trak.common.utils import format_timedelta, format_aprx_duration

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_ProjStatus, e_TaskStatus, e_SysConfig, e_SubTaskStatus, e_Priority, e_TranType, e_NotificationStatus

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta
import math

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@login_required
def reportList():
    loggedin_user = get_user_object(reportList.user_loginid)
    entity = request.args.get('entity', None) if request.args.get('entity') != '' else None #what to query? - task or project
    entity_status = request.args.get('status', None) if request.args.get('status') != '' else None #which report to fetch
    period = request.args.get('period', None) if request.args.get('period') != '' else None #period selected by user
    user = request.args.get('user', loggedin_user.Code) if request.args.get('user') != '' else loggedin_user.Code #for which user to fetch report
    task_status = request.args.get('task_status', e_TaskStatus.Pending.idx) if request.args.get('task_status') != '' else e_TaskStatus.Pending.idx #which task_status to fetch
    by_or_to_me = request.args.get('by_or_to_me', 'to_me') if request.args.get('by_or_to_me') != '' else 'to_me'
    start_date, end_date = period.split(',')
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')
    db_session = DBSession()
    report_days_upto = int(db_session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.ReportDaysUpto.Key).first().Value)
    db_session.close()
    generated_date = start_date + timedelta(days=report_days_upto)
    if end_date > generated_date:
        return jsonify({"status": "error", "message": f"Maximum end date can be {generated_date.strftime('%Y-%m-%d')}"}), 400

    if period is None:
        return jsonify({"status": "error", "message": "Period is required"}), 400

    if entity == "task":
        task_list = list_all_tasks() #fetch all the tasks
        # apply the task lead and allocby filter filter
        task_list = [task for task in task_list if task.TaskLead == user or task.AllocBy == user] if user != "all" else task_list
        # apply the task status filter only if entity_status is selected as all
        task_list = [task for task in task_list if task.Status == int(task_status)] if task_status != "all" else task_list
        # apply the filter of by_me or to_me if selected user != 'all'
        if user != "all":
            # filter based on alloc_by filter
            if by_or_to_me == "all":
                task_list = [task for task in task_list if (task.TaskLead == user or task.AllocBy == user)]
            else:
                task_list = [task for task in task_list if (task.TaskLead == user if by_or_to_me=="to_me" else task.AllocBy == user)]

        if entity_status == "all":
            pass #don't filter based on task_status as 'all' is selected
        elif entity_status == "open":
            task_list = [task for task in task_list if task.Status not in [e_TaskStatus.Done.idx, e_TaskStatus.Cancelled.idx]]
        elif entity_status == "overdue":
            # fetch overdue tasks for the specified user and date range
            current_date = datetime.now()
            
            # Filter tasks that are overdue based on the new criteria
            task_list = [task for task in task_list if 
                         (task.Status == e_TaskStatus.Pending.idx and current_date > task.StartDtTm) or
                         (task.Status == e_TaskStatus.Inprocess.idx and current_date > task.EndDtTm)]
            
        elif entity_status == "delayed":
            task_list = [task for task in task_list if task.Status == e_TaskStatus.Done.idx]
            task_list = [task for task in task_list if task.ActualEndDtTm and task.EndDtTm and task.ActualEndDtTm > task.EndDtTm]
        elif entity_status == "completing":
            task_list = [task for task in task_list if task.Status not in [e_TaskStatus.Done.idx, e_TaskStatus.Cancelled.idx]]
            task_list = [task for task in task_list if not task.ActualEndDtTm and start_date <= task.EndDtTm <= end_date]
        elif entity_status == "completed":
            task_list = [task for task in task_list if task.Status == e_TaskStatus.Done.idx]
            task_list = [task for task in task_list if start_date <= task.ActualEndDtTm <= end_date]
        elif entity_status == "task_totals":
            user_totals_list = []
            if user == "all":
                all_users = get_users_list(e_UserType.Admin.idx, bypass_check=True)  # Assuming there's a function to get all users
                for user in all_users:
                    user_totals = {
                        "srl": len(user_totals_list) + 1,
                        "user_name": user.Name,
                        "total_tasks": 0,
                        "done_on_time": 0,
                        "done_late": 0,
                        "pending_on_time": 0,
                        "pending_late": 0,
                        "in_progress_on_time": 0,
                        "in_progress_late": 0,
                        "under_review": 0,
                        "cancelled": 0,
                        "efficiency_percentage": 0
                    }

                    tasks = [task for task in task_list if task.TaskLead == user.Code]
                    for task in tasks:
                        user_totals["total_tasks"] += 1
                        if task.Status == e_TaskStatus.Done.idx:
                            if task.ActualEndDtTm and task.EndDtTm and task.ActualEndDtTm <= task.EndDtTm:
                                user_totals["done_on_time"] += 1
                            else:
                                user_totals["done_late"] += 1
                        elif task.Status == e_TaskStatus.Pending.idx:
                            if task.ActualStDtTm and task.StartDtTm and task.ActualStDtTm >= task.StartDtTm:
                                user_totals["pending_on_time"] += 1
                            else:
                                user_totals["pending_late"] += 1
                        elif task.Status == e_TaskStatus.Inprocess.idx:
                            if task.ActualStDtTm and task.StartDtTm and task.ActualStDtTm >= task.StartDtTm:
                                user_totals["in_progress_on_time"] += 1
                            else:
                                user_totals["in_progress_late"] += 1
                        elif task.Status == e_TaskStatus.PendReview.idx:
                            user_totals["under_review"] += 1
                        elif task.Status == e_TaskStatus.Cancelled.idx:
                            user_totals["cancelled"] += 1

                    done_all = user_totals["done_on_time"] + user_totals["done_late"]
                    if done_all > 0:
                        user_totals["efficiency_percentage"] = (user_totals["done_on_time"] / done_all) * 100

                    user_totals_list.append(user_totals)
            else:
                user = get_user_by_code(user) if loggedin_user.Type in [e_UserType.SysAdm.idx, e_UserType.Admin.idx] else loggedin_user

                user_totals = {
                    "srl": len(user_totals_list) + 1,
                    "user_name": user.Name,
                    "total_tasks": 0,
                    "done_on_time": 0,
                    "done_late": 0,
                    "pending_on_time": 0,
                    "pending_late": 0,
                    "in_progress_on_time": 0,
                    "in_progress_late": 0,
                    "under_review": 0,
                    "cancelled": 0,
                    "efficiency_percentage": 0
                }

                tasks = [task for task in task_list if task.TaskLead == user.Code]
                for task in tasks:
                    user_totals["total_tasks"] += 1
                    if task.Status == e_TaskStatus.Done.idx:
                        if task.ActualEndDtTm and task.EndDtTm and task.ActualEndDtTm <= task.EndDtTm:
                            user_totals["done_on_time"] += 1
                        else:
                            user_totals["done_late"] += 1
                    elif task.Status == e_TaskStatus.Pending.idx:
                        if task.ActualStDtTm and task.StartDtTm and task.ActualStDtTm >= task.StartDtTm:
                            user_totals["pending_on_time"] += 1
                        else:
                            user_totals["pending_late"] += 1
                    elif task.Status == e_TaskStatus.Inprocess.idx:
                        if task.ActualStDtTm and task.StartDtTm and task.ActualStDtTm >= task.StartDtTm:
                            user_totals["in_progress_on_time"] += 1
                        else:
                            user_totals["in_progress_late"] += 1
                    elif task.Status == e_TaskStatus.PendReview.idx:
                        user_totals["under_review"] += 1
                    elif task.Status == e_TaskStatus.Cancelled.idx:
                        user_totals["cancelled"] += 1

                done_all = user_totals["done_on_time"] + user_totals["done_late"]
                if done_all > 0:
                    user_totals["efficiency_percentage"] = (user_totals["done_on_time"] / done_all) * 100

                user_totals_list.append(user_totals)

            return jsonify({"status":"success", "data":user_totals_list}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid status"}), 400

        filtered_tasks = []
        for task in task_list:
            actual_start = task.ActualStDtTm or task.StartDtTm
            actual_end = task.ActualEndDtTm or task.EndDtTm
            
            if (
                (actual_start and actual_end and
                    actual_start < start_date and start_date <= actual_end <= end_date) or
                (actual_start and actual_end and
                    start_date <= actual_start <= end_date and start_date <= actual_end <= end_date) or
                (actual_start and actual_end and
                    start_date <= actual_start <= end_date and actual_end > end_date) or
                (actual_start and not task.ActualEndDtTm and
                    actual_start < start_date and task.EndDtTm < start_date and task.Status == e_TaskStatus.Inprocess.idx) or
                (actual_start and actual_end and
                    actual_start < start_date and start_date <= actual_end <= end_date and task.EndDtTm < start_date) or
                (actual_start and actual_end and
                    actual_start < start_date and actual_end > end_date) or
                (actual_start and actual_end and
                    actual_start < start_date and actual_end > end_date and task.EndDtTm < end_date) or
                (entity_status == "open") #if entity_status is 'open' then don't check for the dates
            ):
                filtered_tasks.append(task)

        result = []
        for task in filtered_tasks:
            project_obj = get_project_object(task.ProjTranID)
            project_name = project_obj.Name if project_obj else ''

            lead_obj = get_user_by_code(task.TaskLead)
            lead_name = lead_obj.Name if lead_obj else ''

            alloc_by_obj = get_user_by_code(task.AllocBy)
            alloc_by_name = alloc_by_obj.Name if alloc_by_obj else ''
            
            delay_days = None
            if task.ActualEndDtTm:
                delay_timedelta = task.ActualEndDtTm - task.EndDtTm
            else:
                delay_timedelta = datetime.now() - task.EndDtTm
            if delay_timedelta.total_seconds() >= 0:
                delay_days = format_aprx_duration(delay_timedelta)
            else:
                delay_days = None

            comments = {}
            comments['Closing'] = task.ClosingComment if task.ClosingComment else ""
            comments['Cancel'] = task.CancReason if task.CancReason else ""
            comments['Rejection'] = task.RejectReason if task.RejectReason else ""

            task_data = {
                "srl": len(result) + 1,  # Assuming result is the list where task_data is being appended
                "start_date": task.StartDtTm if task.StartDtTm else None,
                "end_date": task.EndDtTm if task.EndDtTm else None,
                "duration": format_aprx_duration(task.EndDtTm - task.StartDtTm) if task.StartDtTm and task.EndDtTm else None,
                "task_name": task.Name,
                "task_description": task.Dscr,
                "project_name": project_name,
                "lead_name": lead_name,
                "alloc_by_name": alloc_by_name,
                "actual_start_date": task.ActualStDtTm if task.ActualStDtTm else None,
                "actual_end_date": task.ActualEndDtTm if task.ActualEndDtTm else None,
                "status": {"idx": task.Status, "text": enumerations.get_enum_info_by_idx(enumerations.e_TaskStatus, task.Status)[0]},
                "comment": comments,
                "delay_days": delay_days,
                "delay_reason": task.DelayReason
            }
            result.append(task_data)

        return jsonify({"status": "success", "data": result}), 200
    
    elif entity == "project":
        project_list = list_all_projects()
        # apply the project lead and allocby filter
        project_list = [project for project in project_list if project.ProjLead == user or project.AllocBy == user] if user != "all" else project_list
        # apply the filter of by_me or to_me if selected user != 'all'
        if user != "all":
            # filter based on alloc_by filter
            if by_or_to_me == "all":
                project_list = [project for project in project_list if (project.ProjLead == user or project.AllocBy == user)]
            else:
                project_list = [project for project in project_list if (project.ProjLead == user if by_or_to_me=="to_me" else project.AllocBy == user)]
        if entity_status == "all":
            pass #don't filter based on project_status as 'all' is selected

        elif entity_status == "open":
            # fetch tasks for the specified task status
            project_list = [project for project in project_list if project.Status not in [e_ProjStatus.Done.idx, e_ProjStatus.Cancelled.idx]]
            pass
        elif entity_status == "overdue":
            current_date = datetime.now()
            
            # Filter projects that are overdue based on the new criteria
            project_list = [project for project in project_list if 
                         (project.Status == e_ProjStatus.Pending.idx and current_date > project.StartDtTm) or
                         (project.Status == e_ProjStatus.Inprocess.idx and current_date > project.EndDtTm)]
            
            # Further filter projects within the specified date range
            project_list = [project for project in project_list if 
                         start_date <= (project.StartDtTm if project.Status == e_ProjStatus.Pending.idx else project.EndDtTm) <= end_date]
        elif entity_status == "delayed":
            project_list = [project for project in project_list if project.Status == e_ProjStatus.Done.idx]
            project_list = [project for project in project_list if project.ActualEndDtTm and project.EndDtTm and project.ActualEndDtTm > project.EndDtTm]

        else:
            return jsonify({"status":"error", "message":"Invalid status"}), 400
        
        filtered_projects = []
        for project in project_list:
            actual_start = project.ActualStDtTm or project.StartDtTm
            actual_end = project.ActualEndDtTm or project.EndDtTm
            
            if (
                (actual_start and actual_end and
                    actual_start < start_date and start_date <= actual_end <= end_date) or
                (actual_start and actual_end and
                    start_date <= actual_start <= end_date and start_date <= actual_end <= end_date) or
                (actual_start and actual_end and
                    start_date <= actual_start <= end_date and actual_end > end_date) or
                (actual_start and not project.ActualEndDtTm and
                    actual_start < start_date and project.EndDtTm < start_date and project.Status == e_ProjStatus.Inprocess.idx) or
                (actual_start and actual_end and
                    actual_start < start_date and start_date <= actual_end <= end_date and project.EndDtTm < start_date) or
                (actual_start and actual_end and
                    actual_start < start_date and actual_end > end_date) or
                (actual_start and actual_end and
                    actual_start < start_date and actual_end > end_date and project.EndDtTm < end_date)
            ):
                filtered_projects.append(project)

        result = []
        for project in filtered_projects:
            lead_user = get_user_by_code(project.ProjLead)
            alloc_by_user = get_user_by_code(project.AllocBy)
            if lead_user is None or alloc_by_user is None:
                continue
            lead_name = lead_user.Name
            alloc_by_name = alloc_by_user.Name
            
            delay_days = None
            if project.ActualEndDtTm and project.EndDtTm:
                delay_timedelta = project.ActualEndDtTm - project.EndDtTm
                if delay_timedelta > timedelta(0):
                    delay_days = format_aprx_duration(delay_timedelta)
                
            comments = {}
            comments['Closing'] = project.ClosingComment or ""
            comments['Cancel'] = project.CancReason or ""
            comments['Rejection'] = project.RejectReason or ""

            project_data = {
                "srl": len(result) + 1,
                "start_date": project.StartDtTm if project.StartDtTm else None,
                "end_date": project.EndDtTm if project.EndDtTm else None,
                "duration": format_aprx_duration(project.EndDtTm - project.StartDtTm) if project.StartDtTm and project.EndDtTm else None,
                "project_name": project.Name,
                "project_description": project.Dscr,
                "lead_name": lead_name,
                "alloc_by_name": alloc_by_name,
                "actual_start_date": project.ActualStDtTm if project.ActualStDtTm else None,
                "actual_end_date": project.ActualEndDtTm if project.ActualEndDtTm else None,
                "status": {"idx": project.Status, "text": enumerations.get_enum_info_by_idx(enumerations.e_ProjStatus, project.Status)[0]},
                "comment": comments,
                "delay_days": delay_days,
                "delay_reason": project.DelayReason
            }
            result.append(project_data)

        return jsonify({"status": "success", "data": result}), 200