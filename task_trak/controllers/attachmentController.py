#Controller Imports
from task_trak import app, admin_only, admin_or_owner, login_required, company_master_exists, system_admin_exists
from flask import jsonify, request, session

#Model Imports
from task_trak.db.database_setup import (Base as Base)
from task_trak.db.models.StaffMaster import (StaffMaster as StaffMaster)
from task_trak.db.models.AttachmentDetails import (AttachmentDetails as AttachmentDetails)
from task_trak.db.models.ProjectTemplate import (ProjectTemplate as ProjectTemplate)
from task_trak.db.models.ProjectTransaction import (ProjectTransaction as ProjectTransaction)
from task_trak.db.models.TaskTemplate import (TaskTemplate as TaskTemplate)
from task_trak.db.models.TaskTransaction import (TaskTransaction as TaskTransaction)
from task_trak.db.models.SubTaskTemplate import (SubTaskTemplate as SubTaskTemplate)
from task_trak.db.models.SubTaskTransaction import (SubTaskTransaction as SubTaskTransaction)
from sqlalchemy import create_engine, func, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from task_trak.controllers.systemConfigController import get_systemconfig_data
from task_trak.controllers.userActivityController import createUserActivity

# flask imports
from flask import session, send_file, send_from_directory, request, redirect, render_template, url_for, flash
import datetime
from werkzeug.utils import secure_filename
import os

# Model imports
from task_trak.db.models.SystemConfig import (SystemConfig as SystemConfig)

# common imports
from task_trak.common import set_models_attr

# import enums
from task_trak.db.enumerations import e_SysConfig, e_TranType, e_AttachTye, e_ActionType, get_enum_info_by_idx

from datetime import datetime, timedelta
from dateutil.tz import *
import pytz
import json

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

max_attachment_size = None
allowed_attachment_extensions = None

# upload the file
@login_required
def uploadAttachment():
    global max_attachment_size, allowed_attachment_extensions  # Declare global to update them
    session = DBSession()
    max_attachment_size = session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.MaxAttachSize.Key).first().Value
    allowed_attachment_extensions = session.query(SystemConfig).filter(SystemConfig.Key == e_SysConfig.AllowAttchExtn.Key).first().Value
    session.close()

    if 'file' not in request.files or request.files['file'].filename == '':
        return jsonify({'status':'error','message': 'No file part in the request'}), 400
    
    file = request.files['file']
    
    # Check if the file extension is allowed
    if not allowed_file(file.filename):
        return jsonify({'status':'error','message': 'Uploaded file type is not supported'}), 400
    
    # if uploaded file size is more than 100MB then don't allow
    if file.content_length > int(max_attachment_size):  # 100 MB in bytes
        return jsonify({'status':'error','message': 'Attachments up to size of 100MB can only be uploaded'}), 400

    attachment_id = add_attachment(request)
    if attachment_id:

        return jsonify({'status':'success','message': f'File successfully uploaded', 'data':str(attachment_id)}), 200
    else:
        return jsonify({'status':'error','message': 'Failed to upload file'}), 500

@login_required
def editAttachment(attachment_id):
    if request.method == 'GET':
        session = DBSession()
        try:
            attachment = session.query(AttachmentDetails).filter_by(ID=attachment_id).one_or_none()
            if not attachment:
                return jsonify({'status': 'error', 'message': 'Attachment not found'}), 404
            attachment_info = attachment.to_dict()
            return jsonify({'status': 'success', 'data': attachment_info}), 200
        except Exception as e:
            app.logger.error(e)
            return jsonify({'status': 'error', 'message': 'Failed to retrieve attachment info'}), 500
        finally:
            session.close()
    elif request.method == 'POST':
        # if 'file' not in request.files or request.files['file'].filename == '':
        #     return jsonify({'status':'error','message': 'No file part in the request'}), 400
        
        # file = request.files['file']
        
        # # Check if the file extension is allowed
        # if not allowed_file(file.filename):
        #     return jsonify({'status':'error','message': 'Uploaded file type is not supported'}), 400
        
        # # if uploaded file size is more than 100MB then don't allow
        # if file.content_length > app.config['ATTACHMENT_UPLOAD_SIZE']:  # 100 MB in bytes
        #     return jsonify({'status':'error','message': 'Attachments up to size of 100MB can only be uploaded'}), 400

        try:
            attachment_edit_status = edit_attachment(request, attachment_id)

            if attachment_edit_status:
                return jsonify({'status':'success','message': 'File successfully updated'}), 200
            else:
                return jsonify({'status':'error','message': 'Failed to update file'}), 500
        except Exception as e:
            app.logger.error(e)
            return jsonify({'status':'error','message': 'Failed to update file'}), 500
    else:
        return jsonify({'status': 'error', 'message': 'Invalid request method'}), 405

