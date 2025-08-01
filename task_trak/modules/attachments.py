# app import
from task_trak import app

# controller import
from task_trak.controllers.attachmentController import uploadAttachment, editAttachment, getAttachment, deleteAttachment

app.route('/upload', methods=['POST'])(uploadAttachment)

app.route('/edit_attachments/<attachment_id>', methods=['GET', 'POST'])(editAttachment)

app.route('/get_attachments', methods=['GET'])(getAttachment)

app.route('/delete/attachment/<attachment_id>', methods=['POST'])(deleteAttachment)