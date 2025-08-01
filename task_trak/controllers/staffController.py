# App imports
from task_trak import app, admin_only, login_required, company_master_exists, system_admin_exists, create_access_token, admin_or_owner
from flask import jsonify, request, session, abort
from werkzeug.exceptions import BadRequest, Unauthorized, Forbidden

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.StaffMaster import (StaffMaster as StaffMaster)
from task_trak.db.models.ProjectTransaction import (ProjectTransaction as ProjectTransaction)
from task_trak.db.models.TaskTransaction import (TaskTransaction as TaskTransaction)
from sqlalchemy import create_engine, func, desc, or_, exists
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.inspection import inspect
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import secrets, string

from task_trak.controllers.companyController import get_company_info
from task_trak.controllers.attachmentController import get_attachments, delete_attachments
from task_trak.controllers.communicationCenterController import generateNotification, get_notification_trantype_tranmid, clear_out_notifications_linkage
from task_trak.controllers.userActivityController import createUserActivity, createUserActivityLogin

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TranType, e_NotificationStatus, e_ActionType

# common imports
from task_trak.common import set_models_attr, encrypt_decrypt

import base64
from datetime import datetime, date
from enum import Enum

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@login_required
@admin_or_owner
def signUp(user_type):
    """
    Sign up a new user.
    
    **POST**: Adds a new user to the database.
    **GET**: Retrieves user type and gender options.

    :return: JSON response with status message and appropriate HTTP status code.
    """
    if request.method == 'POST':
        loggedin_user = get_user_object(signUp.user_loginid)
        user_data = request.get_json()
        email = user_data['EmailID'].lower()
        try:
            user_data = add_user(user_data)
            created_user = user_data['user_obj']
            # send_verification_email(email,request.url_root)
            notification_status = generateNotification(From=loggedin_user.Code, To=[user.Code for user in get_all_admin_users() if user.Code != loggedin_user.Code], tranType=e_TranType.Staff.idx, tranMID=created_user.ID, Subject=f"New user Created : {created_user.Name}", Description=f"New User {created_user.Name} : {get_enum_info_by_idx(e_UserType, created_user.Type)[0]} created.")
            if not notification_status:
                return jsonify({"status":"error", "message":"Failed to send notification."}), 500
            return jsonify({'status':"success", "message": "User added successfully.", "data":{"initial_pawd":str(user_data['initial_password'])}}), 201
        except IntegrityError as e:
            # Check which field caused the integrity error
            error_message = str(e.orig)
            app.logger.error(e)
            if 'UNIQUE constraint failed: staff_master.LoginId' in error_message:
                return jsonify({"status":"error", "message":"LoginId already exists"}), 409
            elif 'UNIQUE constraint failed: staff_master.EmailID' in error_message:
                return jsonify({"status":"error", "message":"EmailID already exists"}), 409
            elif 'UNIQUE constraint failed: staff_master.Code' in error_message:
                return jsonify({"status":"error", "message":"Code already exists"}), 409
            else:
                return jsonify({"status":"error", "message":"Integrity error occurred"}), 500
    else:
        type_gender_optns = {
            "types": enum_to_list(e_UserType, signUp.user_type),
            "gender": enum_to_list(e_Gender)
        }
        # del type_gender_optns["types"][0]
        return jsonify(type_gender_optns), 200
    

