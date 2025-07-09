from datetime import datetime
from typing import Dict, List, Optional
from firebase_admin import firestore


def save_message(chatid: str, message: Dict) -> Dict:
    try:
        db = firestore.client()
        chat_ref = db.collection("chats").document(chatid)
        chat_doc = chat_ref.get()
        if not chat_doc.exists:
            return {"error": "Chat not found"}, 404

        chat_ref.update({
            "messages": firestore.ArrayUnion([message])
        })
        return message, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500



def GetChatId(userId1: str, userId2: str):
    try:
        db = firestore.client()

        chats_ref = db.collection("chats")
        query = chats_ref.where("iduser1", "in", [userId1, userId2]).where("iduser2", "in", [userId1, userId2])
        results = query.get()

        for chat_doc in results:
            chat_data = chat_doc.to_dict()
            chat_data['chatId'] = chat_doc.id 
            return chat_data, 200

        return {"error": "Chat not found"}, 404
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500