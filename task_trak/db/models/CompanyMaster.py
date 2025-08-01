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

class CompanyMaster(Base):
    __tablename__ = 'company_master'

    ID = Column(Integer, primary_key=True)
    Code = Column(String(20), unique=True, nullable=False)
    Name = Column(String(80), nullable=False)
    Logo = Column(LargeBinary)
    Addr1 = Column(String(80), nullable=False)
    Addr2 = Column(String(80))
    Area = Column(String(80), nullable=False)
    City = Column(String(80), nullable=False)
    Pincode = Column(String(20))
    Country = Column(String(80), default='India')
    Phone = Column(String(80))
    Mobile = Column(String(80))
    EMail = Column(String(120))
    WebAddr = Column(String(120))
    AutoNotification = Column(Boolean(), default=True)
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrFrom = Column(String(60))
    CrBy = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))
    
    def to_dict(self):
        return {
            'ID': self.ID,
            'Code': self.Code,
            'Name': self.Name,
            'Logo': f"data:image/jpeg;base64,{base64.b64encode(self.Logo).decode('utf-8')}" if self.Logo else "",
            'Addr1': self.Addr1,
            'Addr2': self.Addr2,
            'Area': self.Area,
            'City': self.City,
            'Pincode': self.Pincode,
            'Country': self.Country,
            'Phone': self.Phone,
            'Mobile': self.Mobile,
            'EMail': self.EMail,
            'WebAddr': self.WebAddr,
            'Other1': self.Other1,
            'Other2': self.Other2,
            'CrDtTm': self.CrDtTm.strftime('%Y-%m-%d %H:%M:%S') if self.CrDtTm else None,
            'CrFrom': self.CrFrom,
            'CrBy': self.CrBy,
            'LstUpdDtTm': self.LstUpdDtTm.strftime('%Y-%m-%d %H:%M:%S') if self.LstUpdDtTm else None,
            'LstUpdBy': self.LstUpdBy,
            'LstUpdFrom': self.LstUpdFrom
        }