# app import
from task_trak import app

# controller import
from task_trak.controllers.baseAppController import indexRoute, getData

app.route("/", methods=['GET', 'POST'])(indexRoute)

app.route("/get_data/<table>", methods=['GET', 'POST'])(getData)