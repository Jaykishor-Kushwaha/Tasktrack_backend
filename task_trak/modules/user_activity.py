from task_trak import app

# controller import
from task_trak.controllers.userActivityController import listUserActivity, createUserActivityForReport

app.route('/list_user_activity', methods=['GET'])(listUserActivity)
app.route('/create_user_activity_reports', methods=['POST'])(createUserActivityForReport)