@system_admin_exists
# @company_master_exists
def logIn():
    """
    Log in a user.

    **POST**: Authenticates the user and returns a session token.

    :param company_info: Information about the company.
    :return: JSON response with session data or status message and appropriate HTTP status code.
    """
    if request.method == "POST":
        user_data = request.get_json()
        login_id = user_data.get('LoginId')
        password = user_data.get('Pswd')

        if not login_id or not password:
            raise BadRequest(description="LoginId and password are required.")

        user = get_user_object(login_id)

        if not user:
            activity_status = createUserActivityLogin(ActionType=e_ActionType.LogInFailure.idx, ActionDscr=f"{e_ActionType.LogInFailure.textval} User not found : {login_id}", EntityType=0, EntityID=0, ChangeLog="", UserCode=login_id)
            if not activity_status:
                return jsonify({"status":"error", "message":"Error while adding user activity."}), 500
            return jsonify({"status":"error", "message":"Credential do not match."}), 404

        if user.LockAcnt >= 5 and not user.ResetPswd:
            set_password_locked(user)
            # activity_status = createUserActivityLogin(ActionType=e_ActionType.LogInFailure.idx, ActionDscr=f"{e_ActionType.LogInFailure.textval} Account locked due to multiple failed attempts", EntityType=0, EntityID=0, ChangeLog="", UserCode=user.Code)
            # if not activity_status:
            #     return jsonify({"status":"error", "message":"Error while adding user activity."}), 500
            return jsonify({"status":"error", "message":"Your account has been locked. Please contact system administrator."}), 403

        if not user.IsActive:
            activity_status = createUserActivityLogin(ActionType=e_ActionType.LogInFailure.idx, ActionDscr=f"{e_ActionType.LogInFailure.textval} Account is inactive", EntityType=0, EntityID=0, ChangeLog="", UserCode=user.Code)
            if not activity_status:
                return jsonify({"status":"error", "message":"Error while adding user activity."}), 500
            return jsonify({"status":"error", "message":"Your account is inactive..."}), 403

        if user.ResetPswd:
            try:
                verify_password(login_id, password)
                reset_password_token = generate_reset_password_token(login_id)
                # clear_resetpasswd_flag(login_id)
                # reset_lockaccnt_count(login_id)
                token = create_access_token({"user_name": user.Name, "user_loginid": user.LoginId, "user_type": get_enum_info_by_idx(e_UserType, user.Type)[0]})
                company_info = company_info_formatted()
                response_data = {
                    "access_token": token,
                    "user_name": user.Name,
                    "user_gender": get_enum_info_by_idx(e_Gender, user.Gender)[0],
                    "user_loginid": user.LoginId,
                    "user_code": user.Code,
                    "user_profile_img": f"data:image/jpeg;base64,{base64.b64encode(user.Photo).decode('utf-8')}" if user.Photo else "",
                    "user_type": get_enum_info_by_idx(e_UserType, user.Type)[0],
                    "company_info": company_info,
                    "reset_password_token": reset_password_token
                }
                activity_status = createUserActivityLogin(ActionType=e_ActionType.LogInSuccess.idx, ActionDscr=f"{e_ActionType.LogInSuccess.textval} Logged in successfully", EntityType=e_TranType.Staff.idx, EntityID=user.ID, ChangeLog="", UserCode=user.Code)
                if not activity_status:
                    return jsonify({"status":"error", "message":"Error while adding user activity."}), 500
                return jsonify({"status":"success", "message":"Logged in successfully.", "session_data": response_data}), 200
            except VerifyMismatchError:
                activity_status = createUserActivityLogin(ActionType=e_ActionType.LogInFailure.idx, ActionDscr=f"{e_ActionType.LogInFailure.textval} Credential do not match", EntityType=0, EntityID=0, ChangeLog="", UserCode=user.Code)
                if not activity_status:
                    return jsonify({"status":"error", "message":"Error while adding user activity."}), 500
                return jsonify({"status":"error", "message":"Credential do not match."}), 401
        else:
            try:
                verify_password(login_id, password)
                token = create_access_token({"user_name": user.Name, "user_loginid": user.LoginId, "user_type": get_enum_info_by_idx(e_UserType, user.Type)[0]})
                company_info = company_info_formatted()
                response_data = {
                    "access_token": token,
                    "user_name": user.Name,
                    "user_gender": get_enum_info_by_idx(e_Gender, user.Gender)[0],
                    "user_loginid": user.LoginId,
                    "user_code": user.Code,
                    "user_profile_img": f"data:image/jpeg;base64,{base64.b64encode(user.Photo).decode('utf-8')}" if user.Photo else "",
                    "user_type": get_enum_info_by_idx(e_UserType, user.Type)[0],
                    "company_info": company_info
                }
                reset_lockaccnt_count(login_id)
                activity_status = createUserActivityLogin(ActionType=e_ActionType.LogInSuccess.idx, ActionDscr=f"{e_ActionType.LogInSuccess.textval} Logged in successfully", EntityType=e_TranType.Staff.idx, EntityID=user.ID, ChangeLog="", UserCode=user.Code, CrBy=user.Code)
                if not activity_status:
                    return jsonify({"status":"error", "message":"Error while adding user activity."}), 500
                return jsonify({"session_data": response_data}), 200
            except VerifyMismatchError:
                if user.Type != e_UserType.SysAdm.idx:
                    user_lockacc_count = increment_lockaccnt_count(user)
                activity_status = createUserActivityLogin(ActionType=e_ActionType.LogInFailure.idx, ActionDscr=f"{e_ActionType.LogInFailure.textval} Credential do not match", EntityType=e_TranType.Staff.idx, EntityID=user.ID, ChangeLog="", UserCode=user.Code, CrBy=user.Code)
                if not activity_status:
                    return jsonify({"status":"error", "message":"Error while adding user activity."}), 500
                if user.Type != e_UserType.SysAdm.idx:
                    if user_lockacc_count == 5:
                        return jsonify({"status":"error", "message":"Your account has been locked. Please contact system administrator."}), 403
                return jsonify({"status":"error", "message":"Credential do not match."}), 401
    else:
        company_info_obj = get_company_info()
        if company_info_obj is not None:
            company_info = {"company_info":{"status":"success","data":{
                'id': company_info_obj.ID,
                'code': encrypt_decrypt.decrypt_data(company_info_obj.Code),
                'name': encrypt_decrypt.decrypt_data(company_info_obj.Name),
                'logo': f"data:image/jpeg;base64,{base64.b64encode(company_info_obj.Logo).decode('utf-8')}" if company_info_obj.Logo else "",
            }}}
            return jsonify(company_info)
        else:
            return jsonify({"status":"error", "message":"Company info not found"}), 404

