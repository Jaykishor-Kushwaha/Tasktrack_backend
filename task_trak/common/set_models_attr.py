from flask import request, jsonify
from datetime import datetime
from task_trak import verify_access_token
import platform

from task_trak import get_db_session
from task_trak.db.models.StaffMaster import (StaffMaster as StaffMaster)

my_system = platform.uname()

def verify_token_and_get_user_data():
    bearer_token = request.headers.get('Authorization')
    if not bearer_token:
        return jsonify({"token": "missing"})
    else:
        token = bearer_token.split()[1] 
    verification = verify_access_token(token)
    if not verification["verified"]:
        return jsonify({"token": "invalid"})
    else:
        user_data = eval(verification["user_info"])
        return user_data

# method to set the created info of the database table object
def setCreatedInfo(table_obj):
    user_data = verify_token_and_get_user_data()
    if isinstance(user_data, dict):
        # table_obj.CrDtTm = datetime.now()
        table_obj.CrBy = user_data["user_loginid"]
        table_obj.CrFrom = str(my_system.node)
    return table_obj

# method to set the updated info of the database table object
def setUpdatedInfo(table_obj):
    user_data = verify_token_and_get_user_data()
    if isinstance(user_data, dict):
        # table_obj.LstUpdDtTm = datetime.now()
        table_obj.LstUpdBy = user_data["user_loginid"]
        table_obj.LstUpdFrom = str(my_system.node)
    return table_obj

# method to set the created by info for a project-txn
def setProjectTxnOwnership(project_obj):
    user_data = verify_token_and_get_user_data()
    if isinstance(user_data, dict):
        # table_obj.LstUpdDtTm = datetime.now()
        session = get_db_session()
        user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
        session.close()
        project_obj.AllocBy = user_obj.Code
        # project_obj.LstUpdFrom = str(my_system.node)
    return project_obj

# method to set the created by info for a task-txn
def setTaskTxnOwnership(task_obj):
    user_data = verify_token_and_get_user_data()
    if isinstance(user_data, dict):
        # table_obj.LstUpdDtTm = datetime.now()
        # session = get_db_session()
        # user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
        # session.close()
        # task_obj.AllocBy = user_obj.Code
        task_obj.LstUpdFrom = str(my_system.node)
    return task_obj

# method to set the created by info for a subtask-txn
def setSubTaskTxnOwnership(task_obj):
    user_data = verify_token_and_get_user_data()
    if isinstance(user_data, dict):
        # table_obj.LstUpdDtTm = datetime.now()
        session = get_db_session()
        user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).one_or_none()
        session.close()
        task_obj.AllocBy = user_obj.Code
        # task_obj.SubTaskLead = user_obj.Code
        task_obj.LstUpdFrom = str(my_system.node)
    return task_obj

# method to set the info of user who is accepting the project-txn
def setProjectTxnAcptdBy(project_obj):
    user_data = verify_token_and_get_user_data()
    if isinstance(user_data, dict):
        # table_obj.LstUpdDtTm = datetime.now()
        session = get_db_session()
        user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).one_or_none()
        session.close()
        project_obj.AcptdBy = user_obj.Code
    return project_obj

# method to set the info of user who is closing the project-txn
def setProjectTxnClosureBy(project_obj):
    user_data = verify_token_and_get_user_data()
    if isinstance(user_data, dict):
        # table_obj.LstUpdDtTm = datetime.now()
        session = get_db_session()
        user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).one_or_none()
        session.close()
        project_obj.ClosureBy = user_obj.Code
    return project_obj

# method to set the info of user who is closing the task-txn
def setTaskTxnClosureBy(task_obj):
    user_data = verify_token_and_get_user_data()
    if isinstance(user_data, dict):
        # table_obj.LstUpdDtTm = datetime.now()
        session = get_db_session()
        user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).one_or_none()
        session.close()
        task_obj.ClosureBy = user_obj.Code
    return task_obj