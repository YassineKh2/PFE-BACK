from firebase_admin import firestore
from datetime import datetime, timezone


def AddComment(request):
    try:
        # Parse JSON body
        data = request.get_json()
        if not data:
            return {"error": "Invalid JSON body"}, 400

        # Add timestamps
        now = datetime.now(timezone.utc).isoformat()
        data["createdAt"] = now
        data["updatedAt"] = None

        # Save to Firestore
        db = firestore.client()
        comment_ref = db.collection("comments").add(data)

        return {"data": comment_ref[1].id}, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def GetComments(courseId):
    try:
        # Connect to Firestore
        db = firestore.client()

        # Query comments by course ID
        comments_ref = db.collection("comments").where("courseId", "==", courseId)
        docs = comments_ref.stream()

        # Collect all matching comments
        comments = []
        for doc in docs:
            comment_data = doc.to_dict()
            comment_data["id"] = doc.id
            comments.append(comment_data)

        return {"data": comments}, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def UpdateComment(id, request):
    try:
        # Parse JSON body
        data = request.get_json()
        if not data:
            return {"error": "Invalid JSON body"}, 400

        # Validate required fields
        if "content" not in data:
            return {"error": "Missing required field: content"}, 400

        # Update the comment
        db = firestore.client()
        comment_ref = db.collection("comments").document(id)
        if not comment_ref.get().exists:
            return {"error": "Comment not found"}, 404

        update_data = {
            "content": data["content"],
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        comment_ref.update(update_data)

        return {"message": "Comment updated successfully"}, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def GetAllComments():
    try:
        # Connect to Firestore
        db = firestore.client()

        # Query all comments
        comments_ref = db.collection("comments")
        docs = comments_ref.stream()

        # Collect all comments
        comments = []
        for doc in docs:
            comment_data = doc.to_dict()
            comment_data["id"] = doc.id
            comments.append(comment_data)

        return comments
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500
