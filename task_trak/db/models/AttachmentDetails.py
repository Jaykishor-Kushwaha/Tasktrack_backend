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
from datetime import datetime
import base64, mimetypes

# import enumerations
from task_trak.db import enumerations

class AttachmentDetails(Base):
    __tablename__ = 'attachment_details'

    ID = Column(Integer, primary_key=True)
    TranType = Column(Integer, nullable=False)
    TranMID = Column(Integer, nullable=False)
    AttchType = Column(Integer, default=enumerations.e_AttachTye.General.idx, nullable=False)
    DocNm = Column(String(120), nullable=False)
    Attchment = Column(LargeBinary, nullable=False)
    FileNm = Column(String(120), nullable=False)
    Dscr = Column(String(800))
    Other1 = Column(String(60))
    Other2 = Column(String(60))
    CrDtTm = Column(DateTime, default=datetime.now)
    CrBy = Column(String(60))
    CrFrom = Column(String(60))
    LstUpdDtTm = Column(DateTime, onupdate=datetime.now)
    LstUpdBy = Column(String(60))
    LstUpdFrom = Column(String(60))

    __table_args__ = (
        Index('TranTypMIDDocNm', TranType, TranMID, DocNm),
        Index('TranTypMIDAtchTyp', TranType, TranMID, AttchType),
    )

    def to_dict(self):
        mime_type, _ = mimetypes.guess_type(self.FileNm)
        return {
            'ID': self.ID,
            'TranType': self.TranType,
            'TranMID': self.TranMID,
            'AttchType': self.AttchType,
            'DocNm': self.DocNm,
            'Attchment': base64.b64encode(self.Attchment).decode('utf-8') if self.Attchment else None,
            'FileNm': self.FileNm,
            'Dscr': self.Dscr,
            'Other1': self.Other1,
            'Other2': self.Other2,
            'CrDtTm': self.CrDtTm.isoformat() if self.CrDtTm else None,
            'CrBy': self.CrBy,
            'CrFrom': self.CrFrom,
            'LstUpdDtTm': self.LstUpdDtTm.isoformat() if self.LstUpdDtTm else None,
            'LstUpdBy': self.LstUpdBy,
            'LstUpdFrom': self.LstUpdFrom,
            "MimeType": mime_type
        }

    # @hybrid_property
    # def TranTypMIDDocNm(self):
    #     return f"{self.TranType}_{self.TranMID}_{self.DocNm}"

    # @TranTypMIDDocNm.expression
    # def TranTypMIDDocNm(cls):
    #     return func.concat(cls.TranType, '_', cls.TranMID, '_', cls.DocNm)

    # # Define hybrid_property for TranTypMIDAtchTyp
    # @hybrid_property
    # def TranTypMIDAtchTyp(self):
    #     return f"{self.TranType}_{self.TranMID}_{self.AttchType}"

    # @TranTypMIDAtchTyp.expression
    # def TranTypMIDAtchTyp(cls):
    #     return func.concat(cls.TranType, '_', cls.TranMID, '_', cls.AttchType)