@login_required
def getUserInfo():
    current_user = get_user_object(getUserInfo.user_loginid)
    user_ID = current_user.ID
    user_name = current_user.Name
    user_code = current_user.Code
    user_gender = get_enum_info_by_idx(e_Gender, current_user.Gender)[0]
    user_loginid = current_user.LoginId
    user_profile_img = f"data:image/jpeg;base64,{base64.b64encode(current_user.Photo).decode('utf-8')}" if current_user.Photo else ""
    user_type = get_enum_info_by_idx(e_UserType, current_user.Type)[0]

    current_user_info = {
        "ID": user_ID,
        "user_name": user_name,
        "user_code": user_code,
        "user_gender": user_gender,
        "user_loginid": user_loginid,
        "user_profile_img": user_profile_img,
        "user_type": user_type,
    }
    return jsonify(current_user_info)
    
@login_required
def logOut():
    """
    Log out the current user.
    
    **GET**: Clears the session and logs user activity.

    :return: JSON response with status message and HTTP status code 200.
    """
    user = get_user_object(logOut.user_loginid)
    session.clear()
    activity_log = createUserActivity(ActionType=e_ActionType.LogOut.idx, ActionDscr=e_ActionType.LogOut.textval, EntityType=e_TranType.Staff.idx, EntityID=user.ID, ChangeLog="")
    if not activity_log:
        return jsonify({"status":"error", "message":"Error while adding user activity."}), 500
    return jsonify({"status":"success", "message":"Logged out successfully."}), 200

    
#one that admin will use from admin-panel to generate the initial reset password
@admin_or_owner
def resetPasswordAdmin(user_type, login_id):
    """
    Reset password for a user by an admin.

    **POST**: Generates a new initial password for the user and sets the ResetPswd flag.

    :param login_id: Login ID of the user.
    :return: JSON response with new password and status message or status message and appropriate HTTP status code.
    """
    user = get_user_object(login_id)

    if user:
        reset_passwd = generate_initial_password(user)
        ph = PasswordHasher()
        password_hash = ph.hash(reset_passwd)
        session = DBSession()
        user.Pswd = password_hash
        user.ResetPswd = True
        selected_user = set_models_attr.setUpdatedInfo(user)
        session.add(selected_user)
        session.commit()
        session.close()
        return jsonify({"status": {"message": "Password reset successfully. Provide this password to the user to reset their password.", "new_password": reset_passwd}}), 200
    else:
        return jsonify({"status": "Account not found."}), 404

