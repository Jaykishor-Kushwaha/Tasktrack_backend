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

# import enumerations
from task_trak.db import enumerations

class SubTaskTransaction(Base):
    __tablename__ = 'subtask_Transaction'
    
    ID = Column(Integer, primary_key=True)
    TaskTranID = Column(Integer, ForeignKey('task_transaction.ID', ondelete='CASCADE'), nullable=False)
    Name = Column(String(80), nullable=False)
    Dscr = Column(String(800))
    SubTaskLead = Column(String(20), ForeignKey('staff_master.Code', ondelete='RESTRICT'), nullable=False)
    AllocBy = Column(String(20), ForeignKey('staff_master.Code', ondelete='RESTRICT'), nullable=False)
    Priority = Column(Integer, default=enumerations.e_Priority.Low.idx, nullable=False)
    OrdNo = Column(DECIMAL(5, 2), nullable=False, default=1)
    StartDtTm = Column(DateTime)
    Duration = Column(Interval)
    EndDtTm = Column(DateTime)
    ActualStDtTm = Column(DateTime)
    ActualEndDtTm = Column(DateTime)
    ClosingComment = Column(String(200))
    DelayReason = Column(String(200))
    CancReason = Column(String(200))
    ClosureBy = Column(String(20), ForeignKey('staff_master.Code', ondelete='RESTRICT'), nullable=True)
    ClosureDtTm = Column(DateTime)
    Status = Column(Integer, default=enumerations.e_SubTaskStatus.Pending.idx, nullable=False)
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrBy = Column(String(60))
    CrFrom = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))

    subtask_lead = relationship("StaffMaster", foreign_keys=[SubTaskLead], back_populates='subtask_leads')
    subtask_alloc_by = relationship("StaffMaster", foreign_keys=[AllocBy], back_populates='subtask_allocates')
    subtask_closure_by = relationship("StaffMaster", foreign_keys=[ClosureBy], back_populates="subtask_closures")
    task_transaction = relationship("TaskTransaction", back_populates="subtask_transaction")

    __table_args__ = (
        Index('SubTaskTranName', Name),
        Index('UserSubTasks', SubTaskLead, StartDtTm, Name),
        Index('AllocSubTasks', AllocBy, StartDtTm, Name),
        Index('TaskSubTasks', TaskTranID, StartDtTm, OrdNo),
    )
    
    def to_dict(self):
        return {
            'ID': self.ID,
            'TaskTranID': self.TaskTranID,
            'Name': self.Name,
            'Dscr': self.Dscr,
            'SubTaskLead': self.SubTaskLead,
            'AllocBy': self.AllocBy,
            'Priority': self.Priority,
            'OrdNo': float(self.OrdNo),
            'StartDtTm': self.StartDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.StartDtTm else "",
            'Duration': self.format_aprx_duration(self.Duration),
            'EndDtTm': self.EndDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.EndDtTm else "",
            'ActualStDtTm': self.ActualStDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.ActualStDtTm else "",
            'ActualEndDtTm': self.ActualEndDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.ActualEndDtTm else "",
            'ClosingComment': self.ClosingComment if self.ClosingComment else "",
            'DelayReason': self.DelayReason if self.DelayReason else "",
            'CancReason': self.CancReason if self.CancReason else "",
            'ClosureBy': self.ClosureBy if self.ClosureBy else "",
            'ClosureDtTm': self.ClosureDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.ClosureDtTm else "",
            'Status': {"idx":self.Status, "text":enumerations.get_enum_info_by_idx(enumerations.e_SubTaskStatus, self.Status)[0]},
            'Other1': self.Other1,
            'Other2': self.Other2,
            'CrDtTm': self.CrDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            'CrBy': self.CrBy,
            'CrFrom': self.CrFrom,
            'LstUpdDtTm': self.LstUpdDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.LstUpdDtTm else "",
            'LstUpdBy': self.LstUpdBy if self.LstUpdBy else "",
            'LstUpdFrom': self.LstUpdFrom if self.LstUpdFrom else ""
        }
        
    def format_aprx_duration(self, interval):
        if interval is None:
            return '0 days, 00:00'
        total_seconds = interval.total_seconds()
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        # return f'{int(days)} days, {int(hours):02}:{int(minutes):02}:{int(seconds):02}'
        return f'{int(days)} days {int(hours):02}:{int(minutes):02}'