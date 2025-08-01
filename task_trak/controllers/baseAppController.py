from task_trak import app, company_master_exists, system_admin_exists, login_required

from task_trak.db.database_setup import (Base as Base)

from task_trak.db.models.CompanyMaster import (CompanyMaster as CompanyMaster)
from task_trak.db.models.StaffMaster import (StaffMaster as StaffMaster)
from task_trak.db.models.ProjectTemplate import (ProjectTemplate as ProjectTemplate)
from task_trak.db.models.TaskTemplate import (TaskTemplate as TaskTemplate)
from task_trak.db.models.SubTaskTemplate import (SubTaskTemplate as SubTaskTemplate)
from task_trak.db.models.ProjectTransaction import (ProjectTransaction as ProjectTransaction)
from task_trak.db.models.TaskTransaction import (TaskTransaction as TaskTransaction)
from task_trak.db.models.SubTaskTransaction import (SubTaskTransaction as SubTaskTransaction)
from task_trak.db.models.CommunicationCenter import (CommunicationCenter as CommunicationCenter)

from task_trak.controllers.staffController import get_user_object, get_users_list

from task_trak.db.enumerations import get_enum_info_by_idx, get_enum_info_by_textval, enum_to_list, e_UserType, e_Gender, e_TranType

from flask import jsonify

from sqlalchemy import create_engine, func, desc, or_
from sqlalchemy.orm import sessionmaker

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

@company_master_exists
@system_admin_exists
def indexRoute(*args, **kwargs):
    """
    Index route for the application.

    :return: A JSON response with a greeting message or an error message.
    :rtype: flask.Response
    """
    try:
        return jsonify({"hello": "world"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    
@login_required
def getData(table):
    selected_table = table_maps[int(table)]
    loggedin_user = get_user_object(getData.user_loginid)
    session = DBSession()
    if loggedin_user.Type in [e_UserType.Admin.idx, e_UserType.SysAdm.idx]:
        data = session.query(selected_table).all()
        session.close()
        return jsonify({"status":"success", "data":[i.to_dict() for i in data]}), 200
    else:
        data = []
        # Check if the selected table is one of the Transaction tables
        if selected_table == ProjectTransaction:
            data = session.query(ProjectTransaction).filter(ProjectTransaction.ProjLead == loggedin_user.Code).all()
        elif selected_table == TaskTransaction:
            data = session.query(TaskTransaction).filter(TaskTransaction.TaskLead == loggedin_user.Code).all()
        elif selected_table == SubTaskTransaction:
            data = session.query(SubTaskTransaction).filter(SubTaskTransaction.SubTaskLead == loggedin_user.Code).all()
        # If it's StaffMaster, use get_users_list()
        elif selected_table == StaffMaster:
            data = get_users_list(getData.user_type)
            # session.close()
            # return jsonify([user.to_dict() for user in data]), 200
        else:
            data = session.query(selected_table).all()
        
        session.close()
        
        # Return filtered data for transaction tables
        if data:
            return jsonify({"status":"success", "data":[i.to_dict() for i in data]}), 200
        else:
            return jsonify({"status":"success", "data":[]}), 200
    



table_maps = {
    1 : CompanyMaster,
    2 : StaffMaster,
    3 : ProjectTemplate,
    4 : TaskTemplate,
    5 : SubTaskTemplate,
    6 : ProjectTransaction,
    7 : TaskTransaction,
    8 : SubTaskTransaction,
    9 : CommunicationCenter,
}