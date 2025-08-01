from task_trak import app, admin_only, admin_or_owner
from flask import jsonify, request, session

# model imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.CompanyMaster import (CompanyMaster as CompanyMaster)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from task_trak.controllers.attachmentController import get_attachments
from task_trak.controllers.userActivityController import createUserActivity

# enum imports
from task_trak.db.enumerations import e_TranType, e_ActionType

# common imports
from task_trak.common import set_models_attr, encrypt_decrypt

import base64
import subprocess
# from dateutil import parser

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@admin_only
@admin_or_owner
def addCompanyInfo(user_type):
    """
    Adds company information to the database.

    :return: A JSON response containing the company data or an error message.
    :rtype: flask.Response
    """
    try:
        company_data = request.get_json()
        add_company_info(company_data)
        return jsonify(company_data), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@admin_or_owner
def editCompanyInfo(user_type):
    """
    Edits company information in the database.

    :return: A JSON response containing the updated company data or an error message.
    :rtype: flask.Response
    """
    try:
        current_info = get_company_info()
        if request.method == 'POST':
            change_data = request.get_json()
            change_company_info(current_info, change_data)
            return jsonify(change_data), 200
        else:
            if current_info:
                response = {
                    "Code": encrypt_decrypt.decrypt_data(current_info.Code),
                    "Name": encrypt_decrypt.decrypt_data(current_info.Name),
                    "Logo": f"data:image/jpeg;base64,{base64.b64encode(current_info.Logo).decode('utf-8')}" if current_info.Logo else "",
                    "Addr1": current_info.Addr1,
                    "Addr2": current_info.Addr2,
                    "Area": current_info.Area,
                    "City": current_info.City,
                    "Pincode": current_info.Pincode,
                    "Country": current_info.Country,
                    "Phone": current_info.Phone,
                    "Mobile": current_info.Mobile,
                    "EMail": current_info.EMail,
                    "WebAddr": current_info.WebAddr,
                    "AutoNotification": current_info.AutoNotification,
                    "Other1": current_info.Other1,
                    "Other2": current_info.Other2,
                    "CrDtTm": current_info.CrDtTm,
                    "CrFrom": current_info.CrFrom,
                    "CrBy": current_info.CrBy,
                    "LstUpdDtTm": current_info.LstUpdDtTm,
                    "LstUpdBy": current_info.LstUpdBy,
                    "LstUpdFrom": current_info.LstUpdFrom,
                    "attachments_no": len(get_attachments(current_info.ID, e_TranType.Company.idx)) #return the length of attachments associated with the task
                }
                return jsonify(response), 200
            else:
                return jsonify({"status": "error", "message": "Company info not found."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def get_company_info():
    """
    Retrieves the company information from the database.

    :return: The company information.
    :rtype: CompanyMaster
    """
    session = DBSession()
    company = session.query(CompanyMaster).first()
    session.close()
    return company

def add_company_info(company_data):
    """
    Adds company information to the database.

    :param company_data: A dictionary containing the company information.
    :type company_data: dict
    """
    changelog = []
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}

    company = CompanyMaster()
    for key, value in company_data.items():
        # Skip the field if it's in the ignored fields set
        if key in ignored_fields:
            continue
        if value: #if value is there then only save the data otherwise whatsoever is there set as default in db_models will be overwritten by empty string
            if key == "Logo":
                img_data = value.split(',')[1]
                setattr(company, key, base64.b64decode(img_data))
            elif key in ['Code', 'Name']:
                setattr(company, key, encrypt_decrypt.encrypt_data(value))
            else:
                setattr(company, key, value)
            changelog.append(f"{key}: None => {value}")
    company = set_models_attr.setCreatedInfo(company)
    db_session = DBSession()
    db_session.add(company)
    db_session.commit()
    createUserActivity(ActionType=e_ActionType.AddRecord.idx, ActionDscr=e_ActionType.AddRecord.textval, EntityType=e_TranType.Company.idx, EntityID=company.ID, ChangeLog="\n".join(changelog))
    db_session.close()
    return

def change_company_info(current_info, change_data):
    """
    Updates the company information in the database.

    :param current_info: The current company information.
    :type current_info: CompanyMaster
    :param change_data: A dictionary containing the updated company information.
    :type change_data: dict
    """
    ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom'}
    changelog = []

    for key, value in change_data.items():
        if key in ignored_fields:
            continue

        old_value = getattr(current_info, key)
        
        if key == "Logo":
            if value == "":
                if old_value is not None:
                    changelog.append(f"{key}: {old_value} => None")
                setattr(current_info, key, None)
            else:
                if old_value is None:
                    # No existing logo, just set the new one
                    img_data = value.split(',')[1]
                    setattr(current_info, key, base64.b64decode(img_data))
                    changelog.append(f"{key}: None => {value}")
                else:
                    # Compare existing logo with new logo
                    converted_old_value = base64.b64encode(old_value).decode('utf-8')
                    converted_new_value = base64.b64encode(base64.b64decode(value.split(',')[1])).decode('utf-8')
                    if converted_old_value != converted_new_value:
                        changelog.append(f"{key}: {converted_old_value} => {converted_new_value}")
                        setattr(current_info, key, base64.b64decode(value.split(',')[1]))

        elif key in ['Code', 'Name']:
            if old_value is None:
                # No existing value, just encrypt and set
                encrypted_new_value = encrypt_decrypt.encrypt_data(value)
                setattr(current_info, key, encrypted_new_value)
                changelog.append(f"{key}: None => {value}")
            else:
                # Compare decrypted old value with new value
                converted_old_value = encrypt_decrypt.decrypt_data(old_value)
                if converted_old_value != value:
                    encrypted_new_value = encrypt_decrypt.encrypt_data(value)
                    changelog.append(f"{key}: {converted_old_value} => {value}")
                    setattr(current_info, key, encrypted_new_value)
        
        elif key == "AutoNotification":
            save_value = True if value=='true' else False
            if old_value != save_value:
                changelog.append(f"{key}: {old_value} => {save_value}")
            setattr(current_info, key, save_value)

        else:
            if old_value in [None, '', ' '] and value in [None, '', ' ']:
                # Both current and new values are empty or None; no change, no log.
                pass
            elif old_value not in [None, '', ' '] and value not in [None, '', ' '] and old_value != value:
                # Both current and new values have data, and they are different.
                changelog.append(f"{key}: {old_value} => {value}")
            elif old_value in [None, '', ' '] and value not in [None, '', ' ']:
                # Current value is empty, new value has data.
                changelog.append(f"{key}: NaN => {value}")
            elif old_value not in [None, '', ' '] and value in [None, '', ' ']:
                # Current value has data, new value is empty.
                changelog.append(f"{key}: {old_value} => NaN")
            setattr(current_info, key, value)

    current_info = set_models_attr.setUpdatedInfo(current_info)
    
    db_session = DBSession()
    db_session.add(current_info)
    db_session.commit()

    if changelog:
        createUserActivity(
            ActionType=e_ActionType.ChangeRecord.idx,
            ActionDscr=e_ActionType.ChangeRecord.textval,
            EntityType=e_TranType.Company.idx,
            EntityID=current_info.ID,
            ChangeLog="\n".join(changelog)
        )
    db_session.close()

def replace_crontab(new_cronjob_schedule):
    """
    Replace the existing crontab with a single new cron job.

    :param new_cronjob: The new cron job to set (e.g., "* * * * * echo 'Hello World'")
    """
    # Create the new crontab content
    cronjob_cmd = 'cd "/Users/macbookpro/Feelancing Projects/tasktrack-backend/task_trak" && "/Users/macbookpro/Feelancing Projects/tasktrack-backend/.env/bin/flask" generate_task_notifications >> generate_task_notifications_job.log 2>&1'
    new_crontab_content = f"{new_cronjob_schedule } {cronjob_cmd}\n"

    # Apply the new crontab
    process = subprocess.run(['crontab'], input=new_crontab_content, text=True)
    if process.returncode == 0:
        print("Crontab replaced successfully.")
    else:
        print("Failed to update crontab.")

# if __name__ == "__main__":
    # Example usage
    # old_timing = "* * * * *"
    # new_timing = "0 5 * * *"  # Change to run daily at 5:00 AM
    # command = 'cd "/Users/macbookpro/Feelancing Projects/tasktrack-backend/task_trak" && "/Users/macbookpro/Feelancing Projects/tasktrack-backend/.env/bin/flask" generate_task_notifications >> generate_task_notifications_job.log 2>&1'

    # update_cronjob_timing(old_timing, new_timing, command)

