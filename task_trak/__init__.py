from flask_cors import CORS
from flask_mail import Mail, Message
from flask import Flask, session, jsonify, request
from functools import wraps
from task_trak import config
import logging
from logging.handlers import RotatingFileHandler
import base64

# schedular imports : library + function
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# swagger ui imports
from flask_swagger_ui import get_swaggerui_blueprint

# db imports
from pymongo import MongoClient
import os

# common imports
from task_trak.common import encrypt_decrypt

from argon2 import PasswordHasher

from datetime import date, timedelta, datetime
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError

from task_trak.db.enumerations import e_UserType, get_enum_info_by_idx, e_SysConfig

app = Flask(__name__)

mode = config.user_config['MODE']


#Update Email Config and Create Mail Object
app.config.update(
    # APP SETTING
    BASE_URL=config.user_config['BASE_URL'],
    #EMAIL SETTINGS
    MAIL_SERVER=config.user_config['MAIL_SERVER'],
    MAIL_PORT=config.user_config['MAIL_PORT'],
    MAIL_USE_SSL=config.user_config['MAIL_USE_SSL'],
    MAIL_USERNAME = config.user_config['MAIL_USERNAME'],
    MAIL_DEFAULT_SENDER = config.user_config['MAIL_DEFAULT_SENDER'],
    MAIL_PASSWORD = config.user_config['MAIL_PASSWORD'],
    LOCKED_PASSWORD = config.user_config['LOCKED_PASSWORD'],
    ATTACHMENT_UPLOAD_SIZE = config.user_config['ATTACHMENT_UPLOAD_SIZE'],
    # SECRET KEY SETTINGS
    APP_SECRET_KEY = config.user_config['APP_SECRET_KEY'],
    JWT_SECRET_KEY = config.user_config['JWT_SECRET_KEY']
)

if mode == 'PRODUCTION':
    app.config.update(
        # Application cofigurations here
        BASE_URL = "https://axayp.pythonanywhere.com/", #deployed url here for production
        LOCKED_PASSWORD = config.user_config['LOCKED_PASSWORD'],
        # SECRET KEY SETTINGS
        APP_SECRET_KEY = os.environ.get('APP_SECRET_KEY'),
        JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    )

mail=Mail(app)

# Add MongoDB configuration
def get_db():
    client = MongoClient(os.environ.get('DATABASE_URL'))
    db = client.get_default_database()
    return db

# Allow CORS for all routes
# CORS(app)
# Allow CORS for a specific route
CORS(app, resources={r"/*": {"origins": "*"}})

