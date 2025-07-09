from firebase_admin import firestore


def GetLogs(userId):
    try:
        # Connect to Firestore
        db = firestore.client()

        # Query comments by course ID
        logs_ref = db.collection("logs").where("userId", "==", userId)
        docs = logs_ref.stream()
        return docs
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500
