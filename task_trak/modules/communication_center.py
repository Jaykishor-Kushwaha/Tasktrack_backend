from task_trak import app

# controller import
from task_trak.controllers.communicationCenterController import addNotification, getNotification, listNotifications, getUnreadNotificationsCount

app.route('/add_notification', methods=['GET','POST'])(addNotification)

app.route('/get_notification/<notification_id>', methods=['GET'])(getNotification)

app.route('/list_notifications', methods=['GET'])(listNotifications)

app.route('/get_unread_notifications_count', methods=['GET'])(getUnreadNotificationsCount)