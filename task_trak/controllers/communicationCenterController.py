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
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker


# utils import
from task_trak.common.utils import format_timedelta

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TaskStatus, e_SubTaskStatus, e_Priority, e_TranType, e_SysConfig, e_NotificationStatus

# common imports
from task_trak.common import set_models_attr

from datetime import datetime, timedelta
import math

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@login_required
def addNotification():
    from task_trak.controllers.staffController import get_users_list, get_user_object, get_user_by_code
    if request.method == 'POST':
        notification_data = request.get_json()
        try:
            notification_status = add_notification_object(notification_data)
            if notification_status:
                return jsonify({"status": "success", "message": "Notification added"}), 201
            else:
                return jsonify({"status": "error", "message": "Error while adding notification"}), 500
                
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status": "error", "message": f'Error occured while adding notification - {str(e)}'}), 200
    if request.method == 'GET':
        users_list = [user.Code for user in get_users_list(addNotification.user_type, bypass_check=True) if user.IsActive]
        status_list, priority_list = enum_to_list(e_TaskStatus), enum_to_list(e_Priority)
        return jsonify({"status": "success", "data": {"users_list":users_list, "priority_list": priority_list, "status_list": status_list}}), 200
    

@login_required
def getNotification(notification_id):
    from task_trak.controllers.staffController import get_users_list, get_user_object, get_user_by_code
    notification = get_notification_object(notification_id)
    if notification is None:
        return jsonify({"status": "error", "message": "Notification not found"}), 404
    else:
        loggedin_user = get_user_object(getNotification.user_loginid)
        if notification.SentTo == loggedin_user.Code and notification.ReadDtTm is None: #if notification allocated to user reads the notification then set the read date-time if it's not already read before
            if not update_notification_read_status(notification):
                return jsonify({"status": "error", "message": "Failed to update notification read status"}), 500
        return jsonify({"status": "success", "data": notification.to_dict()}), 200
    
@login_required
def listNotifications():
    from task_trak.controllers.staffController import get_users_list, get_user_object, get_user_by_code
    all_notifications = request.args.get('all', 'false').lower() == "true"
    payload = {
        'TranType': request.args.get('TranType', None),
        'TranMID': request.args.get('TranMID', None),
        'limit': request.args.get('limit', None)
    }
    loggedin_user = get_user_object(listNotifications.user_loginid)
    if all_notifications:
        notifications = list_notifications(loggedin_user, payload, all_notifications=True)
    else:
        notifications = list_notifications(loggedin_user, payload, all_notifications=False)
        
    if notifications == False:
        return jsonify({"status": "error", "message": "Error occured while listing notifications"}), 500
    else:
        return jsonify({"status": "success", "data": notifications}), 200
    
