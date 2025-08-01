user_config = {}

# App Settings
user_config['MODE'] = 'DEVELOPMENT'
user_config['BASE_URL'] ='http://localhost:5000'
user_config['LOCKED_PASSWORD'] ='Locked'
user_config['ATTACHMENT_UPLOAD_SIZE'] = 100 * 1024 * 1024 #100 MB

#Mail Setings
user_config['MAIL_SERVER']='smtp.gmail.com'
user_config['MAIL_PORT']=465
user_config['MAIL_USE_SSL']=True
user_config['MAIL_USERNAME'] = 'dailyblogs.team@gmail.com'
user_config['MAIL_DEFAULT_SENDER'] = '"Avante TaskTracker" <dailyblogs.team@gmail.com>'
user_config['MAIL_PASSWORD'] = 'exlrlelpnuqnzutw'

# Secret Key Settings
user_config['APP_SECRET_KEY'] = 'development-env-app-secret-key'
user_config['JWT_SECRET_KEY'] = 'development-env-jwt-secret-key'