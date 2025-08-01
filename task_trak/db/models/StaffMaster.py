from task_trak.db.database_setup import Base

import datetime
import os
import sys
from sqlalchemy import Column, Index, ForeignKey, Integer, String, Interval, Date, DateTime, Float, JSON, Boolean, Sequence, Numeric, case, LargeBinary, func, Enum, desc, DECIMAL, asc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.orm import relationship, column_property, validates
from sqlalchemy.event import listens_for
from sqlalchemy import create_engine
from task_trak import app
# from dateutil.relativedelta import relativedelta
from datetime import datetime
import base64

# import enumerations
from task_trak.db import enumerations

# model imports
from task_trak.db.models.UserActivity import UserActivity
from task_trak.db.models.CommunicationCenter import CommunicationCenter
from task_trak.db.models.ProjectTransaction import ProjectTransaction
from task_trak.db.models.TaskTransaction import TaskTransaction
from task_trak.db.models.SubTaskTransaction import SubTaskTransaction

class StaffMaster(Base):
    __tablename__ = 'staff_master'

    ID = Column(Integer, primary_key=True)
    Code = Column(String(20), unique=True, nullable=False)
    Name = Column(String(80), nullable=False)
    IsActive = Column(Boolean, default=True, nullable=False)
    Type = Column(Integer, default=enumerations.e_UserType.Staff.idx, nullable=False)
    LoginId = Column(String(80), unique=True) #made unique=False as worker will not have login necessarily
    Pswd = Column(String(80))
    LockAcnt = Column(Integer, default=0, nullable=False)
    ResetPswd = Column(Boolean, default=False, nullable=False)
    Photo = Column(LargeBinary)
    Mobile = Column(String(80), nullable=False)
    EmailID = Column(String(120), nullable=False)
    Addr1 = Column(String(80))
    Addr2 = Column(String(80))
    Area = Column(String(80))
    City = Column(String(80))
    Pincode = Column(String(20))
    Country = Column(String(80), default='India')
    BirthDt = Column(Date, nullable=False)
    JoinDt = Column(Date)
    RelvDt = Column(Date)
    BldGrp = Column(String(10))
    Gender = Column(Integer, default=enumerations.e_Gender.Male.idx, nullable=False)
    AADHARNo = Column(String(30))
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrBy = Column(String(60))
    CrFrom = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstLoginDtTm = Column(DateTime)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))
    
    def to_dict(self):
        return {
            'ID': self.ID,
            'Code': self.Code,
            'Name': self.Name,
            'IsActive': self.IsActive,
            'Type': self.Type,
            'LoginId': self.LoginId,
            'Mobile': self.Mobile,
            'EmailID': self.EmailID,
            'Addr1': self.Addr1,
            'Addr2': self.Addr2,
            'Area': self.Area,
            'City': self.City,
            'Pincode': self.Pincode,
            'Country': self.Country,
            'BirthDt': self.BirthDt.strftime('%Y-%m-%d') if self.BirthDt else None,
            'JoinDt': self.JoinDt.strftime('%Y-%m-%d') if self.JoinDt else None,
            'RelvDt': self.RelvDt.strftime('%Y-%m-%d') if self.RelvDt else None,
            'BldGrp': self.BldGrp,
            'Gender': self.Gender,
            'AADHARNo': self.AADHARNo,
            'Other1': self.Other1,
            'Other2': self.Other2,
            'CrDtTm': self.CrDtTm.strftime('%Y-%m-%d %H:%M:%S') if self.CrDtTm else None,
            'CrBy': self.CrBy,
            'CrFrom': self.CrFrom,
            'LstUpdDtTm': self.LstUpdDtTm.strftime('%Y-%m-%d %H:%M:%S') if self.LstUpdDtTm else None,
            'LstLoginDtTm': self.LstLoginDtTm.strftime('%Y-%m-%d %H:%M:%S') if self.LstLoginDtTm else None,
            'LstUpdBy': self.LstUpdBy,
            'LstUpdFrom': self.LstUpdFrom,
            'Photo': f"data:image/jpeg;base64,{base64.b64encode(self.Photo).decode('utf-8')}" if self.Photo else "",
        }

    __table_args__ = (
        Index('Name', Name),  # Unique index on 'Name'
        Index('isActiveName', IsActive, Name)
    )

    activities = relationship("UserActivity", back_populates="staff", passive_deletes=True)  # Added back_populates here

    sent_comms = relationship("CommunicationCenter", back_populates="sender", foreign_keys="[CommunicationCenter.SentBy]", passive_deletes=True)  # Added back_populates here
    received_comms = relationship("CommunicationCenter", back_populates="receiver", foreign_keys="[CommunicationCenter.SentTo]", passive_deletes=True)  # Added back_populates here

    project_leads = relationship("ProjectTransaction", back_populates="proj_lead", foreign_keys="[ProjectTransaction.ProjLead]", passive_deletes=True)  # Added back_populates here
    project_allocates = relationship("ProjectTransaction", back_populates="allocate_by", foreign_keys="[ProjectTransaction.AllocBy]", passive_deletes=True)  # Added back_populates here
    project_accepts = relationship("ProjectTransaction", back_populates="accepted_by", foreign_keys="[ProjectTransaction.AcptdBy]", passive_deletes=True)  # Added back_populates here

    task_leads = relationship("TaskTransaction", back_populates="task_lead", foreign_keys="[TaskTransaction.TaskLead]", passive_deletes=True)  # Added back_populates here
    task_allocates = relationship("TaskTransaction", back_populates="task_alloc_by", foreign_keys="[TaskTransaction.AllocBy]", passive_deletes=True)  # Added back_populates here
    task_clousers = relationship("TaskTransaction", back_populates="task_clouser_by", foreign_keys="[TaskTransaction.ClosureBy]", passive_deletes=True)  # Added back_populates here

    subtask_leads = relationship("SubTaskTransaction", back_populates="subtask_lead", foreign_keys="[SubTaskTransaction.SubTaskLead]", passive_deletes=True)  # Added back_populates here
    subtask_allocates = relationship("SubTaskTransaction", back_populates="subtask_alloc_by", foreign_keys="[SubTaskTransaction.AllocBy]", passive_deletes=True)  # Added back_populates here
    subtask_closures = relationship("SubTaskTransaction", back_populates="subtask_closure_by", foreign_keys="[SubTaskTransaction.ClosureBy]", passive_deletes=True)  # Added back_populates here

    def email_verified_check(self):
        """Return True if the user is authenticated."""
        return self.IsActive and self.LoginId

    # @hybrid_property
    # def ASCN(self):
    #     return f"{self.IsActive}{self.Name}"  # Concatenate IsActive and Name

    # # need to define as sqlalchemy expression as well
    # @ASCN.expression
    # def ASCN(cls):
    #     return func.concat(cls.IsActive, cls.Name)  # Concatenate IsActive and Name in SQL expression
    # how to use? - result = session.query(YourModel).filter(YourModel.IsActive == True).order_by(YourModel.ASCN).all()

# Event listener to update CrDtTm before INSERT
# @listens_for(StaffMaster, 'before_insert')
# def update_created_date(mapper, connection, target):
#     target.CrDtTm = datetime.now()

# # Event listener to update LstUpdDtTm before UPDATE
# @listens_for(StaffMaster, 'before_update')
# def update_last_updated_date(mapper, connection, target):
#     target.LstUpdDtTm = datetime.now()