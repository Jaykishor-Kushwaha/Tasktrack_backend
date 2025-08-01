from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from task_trak import app


Base = declarative_base()

from task_trak.db.models import CompanyMaster
from task_trak.db.models import StaffMaster
from task_trak.db.models import UserActivity
from task_trak.db.models import AttachmentDetails
from task_trak.db.models import SystemConfig
from task_trak.db.models import CommunicationCenter
from task_trak.db.models import ProjectTemplate
from task_trak.db.models import TaskTemplate
from task_trak.db.models import SubTaskTemplate
from task_trak.db.models import ProjectTransaction
from task_trak.db.models import TaskTransaction

engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.create_all(engine)