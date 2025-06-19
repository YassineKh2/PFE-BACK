from datetime import datetime
from typing import Dict, List, Optional

# In-memory storage for messages (you might want to use a database in production)
chat_history: Dict[str, List[Dict]] = {}

def save_message(room: str, username: str, message: str) -> Dict:
    """
    Save a message to the chat history
    """
    message_data = {
        'username': username,
        'message': message,
        'timestamp': str(datetime.now())
    }
    
    if room not in chat_history:
        chat_history[room] = []
    
    chat_history[room].append(message_data)
    return message_data

def get_chat_history(room: str) -> List[Dict]:
    """
    Get chat history for a specific room
    """
    return chat_history.get(room, [])