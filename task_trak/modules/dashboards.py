from task_trak import app

# controller import
from task_trak.controllers.dashboardController import overDue, onGoing, underReview, upComing, taskCountsDashboard, unreadNotifications

# count endpoint
app.route('/dashboard/count', methods=['GET'])(taskCountsDashboard)
app.route('/dashboard/count/<user_code>', methods=['GET'])(taskCountsDashboard)

# data endpoints
app.route('/dashboard/overdue/<user_code>', methods=['GET'])(overDue)
app.route('/dashboard/ongoing/<user_code>', methods=['GET'])(onGoing)
app.route('/dashboard/under_review/<user_code>', methods=['GET'])(underReview)
app.route('/dashboard/upcoming/<user_code>', methods=['GET'])(upComing)
app.route('/dashboard/unread_notification/<user_code>', methods=['GET'])(unreadNotifications)