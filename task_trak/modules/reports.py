from task_trak import app

# controller import
from task_trak.controllers.reportController import reportList

app.route('/reports', methods=['GET'])(reportList)