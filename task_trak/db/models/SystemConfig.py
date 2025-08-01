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

class SystemConfig(Base):
    __tablename__ = 'system_config'
    ID = Column(Integer, primary_key=True)
    Key = Column(String(100), unique=True, nullable=False)
    Value = Column(String(500))
    KeyDescription = Column(String(200))
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrBy = Column(String(60))
    CrFrom = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))

    def to_dict(self):
        return {
            "ID": str(self.ID) if self.ID else "",
            "Key": self.Key if self.Key else "",
            "Value": self.Value.strip() if self.Value else "",
            "KeyDescription": self.KeyDescription if self.KeyDescription else "",
            "Other1": self.Other1 if self.Other1 else "",
            "Other2": self.Other2 if self.Other2 else "",
            "CrDtTm": str(self.CrDtTm) if self.CrDtTm else "",
            "CrBy": self.CrBy if self.CrBy else "",
            "CrFrom": self.CrFrom if self.CrFrom else "",
            "LstUpdDtTm": str(self.LstUpdDtTm) if self.LstUpdDtTm else "",
            "LstUpdBy": self.LstUpdBy if self.LstUpdBy else "",
            "LstUpdFrom": self.LstUpdFrom if self.LstUpdFrom else ""
        }