# one that user will use to reset the password
def resetPasswordUser():
    """
    Reset password by the user.

    **POST**: Resets the password if the provided token is valid.

    :return: JSON response with status message and appropriate HTTP status code.
    """
    if request.method == 'POST':
        try:
            user_data = request.get_json()
            login_id = user_data.get('LoginId')
            new_password = user_data.get('ResetPasswd')
            reset_password_token = user_data.get('reset_password_token')

            if not login_id or not new_password or not reset_password_token:
                return jsonify({"status": "error", "message": "LoginId, ResetPasswd, and reset_password_token are required."}), 400

            if reset_password_token == app.config.get(login_id):
                reset_password(login_id, new_password)
                clear_resetpasswd_flag(login_id)
                reset_lockaccnt_count(login_id)
                del app.config[login_id]
                return jsonify({"status": "success", "message": "Password reset successfully."}), 200
            else:
                return jsonify({"status":"error", "message": "Invalid reset password token passed."}), 401

        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message": "Failed to reset password"}), 500
        
@login_required
def changePasswordUser(login_id):
    if request.method == 'POST':
        try:
            user = get_user_object(login_id)
            if user:
                user_data = request.get_json()
                new_password = user_data.get('Pswd')
                reset_password(login_id, new_password)
                return jsonify({"status":"success", "message":"Password change successfully."}), 200
            else:
                return jsonify({"status":"error", "message":"Account not found."}), 404
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":"Failed to change password"}), 500
        
def activateUser(login_id):
    """
    Activate a user account.

    **POST**: Sets the IsActive flag to True for the specified user.

    :param login_id: Login ID of the user.
    :return: JSON response with status message and appropriate HTTP status code.
    """
    user = get_user_object(login_id)
    if user:
        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.Staff.idx, EntityID=user.ID, ChangeLog=f"IsActive: {user.IsActive} => True")
        user.IsActive = True
        session = DBSession()
        session.add(user)
        session.commit()
        session.close()
        return jsonify({"status": "User activated."}), 200
    else:
        return jsonify({"status": "Account not found"}), 404

def deactivateUser(login_id):
    """
    Deactivate a user account.

    **POST**: Sets the IsActive flag to False for the specified user.

    :param login_id: Login ID of the user.
    :return: JSON response with status message and appropriate HTTP status code.
    """
    user = get_user_object(login_id)
    if user:
        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.Staff.idx, EntityID=user.ID, ChangeLog=f"IsActive: {user.IsActive} => False")
        user.IsActive = False
        session = DBSession()
        session.add(user)
        session.commit()
        session.close()
        return jsonify({"status": "User deactivated."}), 200
    else:
        return jsonify({"status": "Account not found."}), 404

@login_required
def deleteUser(login_id):
    """
    Delete a user account.

    **POST**: Removes the user from the database if not associated with any project or task as lead or allocby.

    :param login_id: Login ID of the user.
    :return: JSON response with status message and appropriate HTTP status code.
    """
    session = DBSession()
    loggedin_user = get_user_object(deleteUser.user_loginid)
    user = session.query(StaffMaster).filter(StaffMaster.LoginId == login_id).one_or_none()
    if user:
        try:
            # if project / task is found against the user then don't let user delete
            if user.project_leads or user.project_allocates or user.task_leads or user.task_allocates:
                return jsonify({"status": "error", "message": "User cannot be deleted as they are associated with projects or tasks."}), 400

            # if no project / tasks are found then delete the user
            if not delete_attachments(user.ID, e_TranType.Staff.idx):
                return jsonify({"status":"error", "message":"Error occurred while deleting the attachments."}), 500
            clear_out_notifications_linkage(user.ID, e_TranType.Staff.idx) # first clear the notifications that are linked to the user and then add notification for deletion
            notification_status = generateNotification(
                From=loggedin_user.Code,
                To=[admin_user.Code for admin_user in get_all_admin_users() if admin_user.Code != loggedin_user.Code],
                tranType=e_TranType.Staff.idx,
                tranMID=user.ID,
                Subject=f"User Deleted : {user.Name}",
                Description=f"User {user.Name} : {get_enum_info_by_idx(e_UserType, user.Type)[0]} deleted."
            )
            if not notification_status:
                return jsonify({"status":"error", "message":"Failed to send notification."}), 500
            
            change_log = ""
            ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
            for column in user.__table__.columns:
                if column.name not in ignored_fields:
                    change_log += f"{column.name}: {getattr(user, column.name)} => NaN\n"
            createUserActivity(ActionType=e_ActionType.DeleteRecord.idx, ActionDscr=e_ActionType.DeleteRecord.textval, EntityType=e_TranType.Staff.idx, EntityID=user.ID, ChangeLog=change_log)

            session.delete(user)
            session.commit()
            session.close()
            return jsonify({"status": "User deleted."}), 200
        except IntegrityError:
            session.rollback()
            return jsonify({"status":"error", "message":"User cannot be deleted as they are associated with active projects or tasks."}), 400
        finally:
            session.close()
    else:
        return jsonify({"status": "Account not found"}), 404
    

