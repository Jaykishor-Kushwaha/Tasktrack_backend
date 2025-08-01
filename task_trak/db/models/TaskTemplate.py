from task_trak.db.database_setup import Base

import os
import sys
from sqlalchemy import Column, Index, ForeignKey, Integer, String, Interval, Date, DateTime, Float, JSON, Boolean, Sequence, Numeric, case, LargeBinary, func, Enum, desc, DECIMAL, asc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property, hybrid_method
from sqlalchemy.orm import relationship, column_property, validates, backref
from sqlalchemy.event import listens_for
from sqlalchemy import create_engine
from task_trak import app
# from dateutil.relativedelta import relativedelta
from datetime import datetime

# import enumerations
from task_trak.db import enumerations

from task_trak.db.models.SubTaskTemplate import SubTaskTemplate

class TaskTemplate(Base):
    __tablename__ = 'task_template'

    ID = Column(Integer, primary_key=True, nullable=False)
    ProjTmplID = Column(Integer, ForeignKey('project_template.ID', ondelete='CASCADE'), nullable=True)
    OrdNo = Column(DECIMAL(5, 2), default=1, nullable=False)
    Name = Column(String(80), nullable=False)
    Dscr = Column(String(800))
    AprxDuration = Column(Interval, nullable=False)
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrBy = Column(String(60))
    CrFrom = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))

    # Define relationship to ProjTmpl
    proj_template = relationship("ProjectTemplate", back_populates="task_templates")
    subtask_templates = relationship("SubTaskTemplate", cascade="all, delete-orphan", back_populates="task_template")

    __table_args__ = (
        Index('ProjTmplName', ProjTmplID, Name, unique=True),
        Index('ProjTmplOrd', ProjTmplID, OrdNo),
    )
    
    def to_dict(self):
        return{
                'ID': self.ID,
                'ProjTmplID': self.ProjTmplID,
                'OrdNo': float(self.OrdNo),
                'Name': self.Name,
                'Dscr': self.Dscr,
                'AprxDuration': self.format_aprx_duration(self.AprxDuration),
                'Other1': self.Other1,
                'Other2': self.Other2,
                'CrDtTm': str(self.CrDtTm),
                'CrBy': self.CrBy,
                'CrFrom': str(self.CrFrom),
                'LstUpdDtTm': str(self.LstUpdDtTm),
                'LstUpdBy': self.LstUpdBy,
                'LstUpdFrom': self.LstUpdFrom
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