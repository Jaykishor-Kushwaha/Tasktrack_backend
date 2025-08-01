from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists, user_authorized_task, tasklead_user_only, task_allocatedby_user_only
from flask import jsonify, request, session
import platform
import socket

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.TaskTemplate import (TaskTemplate as TaskTemplate)
from task_trak.db.models.StaffMaster import (StaffMaster as StaffMaster)
from task_trak.db.models.ProjectTransaction import (ProjectTransaction as ProjectTransaction)
from task_trak.db.models.TaskTransaction import (TaskTransaction as TaskTransaction)
from task_trak.db.models.SubTaskTransaction import (SubTaskTransaction as SubTaskTransaction)
from task_trak.db.models.CommunicationCenter import (CommunicationCenter as CommunicationCenter)
from task_trak.db.models.UserActivity import (UserActivity as UserActivity)
from task_trak.db.models.SystemConfig import (SystemConfig as SystemConfig)
from sqlalchemy import create_engine, func, desc, or_, cast, Date
from sqlalchemy.orm import sessionmaker


# utils import
from task_trak.common.utils import format_timedelta

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TaskStatus, e_SubTaskStatus, e_Priority, e_TranType, e_SysConfig, e_NotificationStatus, e_ActionType

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta
import math

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

my_system = platform.uname()

@admin_only
def listUserActivity():
    try:
        session = DBSession()

        # Extract filters from query parameters
        staff_code = request.args.get('staff_code', 'ALL')  # User filter, default to ALL
        action_type = request.args.get('action_type', 'ALL')  # Action Type filter, default to ALL
        entity_type = request.args.get('entity_type', 'ALL')  # Entity Type filter, default to ALL
        entity_id = request.args.get('entity_id', '0')  # Entity ID filter, default to 0
        # report_days_upto = int(app.config[e_SysConfig.ReportDaysUpto.Key])  # Fetch system config for report days up to
        report_days_upto = int(session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.ReportDaysUpto.Key).first().Value)

        # Handle date filter (restrict based on system config)
        try:
            period = request.args.get('period', None) if request.args.get('period') != '' else None #period selected by user
            start_date, end_date = period.split(',')
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            end_date = end_date + timedelta(days=1) - timedelta(seconds=1)
            # start_date = request.args.get('date_from', (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'))
            # end_date = request.args.get('date_to', datetime.now().strftime('%Y-%m-%d'))
            # start_date = datetime.strptime(start_date, '%Y-%m-%d')
            # end_date = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}), 400

        # Calculate the maximum allowed end date based on system config
        generated_date = start_date + timedelta(days=report_days_upto)
        if end_date > generated_date:
            return jsonify({
                "status": "error", 
                "message": f"Maximum end date can be {generated_date.strftime('%Y-%m-%d')}"
            }), 400

        # Build query with date-only comparison
        query = session.query(UserActivity).filter(
            UserActivity.ActionDtTm >= start_date,
            UserActivity.ActionDtTm <= end_date
        )

        # Build query with filters
        if staff_code != 'ALL':
            query = query.filter(UserActivity.StaffCode == staff_code)

        if action_type != 'ALL':
            query = query.filter(UserActivity.ActionType == action_type)

        if entity_type != 'ALL':
            query = query.filter(UserActivity.EntityType == entity_type)

        if entity_id != '0':
            query = query.filter(UserActivity.EntityID == int(entity_id))

        # Apply sorting (newest first)
        query = query.order_by(UserActivity.ActionDtTm.desc())

        # Execute query and fetch results
        activities = query.all()

        # Format the result
        result = [activity.to_dict() for activity in activities]

        return jsonify({
            "status": "success",
            "data": result
        }), 200

    except Exception as e:
        app.logger.error(f"Error in fetching audit log: {str(e)}")
        return jsonify({"status": "error", "message": "An error occurred while fetching the audit log."}), 500

    finally:
        session.close()

