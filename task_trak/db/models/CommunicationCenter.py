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

class CommunicationCenter(Base):
    __tablename__ = 'communication_center'

    ID = Column(Integer, primary_key=True)
    DtTime = Column(DateTime, nullable=False)
    TranType = Column(Integer, default=enumerations.e_TranType.Company.idx, nullable=False)
    TranMID = Column(Integer, nullable=False)
    SentBy = Column(String(20), ForeignKey('staff_master.Code', ondelete='RESTRICT'), nullable=False)
    SentTo = Column(String(20), ForeignKey('staff_master.Code', ondelete='RESTRICT'), nullable=False)
    SentVia = Column(Integer, default=enumerations.e_SentVia.SysNotif.idx, nullable=False)  # Assuming your enum values are represented as integers
    Subject = Column(String(80), nullable=False)
    Description = Column(String(2000), nullable=False)
    ReadDtTm = Column(DateTime)
    Status = Column(Integer, default=enumerations.e_NotificationStatus.Pending.idx, nullable=False)  # Assuming your enum values are represented as integers
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrBy = Column(String(60))
    CrFrom = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))

    # Define relationships
    sender = relationship("StaffMaster", foreign_keys=[SentBy], back_populates='sent_comms')
    receiver = relationship("StaffMaster", foreign_keys=[SentTo], back_populates='received_comms')

    __table_args__ = (
        Index('CommDtTime', DtTime),
        Index('TranTypMIDStatusDtTm', TranType, TranMID, Status, DtTime),
        Index('SentByDtTm', SentBy, DtTime),
        Index('TranTypMIDDtTm', TranType, TranMID, DtTime),
    )
    
    def to_dict(self):
        return {
            'ID': self.ID,
            'DtTime': self.DtTime,
            'TranType': {"idx": self.TranType, "text": enumerations.get_enum_info_by_idx(enumerations.e_TranType, self.TranType)[0]} if self.TranType else {"idx": None, "text": None},
            'TranMID': self.TranMID,
            'SentBy': self.SentBy,
            'SentTo': self.SentTo,
            'SentVia': self.SentVia,
            'Subject': self.Subject,
            'Description': self.Description,
            'ReadDtTm': self.ReadDtTm,
            'Status': {"idx": self.Status, "text": enumerations.get_enum_info_by_idx(enumerations.e_NotificationStatus, self.Status)[0]},
            'Other1': self.Other1 or '',
            'Other2': self.Other2 or '',
            'CrDtTm': self.CrDtTm,
            'CrBy': self.CrBy or '',
            'CrFrom': self.CrFrom or '',
            'LstUpdDtTm': self.LstUpdDtTm,
            'LstUpdBy': self.LstUpdBy or '',
            'LstUpdFrom': self.LstUpdFrom or '',
        }

    # @hybrid_property
    # def TranTypMIDDtTm(self):
    #     return f"{self.TranType}_{self.TranMID}_{self.Status}_{self.DtTime}"  

    # @TranTypMIDDtTm.expression
    # def TranTypMIDDtTm(cls):
    #     return func.concat(cls.TranType, '_', cls.TranMID, '_', cls.Status, '_', cls.DtTime)

    # @hybrid_property
    # def SentByDtTm(self):
    #     return f"{self.SentBy}_{self.DtTime}"

    # @SentByDtTm.expression
    # def SentByDtTm(cls):
    #     return func.concat(cls.SentBy, '_', cls.DtTime)

    # @hybrid_property
    # def TranTypeDtTm(self):
    #     return f"{self.TranType}_{self.TranMID}_{self.DtTime}"

    # @TranTypeDtTm.expression
    # def TranTypeDtTm(cls):
    #     return func.concat(cls.TranType, '_', cls.TranMID, '_', cls.DtTime)