def create_access_token(user_data):
    """Create JWT access token for user"""
    try:
        payload = {
            'sub': str(user_data),
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')
        return token
    except Exception as e:
        app.logger.error(f"Error creating access token: {e}")
        return None


# created in order to generate the refresh token when access token expires
# def create_refresh_token(subject: Union[str, Any], expires_delta: int = config.settings.REFRESH_TOKEN_EXPIRE_MINUTES) -> str:
#     try:
#         expires_delta = datetime.utcnow() + timedelta(minutes=expires_delta)
#         to_encode = {"exp": expires_delta, "sub": str(subject)}
#         encoded_jwt = jwt.encode(
#             to_encode, config.settings.JWT_REFRESH_SECRET_KEY, config.settings.ALGORITHM)
#         return encoded_jwt
#     except Exception as e:
#         return str(e)


def verify_access_token(jwt_token):
    try:
        decoded_jwt = jwt.decode(
            jwt_token, app.config['JWT_SECRET_KEY'], 'HS256')
        # print(decoded_jwt)
        return {'verified': True, 'user_info': decoded_jwt['sub']}
    except (ExpiredSignatureError, Exception, InvalidSignatureError) as e:
        return {'verified': False, 'user_info': ''}

# common functions and flask filters
def get_db_session():
    return get_db()
    
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            bearer_token = request.headers.get('Authorization')
            if not bearer_token:
                return jsonify({"status":"error", "message":"missing_token"}), 401

            token = bearer_token.split()[1]

            verification = verify_access_token(token)
            if not verification["verified"]:
                return jsonify({"status":"error", "message":"invalid_token"}), 401

            user_data = eval(verification["user_info"])
            if 'user_type' not in user_data:
                return jsonify({"status":"error", "message":"You're not logged in."}), 401
            decorated_function.user_type = user_data['user_type']
            decorated_function.user_loginid = user_data['user_loginid']

            return f(*args, **kwargs)

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            bearer_token = request.headers.get('Authorization')
            if not bearer_token:
                return jsonify({"status":"error", "message":"missing_token"}), 401

            token = bearer_token.split()[1]

            verification = verify_access_token(token)
            if not verification["verified"]:
                return jsonify({"status":"error", "message":"invalid_token"}), 401

            user_data = eval(verification["user_info"])
            if user_data["user_type"] != e_UserType.SysAdm.textval:
                return jsonify({"status":"error", "message":"Accessible to admins only"}), 403

            return f(*args, **kwargs)

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def owner_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            bearer_token = request.headers.get('Authorization')
            if not bearer_token:
                return jsonify({"status":"error", "message":"missing_token"}), 401

            token = bearer_token.split()[1]

            verification = verify_access_token(token)
            if not verification["verified"]:
                return jsonify({"status":"error", "message":"invalid_token"}), 401

            user_data = eval(verification["user_info"])
            if user_data["user_type"] != e_UserType.Admin.textval:
                return jsonify({"status":"error", "message":"Accessible to owners only."}), 403

            return f(*args, **kwargs)

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def admin_or_owner(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            bearer_token = request.headers.get('Authorization')
            if not bearer_token:
                return jsonify({"status":"error", "message":"missing_token"}), 401

            token = bearer_token.split()[1]

            verification = verify_access_token(token)
            if not verification["verified"]:
                return jsonify({"status":"error", "message":"invalid_token"}), 401

            user_data = eval(verification["user_info"])
            if user_data["user_type"] not in [e_UserType.SysAdm.textval, e_UserType.Admin.textval]:
                return jsonify({"status":"error", "message":"Accessible to admin/owners only."}), 403

            return f(user_data["user_type"], *args, **kwargs)

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def admin_or_owner_on_post(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'POST':
            try:
                bearer_token = request.headers.get('Authorization')
                if not bearer_token:
                    return jsonify({"status": "error", "message": "missing_token"}), 401

                token = bearer_token.split()[1]

                verification = verify_access_token(token)
                if not verification["verified"]:
                    return jsonify({"status": "error", "message": "invalid_token"}), 401

                user_data = eval(verification["user_info"])
                if user_data["user_type"] not in [e_UserType.SysAdm.textval, e_UserType.Admin.textval]:
                    return jsonify({"status": "error", "message": "Accessible to admin/owners only."}), 403

                return f(user_data["user_type"], *args, **kwargs)

            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500

        # For non-POST requests, pass user_type as None
        return f(None, *args, **kwargs)

    return decorated_function


def system_admin_exists(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.StaffMaster import StaffMaster
            from task_trak.common import set_models_attr

            db_session = get_db_session()
            admin_users = list(db_session.find({"Type": e_UserType.SysAdm.idx}))

            # If no admin user is there then create one and proceed ahead
            if not admin_users:
                admin_user = {
                    "Type": e_UserType.SysAdm.idx,
                    "Code": 'SysAdm',
                    "Name": 'SysAdm',
                    "LoginId": 'SysAdm',
                    "EmailID": 'SysAdm@trimaxinfotech.com',
                    "Pswd": PasswordHasher().hash('SysAdm@321'),
                    "Mobile": '9408697497',
                    "BirthDt": date(1947, 8, 15),
                    "Photo": None,
                    "ResetPswd": False
                }
                db_session.insert_one(admin_user)

            return f(*args, **kwargs)

        except Exception as e:
            from task_trak.controllers.companyController import get_company_info
            app.logger.error(e)
            company_info_obj = get_company_info()
            # {company_info: {status:data,message:sds,detail:sdsd},sysAdmin_status:{status:sdfdf,message:"sdsd"}}
            # return jsonify({"status": "error", "message": "Unable to add defaults.", "company_info":"data:image/jpeg;base64," + base64.b64encode(company_info_obj.Logo).decode('utf-8')}), 500
            if company_info_obj is None:
                return jsonify({"system_admin":{"status":"error", "message":"Unable to add defaults."}, "company_info":{"status":"error", "message":"Company Not found.", "data":""}}), 404
            return jsonify({"system_admin":{"status":"error", "message":"Unable to add defaults."}, "company_info":{"status":"success", "data":f"data:image/jpeg;base64,{str(base64.b64encode(company_info_obj.Logo).decode('utf-8'))}" if company_info_obj.Logo else ""}})

    return decorated_function

def company_info_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.CompanyMaster import CompanyMaster
            
            db_session = get_db_session()
            company_master = db_session.find_one({"_id": 1})  # MongoDB syntax
            
            if company_master is not None:
                company_info = {
                    'id': company_master.get('_id'),
                    'code': encrypt_decrypt.decrypt_data(company_master.get('Code', '')),
                    'name': encrypt_decrypt.decrypt_data(company_master.get('Name', '')),
                    'logo': f"data:image/jpeg;base64,{base64.b64encode(company_master.get('Logo', b'')).decode('utf-8')}" if company_master.get('Logo') else "",
                }
                return f(company_info, *args, **kwargs)
            else:
                return jsonify({"company_info":{"status":"success", "message": "Company's info not found."}}), 404
        except Exception as e:
            app.logger.error(e)
            return jsonify({"company_info":{"status": "error", "message": "Something went wrong while fetching Company's info."}}), 500

    return decorated_function

def user_authorized_project(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.StaffMaster import StaffMaster
            from task_trak.db.models.ProjectTransaction import ProjectTransaction
            from task_trak.db.models.TaskTransaction import TaskTransaction  # Import TaskTransaction model
            
            project_id = kwargs['project_id']
            bearer_token = request.headers.get('Authorization')
            token = bearer_token.split()[1]
            verification = verify_access_token(token)
            user_data = eval(verification["user_info"])

            session = get_db_session()
            
            # Get user and project objects
            user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
            project_obj = session.query(ProjectTransaction).filter(ProjectTransaction.ID == int(project_id)).first()
            
            if not user_obj or not project_obj:
                session.close()
                return jsonify({"status": "error", "message": "Requested Project is not found."}), 404

            # Check if user is the project lead, allocated by, or has admin/system admin rights
            if user_obj.Code in [project_obj.ProjLead, project_obj.AllocBy] or user_obj.Type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx]:
                session.close()
                return f(*args, **kwargs)

            # Check if the user is a task lead for any tasks within the project
            task_lead = session.query(TaskTransaction).filter(
                TaskTransaction.ProjTranID == project_id,
                TaskTransaction.TaskLead == user_obj.Code
            ).first()

            session.close()

            if task_lead:  # If user is task lead for any task within the project, grant access
                return f(*args, **kwargs)
            else:
                return jsonify({"status": "error", "message": "You are not authorized to access this project."}), 403

        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function


def project_allocby_or_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.StaffMaster import StaffMaster
            from task_trak.db.models.ProjectTransaction import ProjectTransaction
            project_id = kwargs['project_id']
            bearer_token = request.headers.get('Authorization')
            token = bearer_token.split()[1]
            verification = verify_access_token(token)
            user_data = eval(verification["user_info"])
            # table_obj.LstUpdDtTm = datetime.now()
            session = get_db_session()
            user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
            project_obj = session.query(ProjectTransaction).filter(ProjectTransaction.ID == int(project_id)).first()
            session.close()
            
            if user_obj and project_obj:
                if user_obj.Code == project_obj.AllocBy or user_obj.Type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx]:
                    return f(*args, **kwargs)
                else:
                    return jsonify({"status": "error", "message": "You are not authorized to access this project."}), 403
            else:
                return jsonify({"status": "error", "message": "Requested Project is not found."}), 404
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def user_authorized_task(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.StaffMaster import StaffMaster
            from task_trak.db.models.TaskTransaction import TaskTransaction
            from task_trak.db.models.ProjectTransaction import ProjectTransaction
            task_id = kwargs['task_id']
            bearer_token = request.headers.get('Authorization')
            token = bearer_token.split()[1]
            verification = verify_access_token(token)
            user_data = eval(verification["user_info"])
            session = get_db_session()
            user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
            task_obj = session.query(TaskTransaction).filter(TaskTransaction.ID == int(task_id)).first()
            
            if user_obj and task_obj:
                authorized = False
                if user_obj.Code in [task_obj.TaskLead, task_obj.AllocBy] or user_obj.Type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx]:
                    authorized = True
                elif task_obj.ProjTranID:
                    project_obj = session.query(ProjectTransaction).filter(ProjectTransaction.ID == task_obj.ProjTranID).first()
                    if project_obj and user_obj.Code in [project_obj.ProjLead, project_obj.AllocBy]:
                        authorized = True
                
                session.close()
                
                if authorized:
                    return f(*args, **kwargs)
                else:
                    return jsonify({"status": "error", "message": "You are not authorized to access this task."}), 403
            else:
                session.close()
                return jsonify({"status": "error", "message": "Requested Task is not found."}), 404
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def user_authorized_subtask(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.StaffMaster import StaffMaster
            from task_trak.db.models.SubTaskTransaction import SubTaskTransaction
            from task_trak.controllers.taskTxnController import get_task_object
            subtask_id = kwargs['subtask_id']
            bearer_token = request.headers.get('Authorization')
            token = bearer_token.split()[1]
            verification = verify_access_token(token)
            user_data = eval(verification["user_info"])
            # table_obj.LstUpdDtTm = datetime.now()
            session = get_db_session()
            user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
            subtask_obj = session.query(SubTaskTransaction).filter(SubTaskTransaction.ID == int(subtask_id)).first()
            session.close()
            
            parent_task = get_task_object(subtask_obj.TaskTranID)
            
            if request.method == "GET":
                if user_obj.Code in [parent_task.TaskLead, parent_task.AllocBy, subtask_obj.SubTaskLead, subtask_obj.AllocBy] or user_obj.Type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx]:
                    return f(*args, **kwargs)
                else:
                    return jsonify({"status": "error", "message": "You are not authorized to access this SubTask."}), 403
            if request.method == "POST":
                if user_obj and subtask_obj:
                    if user_obj.Code in [subtask_obj.SubTaskLead, parent_task.TaskLead] or user_obj.Type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx]:
                        return f(*args, **kwargs)
                    else:
                        return jsonify({"status": "error", "message": "You are not authorized to access this SubTask."}), 403
                else:
                    return jsonify({"status": "error", "message": "Requested SubTask is not found."}), 404
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def tasklead_or_allocby_user_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.StaffMaster import StaffMaster
            from task_trak.db.models.TaskTransaction import TaskTransaction
            task_id = kwargs['task_id']
            bearer_token = request.headers.get('Authorization')
            token = bearer_token.split()[1]
            verification = verify_access_token(token)
            user_data = eval(verification["user_info"])
            # table_obj.LstUpdDtTm = datetime.now()
            session = get_db_session()
            user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
            task_obj = session.query(TaskTransaction).filter(TaskTransaction.ID == int(task_id)).first()
            session.close()
            
            if user_obj and task_obj:
                if user_obj.Code in [task_obj.TaskLead, task_obj.AllocBy] or user_obj.Type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx]:
                    return f(*args, **kwargs)
                else:
                    return jsonify({"status": "error", "message": "You are not Task Lead of current Task."}), 403
            else:
                return jsonify({"status": "error", "message": "Requested Task is not found."}), 404
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def tasklead_user_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.StaffMaster import StaffMaster
            from task_trak.db.models.TaskTransaction import TaskTransaction
            task_id = kwargs['task_id']
            bearer_token = request.headers.get('Authorization')
            token = bearer_token.split()[1]
            verification = verify_access_token(token)
            user_data = eval(verification["user_info"])
            # table_obj.LstUpdDtTm = datetime.now()
            session = get_db_session()
            user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
            task_obj = session.query(TaskTransaction).filter(TaskTransaction.ID == int(task_id)).first()
            session.close()
            
            if user_obj and task_obj:
                if user_obj.Code == task_obj.TaskLead or user_obj.Type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx]:
                    return f(*args, **kwargs)
                else:
                    return jsonify({"status": "error", "message": "You are not Task Lead of current Task."}), 403
            else:
                return jsonify({"status": "error", "message": "Requested Task is not found."}), 404
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def task_allocatedby_user_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.StaffMaster import StaffMaster
            from task_trak.db.models.TaskTransaction import TaskTransaction
            from task_trak.db.models.ProjectTransaction import ProjectTransaction
            task_id = kwargs['task_id']
            bearer_token = request.headers.get('Authorization')
            token = bearer_token.split()[1]
            verification = verify_access_token(token)
            user_data = eval(verification["user_info"])
            session = get_db_session()
            user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
            task_obj = session.query(TaskTransaction).filter(TaskTransaction.ID == int(task_id)).first()
            
            if user_obj and task_obj:
                is_admin = user_data["user_type"] in [e_UserType.SysAdm.textval, e_UserType.Admin.textval]
                is_allocby = user_obj.Code == task_obj.AllocBy
                
                if task_obj.ProjTranID:
                    project_obj = session.query(ProjectTransaction).filter(ProjectTransaction.ID == task_obj.ProjTranID).first()
                    is_projlead = user_obj.Code == project_obj.ProjLead if project_obj else False
                    
                    if is_admin or is_allocby or is_projlead:
                        decorated_function.user_loginid = user_data['user_loginid']
                        session.close()
                        return f(*args, **kwargs)
                else:
                    if is_admin or is_allocby:
                        decorated_function.user_loginid = user_data['user_loginid']
                        session.close()
                        return f(*args, **kwargs)
                
                session.close()
                return jsonify({"status": "error", "message": "You don't have permission to access this task."}), 403
            else:
                session.close()
                return jsonify({"status": "error", "message": "Requested Task is not found."}), 404
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