# methods for auto-notifications i.e. notifications added by system on specific action
def createUserActivityLogin(ActionType=None, ActionDscr=None, EntityType=None, EntityID=None, ChangeLog=None, UserCode=None, CrBy=None):
    try:
        session = DBSession()  # Ensure a new session is created for each call
        user_activity = UserActivity()
        user_activity.StaffCode = UserCode
        user_activity.ActionDtTm = datetime.now()
        user_activity.ActionType = ActionType
        user_activity.ActionDscr = ActionDscr
        user_activity.EntityType = EntityType
        user_activity.EntityID = EntityID
        user_activity.ChangeLog = ChangeLog
        user_activity.FromIP = socket.gethostbyname(my_system.node)
        user_activity.FromDeviceNm = my_system.node
        user_activity = set_models_attr.setCreatedInfo(user_activity)
        if user_activity.CrBy is None:
            user_activity.CrBy = CrBy
        if user_activity.CrFrom is None:
            user_activity.CrFrom = str(my_system.node)
        if ActionType == e_ActionType.LogInSuccess.idx:
            loggedin_user = session.query(StaffMaster).filter(StaffMaster.Code == UserCode).one_or_none()
            loggedin_user.LstLoginDtTm = datetime.now()
            session.add(loggedin_user)
        session.add(user_activity)
        session.commit()
        return True
    except Exception as e:
        app.logger.error(e)
        return False
    finally:
        if session:
            session.close()

@login_required
def createUserActivity(ActionType=None, ActionDscr=None, EntityType=None, EntityID=None, ChangeLog=None):
    from task_trak.controllers.staffController import get_user_object
    try:
        session = DBSession()  # Ensure a new session is created for each call
        loggedin_user = session.query(StaffMaster).filter(StaffMaster.LoginId == createUserActivity.user_loginid).one_or_none()
        user_activity = UserActivity()
        user_activity.StaffCode = loggedin_user.Code
        user_activity.ActionDtTm = datetime.now()
        user_activity.ActionType = ActionType
        user_activity.ActionDscr = ActionDscr
        user_activity.EntityType = EntityType
        user_activity.EntityID = EntityID
        user_activity.ChangeLog = ChangeLog
        user_activity.FromIP = socket.gethostbyname(my_system.node)
        user_activity.FromDeviceNm = my_system.node
        user_activity = set_models_attr.setCreatedInfo(user_activity)
        session.add(user_activity)
        session.commit()
        return True
    except Exception as e:
        app.logger.error(e)
        return False
    finally:
        if session:
            session.close()

@login_required
def createUserActivityForReport():
    """
    Create user activity for exporting or printing a report.

    :return: JSON response indicating success or failure.
    """
    try:
        # Create a new DB session
        session = DBSession()

        action_type_arg = request.args.get('action_type')
        report_name = request.args.get('report_name')

        if not action_type_arg or not report_name:
            return jsonify({"status": "error", "message": "Missing required parameters"}), 400


        # Get the logged-in user's details
        loggedin_user = session.query(StaffMaster).filter(StaffMaster.LoginId == createUserActivityForReport.user_loginid).one_or_none()

        if not loggedin_user:
            return jsonify({"status": "error", "message": "Logged-in user not found"}), 404

        # Create user activity entry
        user_activity = UserActivity()
        user_activity.StaffCode = loggedin_user.Code
        user_activity.ActionDtTm = datetime.now()

        # Set action type based on argument
        if action_type_arg == 'export':
            action_type = e_ActionType.ExportReport.idx
            action_type_dscr = e_ActionType.ExportReport.textval
        else:
            action_type = e_ActionType.PrintReport.idx
            action_type_dscr = e_ActionType.PrintReport.textval

        # Build the action description dynamically using query parameters
        query_params = request.args.to_dict()  # Get all query parameters as a dictionary
        action_description = f"{action_type_dscr} {report_name}\n"
        for param_name, param_value in query_params.items():
            action_description += f"{param_name}={param_value}\n"  # Append each query param and value

        # Set action type and description
        user_activity.ActionType = action_type
        user_activity.ActionDscr = action_description.strip()  # Trim trailing newline

        # EntityType and EntityID will be 0 for report activities
        user_activity.EntityType = 0
        user_activity.EntityID = 0

        # Get client IP and server hostname
        user_activity.FromIP = request.remote_addr  # Client's IP address
        user_activity.FromDeviceNm = socket.gethostname()  # Server hostname

        # Set created info (e.g., timestamps)
        user_activity = set_models_attr.setCreatedInfo(user_activity)

        # Add the activity to the session and commit
        session.add(user_activity)
        session.commit()

        return jsonify({"status": "success", "message": "User activity created successfully"}), 201

    except Exception as e:
        # Log any error and return a failure response
        app.logger.error(f"Error creating user activity: {e}")
        session.rollback()  # Rollback any uncommitted transactions
        return jsonify({"status": "error", "message": "Failed to create user activity"}), 500

    finally:
        # Close the session to avoid leaks
        if session:
            session.close()
