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

from task_trak.db.models.TaskTransaction import TaskTransaction

class ProjectTransaction(Base):
    __tablename__ = 'project_transaction'

    ID = Column(Integer, primary_key=True)
    Name = Column(String(80), nullable=False)
    Dscr = Column(String(800))
    ProjLead = Column(String(20), ForeignKey('staff_master.Code', ondelete='RESTRICT'), nullable=False)
    AllocBy = Column(String(20), ForeignKey('staff_master.Code', ondelete='RESTRICT'), nullable=False)
    Priority = Column(Integer, default=enumerations.e_Priority.Low.idx, nullable=False)
    StartDtTm = Column(DateTime)
    Duration = Column(Interval)
    EndDtTm = Column(DateTime)
    ActualStDtTm = Column(DateTime)
    ActualEndDtTm = Column(DateTime)
    ClosingComment = Column(String(200))
    DelayReason = Column(String(200))
    RejectReason = Column(String(200))
    CancReason = Column(String(200))
    ClosureBy = Column(String(20), ForeignKey('staff_master.Code', ondelete='RESTRICT'), nullable=True)
    ClosureDtTm = Column(DateTime)
    AcptdBy = Column(String(20), ForeignKey('staff_master.Code', ondelete='RESTRICT'))
    AcptdDtTm = Column(DateTime)
    Status = Column(Integer, default=enumerations.e_ProjStatus.Pending.idx, nullable=False)
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrBy = Column(String(60))
    CrFrom = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))

    # Relationships
    proj_lead = relationship("StaffMaster", foreign_keys=[ProjLead], back_populates="project_leads")
    allocate_by = relationship("StaffMaster", foreign_keys=[AllocBy], back_populates="project_allocates")
    accepted_by = relationship("StaffMaster", foreign_keys=[AcptdBy], back_populates="project_accepts")
    task_transactions = relationship("TaskTransaction", cascade="all, delete-orphan", back_populates="project_transaction")

    __table_args__ = (
        Index('ProjName', Name),
        Index('UserProjs', ProjLead, StartDtTm, Name),
        Index('AllocProjs', AllocBy, StartDtTm, Name),
    )
    
    def to_dict(self):
        return {
            'ID': self.ID,
            'Name': self.Name,
            'Dscr': self.Dscr if self.Dscr else "",
            'ProjLead': self.ProjLead,
            'AllocBy': self.AllocBy,
            'Priority': self.Priority,
            'StartDtTm': self.StartDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.StartDtTm else "",
            'Duration': self.format_aprx_duration(self.Duration) if self.Duration else "",
            'EndDtTm': self.EndDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.EndDtTm else "",
            'ActualStDtTm': self.ActualStDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.ActualStDtTm else "",
            'ActualEndDtTm': self.ActualEndDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.ActualEndDtTm else "",
            'ClosingComment': self.ClosingComment if self.ClosingComment else "",
            'DelayReason': self.DelayReason if self.DelayReason else "",
            'CancReason': self.CancReason if self.CancReason else "",
            'RejectReason': self.RejectReason if self.RejectReason else "",
            'AcptdBy': self.AcptdBy if self.AcptdBy else "",
            'AcptdDtTm': self.AcptdDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.AcptdDtTm else "",
            'Status': {"idx": self.Status, "text": enumerations.get_enum_info_by_idx(enumerations.e_ProjStatus, self.Status)[0]},
            'Other1': self.Other1 if self.Other1 else "",
            'Other2': self.Other2 if self.Other2 else "",
            'CrDtTm': self.CrDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            'CrBy': self.CrBy if self.CrBy else "",
            'CrFrom': self.CrFrom if self.CrFrom else "",
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
        return f'{int(days)} days {int(hours):02}:{int(minutes):02}'
