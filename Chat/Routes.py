from Socket import socketio
from flask_socketio import emit, join_room, leave_room
from datetime import datetime

baseurl = "/chat"

# Store connected users and their rooms
connected_users = {}

@socketio.on('join')
def on_join(data):
    print("User joined:", data)
    displayName = data.get('displayName')
    room = data.get('room')
    if displayName and room:
        join_room(room)
        connected_users[displayName] = room
        emit('user_joined', {'displayName': displayName}, room=room)

@socketio.on('leave')
def on_leave(data):
    displayName = data.get('displayName')
    room = data.get('room')
    if displayName and room:
        leave_room(room)
        if displayName in connected_users:
            del connected_users[displayName]
        emit('user_left', {'displayName': displayName}, room=room)

@socketio.on('message')
def handle_message(data):
    displayName = data.get('displayName')
    room = data.get('room')
    message = data.get('message')
    if displayName and room and message:
        emit('new_message', {
            'displayName': displayName,
            'message': message,
            'timestamp': str(datetime.now())
        }, room=room)
