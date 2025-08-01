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
from datetime import datetime, timedelta

# import enumerations
from task_trak.db import enumerations

from task_trak.db.models.TaskTemplate import TaskTemplate

class ProjectTemplate(Base):
    __tablename__ = 'project_template'

    ID = Column(Integer, primary_key=True, nullable=False)
    Name = Column(String(80), unique=True, nullable=False)
    Dscr = Column(String(800))
    AprxDuration = Column(Interval)
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrBy = Column(String(60))
    CrFrom = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))

    task_templates = relationship("TaskTemplate", cascade="all, delete-orphan", back_populates="proj_template")
    
    def to_dict(self):
        return {
                'ID': self.ID,
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