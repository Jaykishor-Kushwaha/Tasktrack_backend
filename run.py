import os
from task_trak import app

app.secret_key = app.config['APP_SECRET_KEY']

# For Vercel deployment
if __name__ != "__main__":
    # This is for Vercel
    application = app
else:
    # This is for local development
    port = int(os.environ.get('PORT', 5000))
    app.run(
        debug=False,
        host='0.0.0.0',
        port=port
    )