def get_user_object(login_id, table=StaffMaster):
    """
    Retrieve a user object from the database.

    :param login_id: Login ID of the user.
    :param table: The table to query, defaults to StaffMaster.
    :return: User object or None if not found.
    """
    session = DBSession()
    user_object = session.query(table).filter_by(LoginId=login_id).one_or_none()
    session.close()
    return user_object

def increment_lockaccnt_count(user):
    """
    Increment the account lock count for a user.

    :param user: User object.
    :return: Updated user object.
    """
    session = DBSession()
    user.LockAcnt += 1
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    if user.LockAcnt==5:
        # add notification of account locked
        notification_status = generateNotification(From=user.Code, To=[user.Code for user in get_all_admin_users()], tranType=e_TranType.Staff.idx, tranMID=user.ID, Subject=f"Account Locked : {user.Name}", Description="Account locked as number of attempts exceeded.")
        if not notification_status:
            return jsonify({"status":"error", "message":"Failed to send notification."}), 500
        # add user acitivity of account locked
        activity_status = createUserActivityLogin(ActionType=e_ActionType.LogInFailure.idx, ActionDscr=f"{e_ActionType.LogInFailure.textval} Account locked due to multiple failed attempts", EntityType=0, EntityID=0, ChangeLog="", UserCode=user.Code)
        if not activity_status:
            return jsonify({"status":"error", "message":"Error while adding user activity."}), 500
    return user.LockAcnt

def reset_lockaccnt_count(login_id):
    """
    Reset the account lock count for a user.

    :param login_id: Login ID of the user.
    :return: Updated user object.
    """
    session = DBSession()
    user = session.query(StaffMaster).filter_by(LoginId=login_id).one_or_none()
    user.LockAcnt = 0
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    return user

def clear_resetpasswd_flag(login_id):
    """
    Clear the ResetPswd flag for a user.

    :param login_id: Login ID of the user.
    :return: Updated user object.
    """
    session = DBSession()
    user = session.query(StaffMaster).filter_by(LoginId=login_id).one_or_none()
    user.ResetPswd = False
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    return user

def generate_initial_password(user):
    """
    Generate an initial password for a user based on their name, birth date, and mobile number.

    :param user: User object.
    :return: Generated password as a string.
    """
    try:
        password = user.Name[0:3] + str(user.BirthDt.strftime('%y')) + str(user.BirthDt.strftime('%m')) + user.Mobile[-4:]
    except IndexError:
        password = user.Name + str(user.BirthDt.strftime('%y')) + str(user.BirthDt.strftime('%m')) + user.Mobile[-4:]
    return password

def set_password_locked(user):
    """
    Set the password to 'Locked' for the passed user object.

    :param user: User object whose password needs to be locked.
    """
    session = DBSession()
    ph = PasswordHasher()
    password_hash = ph.hash(app.config['LOCKED_PASSWORD'])
    user.Pswd = password_hash
    session.add(user)
    session.commit()
    session.close()

def reset_password(login_id,password):
    """
    Reset the password for a user.

    :param login_id: Login ID of the user.
    :param password: New password to set.
    """
    session = DBSession()
    user = session.query(StaffMaster).filter_by(LoginId=login_id).one_or_none()
    ph = PasswordHasher()
    password_hash = ph.hash(password)
    user.Pswd = password_hash
    session.add(user)
    session.commit()
    session.close()
    return

