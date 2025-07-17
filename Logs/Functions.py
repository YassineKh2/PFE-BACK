from firebase_admin import firestore


def GetLogs(userId):
    try:
        db = firestore.client()

        logs_ref = db.collection("logs").where("userId", "==", userId)
        docs = logs_ref.stream()
        logs = []
        for doc in docs:
            logs_data = doc.to_dict()
            logs_data["id"] = doc.id
            logs.append(logs_data)

        return logs
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500
