from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists, user_authorized_task, tasklead_user_only, task_allocatedby_user_only
from flask import jsonify, request, session

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.SystemConfig import (SystemConfig as SystemConfig)
from task_trak.db.models.CompanyMaster import (CompanyMaster as CompanyMaster)
from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker

# utils import
from task_trak.common.utils import format_timedelta

# enum imports
from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TaskStatus, e_SubTaskStatus, e_Priority, e_TranType, e_SysConfig

# common imports
from task_trak.common import set_models_attr

from apscheduler.triggers.cron import CronTrigger

from datetime import datetime, timedelta
import math

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

defaults = {
    "allowed_attachment_types": {"value":"bmp, gif, jpg, jpeg, png, ico, mpeg, pdf, doc, docx, docm, rtf, xls, xlsx, csv, txt, zip, rar, 7z, tar, ppt, pptx, mp3, mp4, svg, ttf", "key_description":"File Extensions that are allowed for users to uplaod supportings."},
    "rows_in_single_line": {"value":"15", "key_description":"Number of rows displayed in a single line."},
    "days_for_upcoming_task": {"value":"10", "key_description":"Number of days for upcoming tasks."},
    "report_days_upto": {"value":"60", "key_description":"Maximum number of days for which reports are generated."},
}

@login_required
def checkConfigExists():
    session = DBSession()
    config_exists = session.query(SystemConfig).filter(SystemConfig.Key!= None).all()
    available_keys = [config.Key for config in config_exists]
    data = [config for config in e_SysConfig]
    for config in data:
        if config.Key not in available_keys:
            new_config = SystemConfig()
            new_config.Key = config.Key
            new_config.Value = config.DefVal
            new_config.KeyDescription = config.Dscr
            new_config = set_models_attr.setCreatedInfo(new_config)
            session.add(new_config)
            session.commit()
    session.close()
    current_config = update_global_config_vars()
    return jsonify(current_config)

def update_global_config_vars():
    session = DBSession()
    defaults_data = session.query(SystemConfig).filter(SystemConfig.Key!=None).all()
    session.close()
    # Create a dictionary for quick lookup of the enum values by Key
    config_enum_lookup = {config.Key: config for config in e_SysConfig}
    for config in defaults_data:
        # Get the enum object based on the key
        enum_config = config_enum_lookup.get(config.Key)
        # Use the database value if it's not None, otherwise use the enum default
        app.config[config.Key] = config.Value if config.Value not in ['', None, 0, '0'] else enum_config.DefVal
    result = {
        config.Key: app.config.get(config.Key, config.DefVal)
        for config in e_SysConfig
    }
    return result


@login_required
def listSysConfigs():
    session = DBSession()
    sysconfig_data = session.query(SystemConfig).filter(SystemConfig.Key != None).all()
    company = session.query(CompanyMaster).one_or_none()
    session.close()

    sysconfig_json = {sysconfig.Key: sysconfig.to_dict() for sysconfig in sysconfig_data}
    if company is not None:
        sysconfig_json['AutoNotification'] = company.AutoNotification
    return jsonify({"status": "success", "data": sysconfig_json}), 200


@admin_only #allow developers only to access this
def updateSystemConfigs():
    if request.method == 'POST':
        try:
            sysconfig_data = request.get_json()
            updated_sysconfig = update_sysconfig_data(sysconfig_data)
            if updated_sysconfig is True:
                return jsonify({"status":"success", "message":f"Sysconfig updated successfully."}), 200
            else:
                return jsonify({"status":"error", "message":f"{updated_sysconfig} not found in database."}), 404
        except Exception as e:
            app.logger.error(e)
            return jsonify({"status":"error", "message":f"Sysconfig couldn't be updated."}), 500
    else:
        sysconfig_data_json = get_systemconfig_data()
        return jsonify({"status":"success", "data":sysconfig_data_json}), 200



# model functions
def get_systemconfig_data():
    session = DBSession()
    sysconfig = session.query(SystemConfig).all()
    session.close()
    sysconfig_data_json = [config.to_dict() for config in sysconfig]
    return sysconfig_data_json

def sysconfig_objects(key):
    session = DBSession()
    sysconfig = session.query(SystemConfig).filter(SystemConfig.Key == key).first()
    session.close()
    return sysconfig


def update_sysconfig_data(sysconfigs):
    from task_trak import scheduler
    from task_trak.controllers.companyController import replace_crontab
    crontab_keys = {"Minute", "Hour", "DayOfMonth", "Month", "DayOfWeek"}
    crontab_values = {"Minute": "*", "Hour": "*", "DayOfMonth": "*", "Month": "*", "DayOfWeek": "*"}

    session = DBSession()
    for key, value in sysconfigs.items():
        sysconfig = session.query(SystemConfig).filter(SystemConfig.Key == key).one_or_none()
        if sysconfig:
            if sysconfig.Value != value:
                sysconfig.Value = value
                sysconfig = set_models_attr.setUpdatedInfo(sysconfig)
                session.add(sysconfig)
                session.commit()

                # If the key is a crontab field, update its value in crontab_values
                if key in crontab_keys:
                    crontab_values[key] = value

        else:
            session.close()
            return key

    # If any crontab fields were updated, construct the crontab string and update the scheduler
    if any(crontab_values[key] != "*" for key in crontab_keys):
        crontab_timing = f"{crontab_values['Minute']} {crontab_values['Hour']} {crontab_values['DayOfMonth']} {crontab_values['Month']} {crontab_values['DayOfWeek']}"
        print(f"Updating scheduler with new timing: {crontab_timing}")

        # Replace the existing crontab if scheduler exists
        try:
            new_trigger = CronTrigger(
                minute=crontab_values["Minute"],
                hour=crontab_values["Hour"],
                day=crontab_values["DayOfMonth"],
                month=crontab_values["Month"],
                day_of_week=crontab_values["DayOfWeek"]
            )
            try:
                scheduler.modify_job(job_id="task_notification_job", trigger=new_trigger)
                print(f"Scheduler updated successfully to: {crontab_timing}")
            except Exception as e:
                print(f"Job not found or error modifying scheduler: {e}. Re-adding the job.")
                from task_trak.controllers.notificationsCronJobs import generate_task_notifications
                scheduler.add_job(
                    func=generate_task_notifications,
                    trigger=new_trigger,
                    id="task_notification_job",
                    replace_existing=True,
                )
            print(f"Scheduler updated successfully to: {crontab_timing}")
        except Exception as e:
            print(f"Error updating scheduler: {e}")

    session.close()
    return True