def verify_password(login_id, password):
    """
    Verify a user's password.

    :param login_id: Login ID of the user.
    :param password: Password to verify.
    :return: True if password matches, False otherwise.
    """
    ph = PasswordHasher()
    session = DBSession()

    user = session.query(StaffMaster).filter_by(LoginId=login_id).one_or_none()
    if user:
        password_match = ph.verify(user.Pswd, password)
        if ph.check_needs_rehash(user.Pswd):
            user.Pswd = ph.hash(password)
        session.close()
        return password_match
    else:
        return None
    
def add_user(user_obj):
    """
    Add a new user to the database.

    :param user_obj: Dictionary containing user information.
    """
    new_user = StaffMaster()
    
    change_log = ""
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    for key, value in user_obj.items():
        # Skip fields that should be ignored
        if key in ignored_fields:
            continue
        # if key == "Type":
        #     setattr(new_user, key, value)
        # if key == "Pswd":
        #     ph = PasswordHasher()
        #     password_hash = ph.hash(value)        
        #     setattr(new_user, key, password_hash)
        if key == "Photo":
            img_data = value.split(',')[1]
            change_log += f"{key}: NaN => {value}\n"
            setattr(new_user, key, base64.b64decode(img_data))
        elif key in ['BirthDt', 'RelvDt', 'JoinDt']:
            date_value = datetime.strptime(value, "%Y-%m-%d").date()
            if key == 'RelvDt':
                if date_value < date.today():
                    new_user.IsActive = False  # `RelvDt` is in the past
            change_log += f"{key}: NaN => {value}\n"
            setattr(new_user, key, datetime.strptime(value, "%Y-%m-%d").date())
        # elif key in ['CrDtTm', 'LstUpdDtTm']:
        #     setattr(new_user, key, parser.parse(value))
        else:
            change_log += f"{key}: NaN => {value}\n"
            setattr(new_user, key, value)
    
    new_user = set_models_attr.setCreatedInfo(new_user)
    db_session = DBSession()
    # db_session.add(new_user)
    # db_session.commit()
    initial_password = generate_initial_password(new_user)
    setattr(new_user, 'Pswd', PasswordHasher().hash(initial_password)) #store the password with initial generated password
    setattr(new_user, 'ResetPswd', True) #set the reset password flag to True so that user can reset while login
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    db_session.close()
    # Log the user activity
    createUserActivity(ActionType=e_ActionType.AddRecord.idx, ActionDscr=e_ActionType.AddRecord.textval, EntityType=e_TranType.Staff.idx, EntityID=new_user.ID, ChangeLog=change_log)
    return {'initial_password': initial_password, 'user_obj': new_user}