@login_required
def getUnreadNotificationsCount():
    from task_trak.controllers.staffController import get_users_list, get_user_object, get_user_by_code
    loggedin_user = get_user_object(getUnreadNotificationsCount.user_loginid)
    try:
        unread_count = get_unread_notifications_count(loggedin_user)
        return jsonify({"status": "success", "data": unread_count}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({"status": "error", "message": f'Error occured while getting unread notifications count - {str(e)}'}), 500

def get_unread_notifications_count(loggedin_user):
    session = DBSession()
    unread_count = session.query(CommunicationCenter).filter(CommunicationCenter.SentTo == loggedin_user.Code, CommunicationCenter.ReadDtTm == None).count()
    session.close()
    return unread_count

def add_notification_object(notification_data):
    from task_trak.controllers.staffController import get_users_list, get_user_object, get_user_by_code
    try:
        special_cases = ['ReadDtTm']
        notification = CommunicationCenter()

        for key, value in notification_data.items():
            if key not in special_cases: #special_cases will hold the attributes that shouldn't be set while adding
                if key in ["TranType", "TranMID"]:
                    if value:
                        if key == "TranType":
                            setattr(notification, key, int(value))
                        elif key == "TranMID":
                            if notification.TranType == 2:
                                user = get_user_by_code(value)
                                if user:
                                    setattr(notification, key, user.ID)
                            else:
                                setattr(notification, key, int(value))
                else:
                    setattr(notification, key, value)

        notification.DtTime = datetime.now()
        notification = set_models_attr.setCreatedInfo(notification)
        session = DBSession()
        session.add(notification)
        session.commit()
        session.close()
        return True
    except Exception as e:
        app.logger.error(e)
        return False

def list_notifications(loggedin_user, filters, all_notifications=False):
    try:
        session = DBSession()
        
        # Check if limit is provided and not None
        if 'limit' in filters and filters['limit'] is not None:
            # if loggedin_user.Type == e_UserType.Staff.idx:
            #     query = session.query(CommunicationCenter).filter(
            #         CommunicationCenter.SentTo == loggedin_user.Code,
            #         CommunicationCenter.ReadDtTm == None
            #     )
            # else:
            #     query = session.query(CommunicationCenter).filter(CommunicationCenter.ReadDtTm == None)
            query = session.query(CommunicationCenter).filter(
                CommunicationCenter.SentTo == loggedin_user.Code,
                CommunicationCenter.ReadDtTm == None
            )
            
            # Order by most recent and apply the limit
            notifications_list = query.order_by(CommunicationCenter.Status.asc(), CommunicationCenter.DtTime.asc()).limit(int(filters['limit'])).all()
        else:
            # Build the base query
            if all_notifications:
                # if loggedin_user.Type == e_UserType.Staff.idx:
                query = session.query(CommunicationCenter).filter(or_(CommunicationCenter.SentTo == loggedin_user.Code, CommunicationCenter.SentBy == loggedin_user.Code))
                # else:
                #     query = session.query(CommunicationCenter)
            else:
                # if loggedin_user.Type == e_UserType.Staff.idx:
                query = session.query(CommunicationCenter).filter(
                    or_(
                        CommunicationCenter.SentTo == loggedin_user.Code,
                        CommunicationCenter.SentBy == loggedin_user.Code
                    ),
                    CommunicationCenter.TranType == int(filters['TranType']),
                    CommunicationCenter.TranMID == int(filters['TranMID'])
                )
                # else:
                #     query = session.query(CommunicationCenter).filter(
                #         CommunicationCenter.TranType == int(filters['TranType']),
                #         CommunicationCenter.TranMID == int(filters['TranMID'])
                #     )
            
            # Sort by Status (Pending first) and DtTime (oldest first)
            notifications_list = query.order_by(CommunicationCenter.Status.asc(), CommunicationCenter.DtTime.asc()).all()
        
        # Convert to dict format
        notifications_list = [notification.to_dict() for notification in notifications_list]
        
        return notifications_list
    except Exception as e:
        app.logger.error(e)
        return False
    

def get_notification_object(notification_id):
    session = DBSession()
    notification = session.query(CommunicationCenter).filter(CommunicationCenter.ID == notification_id).one_or_none()
    session.close()
    return notification

def update_notification_read_status(notification_obj):
    try:
        session = DBSession()
        # Reattach the notification_obj to the session
        notification_obj = session.merge(notification_obj)
        notification_obj.Status = e_NotificationStatus.Read.idx
        notification_obj.ReadDtTm = datetime.now()
        session.add(notification_obj)
        session.commit()
        session.close()
        return True
    except Exception as e:
        app.logger.error(e)
        return False
    

# methods for auto-notifications i.e. notifications added by system on specific action
def generateNotification(From=None, To=None, tranType=None, tranMID=None, Subject=None, Description=None):
    from task_trak.controllers.staffController import get_users_list, get_user_object, get_user_by_code
    try:
        session = DBSession()
        if type(To) == list:
            for user_code in To:
                sent_to_user = get_user_by_code(user_code)
                if sent_to_user.IsActive:
                    notification = CommunicationCenter()
                    notification.SentBy = From
                    notification.SentTo = user_code
                    notification.TranType = tranType
                    notification.TranMID = get_user_by_code(user_code).ID if "New user Created" in Subject else tranMID
                    notification.Subject = Subject
                    notification.Description = Description
                    notification.DtTime = datetime.now()
                    notification = set_models_attr.setCreatedInfo(notification)
                    session.add(notification)
        else:
            notification = CommunicationCenter()
            notification.SentBy = From
            notification.SentTo = To
            notification.TranType = tranType
            notification.TranMID = tranMID
            notification.Subject = Subject
            notification.Description = Description
            notification.DtTime = datetime.now()
            notification = set_models_attr.setCreatedInfo(notification)
            session.add(notification)
        session.commit()
        session.close()
        return True
    except Exception as e:
        app.logger.error(e)
        return False
    
@login_required
def get_notification_trantype_tranmid(tranMID, tranType):
    from task_trak.controllers.staffController import get_users_list, get_user_object, get_user_by_code
    logged_in_user = get_user_object(get_notification_trantype_tranmid.user_loginid)
    session = DBSession()
    if logged_in_user.Type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx]:
        notifications = session.query(CommunicationCenter).filter(CommunicationCenter.TranType == int(tranType), CommunicationCenter.TranMID == int(tranMID)).all()
    else:
        notifications = session.query(CommunicationCenter).filter(
            CommunicationCenter.TranType == int(tranType),
            CommunicationCenter.TranMID == int(tranMID),
            or_(
                CommunicationCenter.SentTo == logged_in_user.Code,
                CommunicationCenter.SentBy == logged_in_user.Code
            )
        ).all()
    session.close()
    return notifications

#TODO: when finalized what to do with notification's trantype and tranmid then implement the same here - NOTE: we can't set it to None as it will breaks a not null constraint
def clear_out_notifications_linkage(txnMid, txnType):
    try:
        session = DBSession()
        notifications = session.query(CommunicationCenter).filter(
            CommunicationCenter.TranType == txnType,
            CommunicationCenter.TranMID == txnMid
        ).all()
        
        for notification in notifications:
            notification.TranType = 0
            notification.TranMID = 0
            session.add(notification)
        session.commit()
        session.close()
        return True
    except Exception as e:
        app.logger.error(f"Error clearing notifications linkage: {e}")
        return False