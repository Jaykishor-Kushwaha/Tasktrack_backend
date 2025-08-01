from task_trak import app

# controller import
from task_trak.controllers.systemConfigController import checkConfigExists, updateSystemConfigs, listSysConfigs

app.route('/check_sysconfig_exists', methods=['GET','POST'])(checkConfigExists) #call this on successful login

app.route('/list_sysconfigs', methods=['GET','POST'])(listSysConfigs)

app.route('/update_sysconfigs', methods=['GET','POST'])(updateSystemConfigs)