def edit_user_object(selected_user, update_data):
    """
    Edit an existing user in the database.

    :param selected_user: User object to update.
    :param update_data: Dictionary containing updated user information.
    :return: JSON response with status message.
    """
    change_log = ""

    for key, value in update_data.items():
        current_value = getattr(selected_user, key, None)

        if current_value != value:
            if key == "Pswd":
                ph = PasswordHasher()
                password_hash = ph.hash(value)
                change_log += f"{key}: {'NaN' if current_value in [None, '', ' '] else current_value} => {value}\n"
                setattr(selected_user, key, password_hash)

            elif key == "Photo":
                if value == "":
                    if current_value is not None:
                        change_log += f"{key}: {current_value} => 'NaN'\n"
                    setattr(selected_user, key, None)
                else:
                    img_data = value.split(',')[1]
                    new_photo = base64.b64decode(img_data)
                    if current_value != new_photo:
                        change_log += f"{key}: {'NaN' if current_value in [None, '', ' '] else current_value} => {value}\n"
                        setattr(selected_user, key, new_photo)

            elif key in ['BirthDt', 'RelvDt', 'JoinDt']:
                date_value = datetime.strptime(value, "%Y-%m-%d").date()
                if key == 'RelvDt' and date_value < date.today():
                    selected_user.IsActive = False  # `RelvDt` is in the past
                if current_value != date_value:
                    change_log += f"{key}: {'NaN' if current_value in [None, '', ' '] else current_value} => {value}\n"
                    setattr(selected_user, key, date_value)

            elif key in ['Gender', 'Type']:
                enum_type = e_Gender if key == 'Gender' else e_UserType
                # Transform values using `get_enum_info_by_idx`
                old_enum_value = (
                    'NaN' if current_value in [None, '', ' '] else get_enum_info_by_idx(enum_type, int(current_value))
                )
                new_enum_value = get_enum_info_by_idx(enum_type, int(value)) if value not in [None, '', ' '] else 'NaN'
                if old_enum_value[1] != new_enum_value[1]:
                    change_log += f"{key}: {old_enum_value[0]} => {new_enum_value[0]}\n"
                setattr(selected_user, key, value)

            else:
                if current_value in [None, '', ' '] and value in [None, '', ' ']:
                    # Both current and new values are empty or None; no change, no log.
                    pass
                elif current_value not in [None, '', ' '] and value not in [None, '', ' '] and current_value != value:
                    # Both current and new values have data, and they are different.
                    change_log += f"{key}: {current_value} => {value}\n"
                elif current_value in [None, '', ' '] and value not in [None, '', ' ']:
                    # Current value is empty, new value has data.
                    change_log += f"{key}: NaN => {value}\n"
                elif current_value not in [None, '', ' '] and value in [None, '', ' ']:
                    # Current value has data, new value is empty.
                    change_log += f"{key}: {current_value} => NaN\n"

                setattr(selected_user, key, None if value == "" else value)

    # Set `RelvDt` and `JoinDt` to `NaN` if not present in update_data
    for date_key in ['RelvDt', 'JoinDt']:
        if date_key not in update_data:
            current_value = getattr(selected_user, date_key, None)
            if current_value is not None:
                change_log += f"{date_key}: {current_value} => 'NaN'\n"
            setattr(selected_user, date_key, None)

    selected_user = set_models_attr.setUpdatedInfo(selected_user)
    db_session = DBSession()
    db_session.add(selected_user)
    db_session.commit()

    if change_log:
        createUserActivity(
            ActionType=e_ActionType.ChangeRecord.idx,
            ActionDscr=e_ActionType.ChangeRecord.textval,
            EntityType=e_TranType.Staff.idx,
            EntityID=selected_user.ID,
            ChangeLog=change_log,
        )
    db_session.close()
    return jsonify({"status": "success", "message": "User updated successfully."}), 200


def generate_reset_password_token(login_id, token_length=20):
    """
    Generate a reset password token for a user.

    :param login_id: Login ID of the user.
    :param token_length: Length of the generated token, defaults to 20.
    :return: Generated reset password token.
    """
    # Generate a random token using alphanumeric characters
    alphabet = string.ascii_letters + string.digits
    reset_password_token = ''.join(secrets.choice(alphabet) for _ in range(token_length))
    # set the same as app config param to validate while user resetting password
    app.config[login_id] = reset_password_token
    return reset_password_token

@login_required
@admin_or_owner
def listUsers(user_type):
    """
    List all users in the database.

    **GET**: Retrieves a list of all users with their information.

    :return: JSON response with list of users and appropriate HTTP status code.
    """
    try:
        users_object_list = get_users_list(user_type)
        result = []
        for user in users_object_list:
            user_dict = construct_user_dict(user)
            del user_dict['Pswd']
            user_dict["attachment_no"] = len(get_attachments(user.ID, e_TranType.Staff.idx))
            user_dict["notifications"] = {
                "total": len(get_notification_trantype_tranmid(user.ID, e_TranType.Staff.idx)), #return the length of notifications associated with the task
                "unread": len([notification for notification in get_notification_trantype_tranmid(user.ID, e_TranType.Staff.idx) if notification.Status==e_NotificationStatus.Pending.idx and notification.ReadDtTm==None]) #return the length of unread notifications associated with the task
            }
            result.append(user_dict)
        return jsonify(result), 200
    except Exception as e:
        app.logger.error(e)
        abort(500)