@login_required
def getAttachment():
    tran_type = request.args.get('TranType')
    tran_mid = request.args.get('TranMID')
    attch_type = request.args.get('AttchType')
    print(attch_type, tran_mid, attch_type)

    if not tran_type or not tran_mid or not attch_type:
        return jsonify({'status':'error','message': 'TranType, TranMID, and AttchType are required parameters'}), 400

    session = DBSession()
    try:
        if attch_type and attch_type!='0':
            attachments = session.query(AttachmentDetails).filter_by(TranType=tran_type, TranMID=tran_mid, AttchType=attch_type).order_by(func.lower(AttachmentDetails.FileNm)).all()
        else:
            attachments = session.query(AttachmentDetails).filter_by(TranType=tran_type, TranMID=tran_mid).order_by(func.lower(AttachmentDetails.FileNm)).all()
        attachment_data = [att.to_dict() for att in attachments]
        return jsonify({'status':'success','data': attachment_data, 'length': len(attachment_data)}), 200
    except Exception as e:
        app.logger.error(e)
        return jsonify({'status':'error','message': 'Failed to retrieve attachment'}), 500
    finally:
        session.close()

@login_required
def deleteAttachment(attachment_id):
    if request.method == 'POST':
        session = DBSession()
        try:
            attachment = session.query(AttachmentDetails).filter_by(ID=attachment_id).one_or_none()
            if not attachment:
                return jsonify({'status': 'error', 'message': 'Attachment not found'}), 404

            ignored_fields = {'Other1', 'Other2', 'CrDtTm', 'CrBy', 'CrFrom', 'LstUpdDtTm', 'LstUpdBy', 'LstUpdFrom', 'Attchment'}
            change_log = ""
            for column in attachment.__table__.columns:
                if column.name and column.name not in ignored_fields:
                    change_log += f"{column.name}: {getattr(attachment, column.name)} => NaN\n"
            createUserActivity(ActionType=e_ActionType.DeleteRecord.idx, ActionDscr=e_ActionType.DeleteRecord.textval, EntityType=e_TranType.Attachment.idx, EntityID=attachment.ID, ChangeLog=change_log)

            session.delete(attachment)
            session.commit()
            return jsonify({'status': 'success', 'message': 'Attachment successfully deleted'}), 200
        except Exception as e:
            session.rollback()
            app.logger.error(e)
            return jsonify({'status': 'error', 'message': 'Failed to delete attachment'}), 500
        finally:
            session.close()
    else:
        return jsonify({'status': 'error', 'message': 'Invalid request method'}), 405

    
# Model functions    
def add_attachment(request):
    file = request.files['file']
    
    file_data = file.read()
    attachment = AttachmentDetails()
    attachment.Attchment=file_data
    attachment.FileNm=file.filename
    attachment.DocNm=request.form.get('DocNm', file.filename)

    changelog = []

    for key, value in request.form.items():
        if key not in ['file', 'FileNm']:
            if key == 'AttchType':
                changelog.append(f"{key}: NaN => {get_enum_info_by_idx(e_AttachTye, int(value))[0]}")
                setattr(attachment, key, int(value))
            else:
                changelog.append(f"{key}: NaN => {value}")
                setattr(attachment, key, value)
    
    attachment.AttchType=1 #it's fixed as of now and is not going to be used anywhere
    attachment = set_models_attr.setCreatedInfo(attachment)
    db_session = DBSession()
    try:
        db_session.add(attachment)
        db_session.commit()
        db_session.refresh(attachment)
        if changelog:
            createUserActivity(ActionType=e_ActionType.AddRecord.idx, ActionDscr=e_ActionType.AddRecord.textval, EntityType=e_TranType.Attachment.idx, EntityID=attachment.ID, ChangeLog="\n".join(changelog))
        return attachment.ID
    except Exception as e:
        db_session.rollback()
        app.logger.error(e)
        return False
    finally:
        db_session.close()

