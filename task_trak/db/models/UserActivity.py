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

class UserActivity(Base):
    __tablename__ = 'user_activity'

    ID = Column(Integer, primary_key=True)
    StaffCode = Column(String(20), ForeignKey('staff_master.Code', ondelete='CASCADE'), nullable=False)
    ActionDtTm = Column(DateTime, nullable=False)
    ActionType = Column(String(50), nullable=False)
    ActionDscr = Column(String(200), nullable=False)
    EntityType = Column(Integer, nullable=False)
    EntityID = Column(Integer, nullable=False)
    ChangeLog = Column(String, nullable=True)
    FromIP = Column(String(80), nullable=False)
    FromDeviceNm = Column(String(80), nullable=False)
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrBy = Column(String(60))
    CrFrom = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))

    __table_args__ = (
        Index('DayAction', ActionDtTm.desc()),
        Index('StaffActions', StaffCode, ActionDtTm.desc()),
        Index('Action', ActionType),
        Index('EntityTypeID', EntityType, EntityID),
    )

    # Define relationship with StaffMst table
    staff = relationship("StaffMaster", foreign_keys=[StaffCode], back_populates="activities")  # Added back_populates here

    def to_dict(self):
        return {
            'ID': self.ID,
            'StaffCode': self.StaffCode,
            'ActionDtTm': self.ActionDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.ActionDtTm else "",
            'ActionType': self.ActionType,
            'ActionDscr': self.ActionDscr,
            'EntityType': self.EntityType,
            'EntityID': self.EntityID,
            'ChangeLog': self.ChangeLog,
            'FromIP': self.FromIP,
            'FromDeviceNm': self.FromDeviceNm,
            'Other1': self.Other1,
            'Other2': self.Other2,
            'CrDtTm': self.CrDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.CrDtTm else "",
            'CrBy': self.CrBy,
            'CrFrom': self.CrFrom,
            'LstUpdDtTm': self.LstUpdDtTm.strftime("%a, %d %b %Y %H:%M:%S GMT") if self.LstUpdDtTm else "",
            'LstUpdBy': self.LstUpdBy,
            'LstUpdFrom': self.LstUpdFrom
        }

    # @hybrid_property
    # def DSCN(self):
    #     return (self.StaffCode, self.ActDtTm)

    # @DSCN.expression
    # def DSCN(cls):
    #     return desc(cls.StaffCode), desc(cls.ActDtTm)
    # how to use? - results = session.query(YourModel).order_by(YourModel.DSCN).all()