def subtask_allocatedby_user_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            from task_trak.db.models.StaffMaster import StaffMaster
            from task_trak.db.models.SubTaskTransaction import SubTaskTransaction
            task_id = kwargs['subtask_id']
            bearer_token = request.headers.get('Authorization')
            token = bearer_token.split()[1]
            verification = verify_access_token(token)
            user_data = eval(verification["user_info"])
            # table_obj.LstUpdDtTm = datetime.now()
            session = get_db_session()
            user_obj = session.query(StaffMaster).filter(StaffMaster.LoginId == user_data["user_loginid"]).first()
            subtask_obj = session.query(SubTaskTransaction).filter(SubTaskTransaction.ID == int(task_id)).first()
            session.close()
            
            if user_obj and subtask_obj:
                if user_obj.Code == subtask_obj.AllocBy:
                    return f(*args, **kwargs)
                else:
                    return jsonify({"status": "error", "message": "You have not allocated this task."}), 403
            else:
                return jsonify({"status": "error", "message": "Requested SubTask is not found."}), 404
                
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return decorated_function

# schedular script
# Initialize APScheduler
def setup_scheduler():
    from task_trak.controllers.notificationsCronJobs import generate_task_notifications
    from task_trak.controllers.systemConfigController import sysconfig_objects
    scheduler = BackgroundScheduler()

    # Schedule a job using a cron-like trigger
    trigger = CronTrigger(
        day=sysconfig_objects(e_SysConfig.DayOfMonth.Key).Value,  # Every day
        hour=sysconfig_objects(e_SysConfig.Hour.Key).Value,  # At 9 AM
        minute=sysconfig_objects(e_SysConfig.Minute.Key).Value,  # At 0 minutes
        month=sysconfig_objects(e_SysConfig.Month.Key).Value,  # Every month
        day_of_week=sysconfig_objects(e_SysConfig.DayOfWeek.Key).Value,  # Every day of the week
    )

    # Add the job to the scheduler
    scheduler.add_job(
        func=generate_task_notifications,
        trigger=trigger,
        id="task_notification_job",  # Unique identifier for the job
        replace_existing=True,
    )

    # Start the scheduler
    scheduler.start()
    print("Scheduler started.")
    return scheduler