def get_users_list(user_type,current_user=None, bypass_check=False):
    """
    Retrieve the list of all users from the database based on the user type.

    :param user_type: The type of user making the request.
    :return: List of user objects or None.
    """
    if bypass_check:
        session = DBSession()
        if user_type == e_UserType.SysAdm.textval:
            users_object_list = session.query(StaffMaster).order_by(func.lower(StaffMaster.Name).asc()).all()
        else:
            users_object_list = session.query(StaffMaster).filter(StaffMaster.Type != e_UserType.SysAdm.idx).order_by(func.lower(StaffMaster.Name).asc()).all()
        session.close()
        return users_object_list
    if current_user:
        current_user_obj = get_user_object(current_user)
        if current_user_obj.Type==e_UserType.Staff.idx:
            return [current_user_obj]
        else:
            session = DBSession()
            if user_type == e_UserType.SysAdm.textval:  # if superuser, then show all users
                users_object_list = session.query(StaffMaster).order_by(func.lower(StaffMaster.Name).asc()).all()
            elif user_type == e_UserType.Admin.textval:  # if admin, then show all users except superusers
                users_object_list = session.query(StaffMaster).filter(StaffMaster.Type != e_UserType.SysAdm.idx).order_by(func.lower(StaffMaster.Name).asc()).all()
            else:  # if staff, then don't show any user
                users_object_list = None
            session.close()
            return users_object_list
    else:
        session = DBSession()
        if user_type == e_UserType.SysAdm.textval:  # if superuser, then show all users
            users_object_list = session.query(StaffMaster).order_by(func.lower(StaffMaster.Name).asc()).all()
        elif user_type == e_UserType.Admin.textval:  # if admin, then show all users except superusers
            users_object_list = session.query(StaffMaster).filter(StaffMaster.Type != e_UserType.SysAdm.idx).order_by(func.lower(StaffMaster.Name).asc()).all()
        else:  # if staff, then don't show any user
            users_object_list = None
        session.close()
        return users_object_list
    
def get_all_admin_users():
    session = DBSession()
    users = session.query(StaffMaster).filter(StaffMaster.Type==e_UserType.Admin.idx).all()
    session.close()
    return users

def construct_user_dict(user):
    """
    Construct a dictionary representing a user.

    :param user: User object.
    :return: Dictionary containing user information.
    """
    user_dict = {}
    for column in inspect(StaffMaster).columns:
        column_name = column.key
        column_value = getattr(user, column_name)
        if column_name == "Photo" and column_value is not None:
            # Decode the base64 URL data for the Photo column
            column_value = f"data:image/jpeg;base64,{base64.b64encode(column_value).decode('utf-8')}" if column_value else ""
        elif column_name == 'Type':
            # Convert enum values to dictionaries containing both textual value and index
            column_value = get_enum_info_by_idx(e_UserType, column_value)
            column_value = {"textval": column_value[0], "idx": column_value[1]}
        elif column_name == 'Gender':
            # Convert enum values to dictionaries containing both textual value and index
            column_value = get_enum_info_by_idx(e_Gender, column_value)
            column_value = {"textval": column_value[0], "idx": column_value[1]}
        elif column_name == 'Pswd':
            pass #don't send Password
        user_dict[column_name] = column_value
    return user_dict

def company_info_formatted():
    company_info = get_company_info()
    if company_info:
        company_info_dict = {
            'id': company_info.ID,
            'code': encrypt_decrypt.decrypt_data(company_info.Code),
            'name': encrypt_decrypt.decrypt_data(company_info.Name),
            'logo': f"data:image/jpeg;base64,{base64.b64encode(company_info.Logo).decode('utf-8')}" if company_info.Logo else "",
        }
    else:
        company_info_dict = {}
    return company_info_dict


@login_required
@admin_or_owner
def editUser(user_type, login_id):
    """
    Edit an existing user.

    **POST**: Updates user information.
    **GET**: Retrieves user information and options for user types and genders.

    :param login_id: Login ID of the user.
    :return: JSON response with status message and appropriate HTTP status code.
    """
    selected_user = get_user_object(login_id)
    if selected_user:
        if request.method == 'POST':
            try:
                updated_data = request.get_json()
                response = edit_user_object(selected_user, updated_data)
                return response
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        else:
            type_gender_optns = {
                "types": enum_to_list(e_UserType),
                "gender": enum_to_list(e_Gender)
            }
            user_dict = {}
            try:
                user_dict = construct_user_dict(selected_user)
                del user_dict["Pswd"]  # don't send password
                user_dict["attachment_no"] = len(get_attachments(selected_user.ID, e_TranType.Staff.idx))
                
                response = {"user_info": user_dict, "type_gender_optns": type_gender_optns}
                return jsonify(response)
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": "User not found"}), 404
    
def get_user_by_code(user_code):
    session = DBSession()
    user = session.query(StaffMaster).filter(StaffMaster.Code == user_code).one_or_none()
    session.close()
    return user