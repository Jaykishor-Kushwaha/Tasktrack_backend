from task_trak import app
app.secret_key = app.config['APP_SECRET_KEY']

if __name__ ==  "__main__":
    app.run(
	debug = True,
    host='0.0.0.0',
    port=5000
    )
else:
    pass

#python -m run