# Set up the scheduler when the app starts
# @app.before_first_request
# def start_scheduler():
#     setup_scheduler()

# Start the scheduler when the app starts
if os.environ.get("WERKZEUG_RUN_MAIN") == "true":  # Prevent duplicate scheduler in debug mode
    scheduler = setup_scheduler()

import task_trak.modules.base_app
import task_trak.modules.attachments
import task_trak.modules.dashboards
import task_trak.modules.staff
import task_trak.modules.company
import task_trak.modules.project_template
import task_trak.modules.project_transaction
import task_trak.modules.task_template
import task_trak.modules.task_transaction
import task_trak.modules.subtask_template
import task_trak.modules.subtask_transaction
import task_trak.modules.reports
import task_trak.modules.system_config
import task_trak.modules.communication_center
import task_trak.modules.user_activity

# import task status cron job
import task_trak.controllers.notificationsCronJobs

# Create a rotating file handler
file_handler = RotatingFileHandler('syslog.log', maxBytes=10240, backupCount=10)
file_handler.setLevel(logging.DEBUG)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create a formatter and set it for the handlers
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the app's logger
app.logger.addHandler(file_handler)
app.logger.addHandler(console_handler)
app.logger.setLevel(logging.DEBUG)

# swagger specific code
SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'

SWAGGERUI_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': 'TaskTrak',
        'app_url': app.config['BASE_URL'],
        'doc_expansion': 'list',
        }
    )

app.register_blueprint(SWAGGERUI_BLUEPRINT, url_prefix=SWAGGER_URL)
