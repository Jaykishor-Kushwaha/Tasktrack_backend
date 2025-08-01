# app import
from task_trak import app

# controller import
from task_trak.controllers.staffController import logIn, getUserInfo, logOut, signUp, resetPasswordAdmin, resetPasswordUser, changePasswordUser, activateUser, deactivateUser, deleteUser, listUsers, editUser

app.route('/signup', methods=['GET', 'POST'])(signUp)
    

app.route('/login', methods=['GET', 'POST'])(logIn)

app.route('/get_user_info', methods=['GET'])(getUserInfo)

app.route('/logout', methods=['GET'])(logOut)

    
#one that admin will use from admin-panel to generate the initial reset password
app.route('/reset_password/<login_id>', methods=['POST'])(resetPasswordAdmin)


# one that user will use to reset the password
app.route('/password_reset/', methods=['POST'])(resetPasswordUser)

app.route('/change_password/<login_id>', methods=['POST'])(changePasswordUser)
        
app.route('/activate/<login_id>', methods=['POST'])(activateUser)


app.route('/deactivate/<login_id>', methods=['POST'])(deactivateUser)

    
app.route('/delete_staff/<login_id>', methods=['POST'])(deleteUser)
    

app.route('/list_users', methods=['GET'])(listUsers)


app.route('/user/<login_id>', methods=['GET','POST'])(editUser)
