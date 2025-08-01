# app import
from task_trak import app

# controller import
from task_trak.controllers.companyController import addCompanyInfo, editCompanyInfo

app.route('/add_company_info', methods=['POST'])(addCompanyInfo)

app.route('/company_info', methods=['GET','POST'])(editCompanyInfo)