import os
from task_trak import app

app.secret_key = app.config['APP_SECRET_KEY']

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(
        debug=False,
        host='0.0.0.0',
        port=port
    )
else:
    pass

#python -m run