def edit_attachment(request, attachment_id):
    db_session = DBSession()
    attachment = db_session.query(AttachmentDetails).filter_by(ID=attachment_id).one_or_none()
    if not attachment:
        return jsonify({'status': 'error', 'message': 'Attachment not found'}), 404

    # if 'file' in request.files:
    #     file = request.files['file']
    #     file_data = file.read()
    #     attachment.Attchment = file_data
    #     attachment.FileNm = file.filename
    #     attachment.DocNm = request.form.get('DocNm', file.filename)

    changelog = []

    for key, value in request.form.items():
        # if key not in ['file', 'FileNm', 'DocNm']:
        if key in ['TranType', 'AttchType']:
            enum_select = e_AttachTye if key == 'AttchType' else e_TranType
            current_value = getattr(attachment, key)
            old_enum_value = (
                'NaN' if current_value in [None, '', ' '] else get_enum_info_by_idx(enum_select, int(current_value))
            )
            new_enum_value = get_enum_info_by_idx(enum_select, int(value)) if value not in [None, '', ' '] else 'NaN'
            if old_enum_value[1] != new_enum_value[1]:
                changelog.append(f"{key}: {old_enum_value[0]} => {new_enum_value[0]}")
            setattr(attachment, key, int(value))
        elif key not in ['file', 'FileNm', 'TranMID']:
            current_value = getattr(attachment, key, None)
            if current_value in [None, '', ' '] and value in [None, '', ' ']:
                # Both current and new values are empty or None; no change, no log.
                pass
            elif current_value not in [None, '', ' '] and value not in [None, '', ' '] and current_value != value:
                # Both current and new values have data, and they are different.
                changelog.append(f"{key}: {current_value} => {value}")
            elif current_value in [None, '', ' '] and value not in [None, '', ' ']:
                # Current value is empty, new value has data.
                changelog.append(f"{key}: NaN => {value}")
            elif current_value not in [None, '', ' '] and value in [None, '', ' ']:
                # Current value has data, new value is empty.
                changelog.append(f"{key}: {current_value} => NaN")
            setattr(attachment, key, value)

    # attachment.AttchType = 1  # it's fixed as of now and is not going to be used anywhere
    if changelog:
        createUserActivity(ActionType=e_ActionType.ChangeRecord.idx, ActionDscr=e_ActionType.ChangeRecord.textval, EntityType=e_TranType.Attachment.idx, EntityID=attachment.ID, ChangeLog="\n".join(changelog))

    attachment = set_models_attr.setUpdatedInfo(attachment)
    try:
        db_session.commit()
        return jsonify({'status': 'success', 'message': 'Attachment successfully updated'}), 200
    except Exception as e:
        db_session.rollback()
        app.logger.error(e)
        return jsonify({'status': 'error', 'message': 'Failed to update attachment'}), 500
    finally:
        db_session.close()


def allowed_file(filename):
    file_extension = filename.rsplit('.', 1)[1].lower()
    return file_extension in allowed_attachment_extensions

def get_attachments(MID, txn_type):
    session = DBSession()

    attachments_list = session.query(AttachmentDetails).filter(AttachmentDetails.TranMID == MID, AttachmentDetails.TranType == txn_type).all()
    session.close()
    return attachments_list

def delete_attachments(MID, txn_type):
    try:
        session = DBSession()
        
        if txn_type in [e_TranType.ProjectTmpl.idx, e_TranType.ProjectTran.idx]:
            delete_project_attachments(session, MID, txn_type)

        elif txn_type in [e_TranType.TaskTmpl.idx, e_TranType.TaskTran.idx]:
            delete_task_attachments(session, MID, txn_type)

        elif txn_type in [e_TranType.SubTaskTmpl.idx, e_TranType.SubTaskTran.idx]:
            delete_subtask_attachments(session, MID, txn_type)

        elif txn_type == e_TranType.Staff.idx:
            delete_staff_attachments(session, MID)
        
        session.commit()
        session.close()
        return True
    except Exception as e:
        session.rollback()  # Rollback in case of error
        app.logger.error(e)
        return False

