from Socket import socketio
from flask_socketio import emit
from Chat.Functions import GetChatId, save_message
from datetime import datetime

@socketio.on('join')
def on_join(data):
    user1 = data.get('user1')
    user2 = data.get('user2')
    if not user1 or not user2:
        emit('error', {'error': 'user1 and user2 are required'})
        return
    chat_data, status = GetChatId(user1, user2)
    if status == 200:
        emit('chat_data', chat_data)
    else:
        emit('error', chat_data)


@socketio.on('message')
def handle_message(data):
    content = data.get('content')
    sender = data.get('sender')
    chatId = data.get('chatId')
    if content and sender and sender.get('id') and sender.get('name'):
        message_obj = {
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'sender': {
                'id': sender.get('id'),
                'name': sender.get('name'),
                'photoURL': sender.get('photoURL')
            },
            'chatId': chatId
        }
        save_message(chatId,message_obj)
        emit('new_message', message_obj,include_self=False,broadcast=True)
    else:
        emit('error', {'error': 'Invalid message structure'})