def delete_project_attachments(session, MID, txn_type):
    if txn_type == e_TranType.ProjectTmpl.idx:
        project = session.query(ProjectTemplate).filter(ProjectTemplate.ID == MID).first()
        associated_tasks = [task.ID for task in project.task_templates]
        associated_subtasks = []

        for task_id in associated_tasks:
            task_obj = session.query(TaskTemplate).filter(TaskTemplate.ID == task_id).first()
            associated_subtasks.extend(subtask.ID for subtask in task_obj.subtask_templates)
        
        delete_attachments_by_type(session, project.ID, e_TranType.ProjectTmpl.idx)
        delete_attachments_by_type(session, associated_tasks, e_TranType.TaskTmpl.idx)
        delete_attachments_by_type(session, associated_subtasks, e_TranType.SubTaskTmpl.idx)

    else:
        project = session.query(ProjectTransaction).filter(ProjectTransaction.ID == MID).first()
        associated_tasks = [task.ID for task in project.task_transactions]
        associated_subtasks = []

        for task_id in associated_tasks:
            task_obj = session.query(TaskTransaction).filter(TaskTransaction.ID == task_id).first()
            associated_subtasks.extend(subtask.ID for subtask in task_obj.subtask_transaction)
        
        delete_attachments_by_type(session, project.ID, e_TranType.ProjectTran.idx)
        delete_attachments_by_type(session, associated_tasks, e_TranType.TaskTran.idx)
        delete_attachments_by_type(session, associated_subtasks, e_TranType.SubTaskTran.idx)

def delete_task_attachments(session, MID, txn_type):
    if txn_type == e_TranType.TaskTmpl.idx:
        task_obj = session.query(TaskTemplate).filter(TaskTemplate.ID == MID).first()
        associated_subtasks = [subtask.ID for subtask in task_obj.subtask_templates]
        
        delete_attachments_by_type(session, task_obj.ID, e_TranType.TaskTmpl.idx)
        delete_attachments_by_type(session, associated_subtasks, e_TranType.SubTaskTmpl.idx)

    else:
        task_obj = session.query(TaskTransaction).filter(TaskTransaction.ID == MID).first()
        associated_subtasks = [subtask.ID for subtask in task_obj.subtask_transaction]
        
        delete_attachments_by_type(session, task_obj.ID, e_TranType.TaskTran.idx)
        delete_attachments_by_type(session, associated_subtasks, e_TranType.SubTaskTran.idx)

def delete_subtask_attachments(session, MID, txn_type):
    if txn_type == e_TranType.SubTaskTmpl.idx:
        subtask_obj = session.query(SubTaskTemplate).filter(SubTaskTemplate.ID == MID).first()
        delete_attachments_by_type(session, subtask_obj.ID, e_TranType.SubTaskTmpl.idx)
    else:
        subtask_obj = session.query(SubTaskTransaction).filter(SubTaskTransaction.ID == MID).first()
        delete_attachments_by_type(session, subtask_obj.ID, e_TranType.SubTaskTran.idx)

def delete_staff_attachments(session, MID):
    staff_obj = session.query(StaffMaster).filter(StaffMaster.ID == MID).first()
    delete_attachments_by_type(session, staff_obj.ID, e_TranType.Staff.idx)

def delete_attachments_by_type(session, ids, txn_type):
    if isinstance(ids, list):
        session.query(AttachmentDetails).filter(
            AttachmentDetails.TranMID.in_(ids),
            AttachmentDetails.TranType == txn_type
        ).delete(synchronize_session=False)
    else:
        session.query(AttachmentDetails).filter(
            AttachmentDetails.TranMID == ids,
            AttachmentDetails.TranType == txn_type
        ).delete(synchronize_session=False)
