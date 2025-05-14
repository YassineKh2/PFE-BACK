from firebase_admin import firestore
from werkzeug.utils import secure_filename
import os
from datetime import datetime,timezone

def SaveCourse(request):
    try:
        # File handling logic
        if 'file' not in request.files:
            return {"error": "No file part in the request"}, 400
        file = request.files['file']
        if file.filename == '':
            return {"error": "No selected file"}, 400
        if file:
            filename = secure_filename(file.filename)
            random_filename = f"{os.urandom(16).hex()}_{filename}"
            save_path = os.path.join('static', 'Images', random_filename)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            file.save(save_path)
            data = request.form.to_dict()
            data['image'] = random_filename

            # Add createdAt and editedAt fields
            now = now = datetime.now(timezone.utc)
            data['createdAt'] = now
            data['editedAt'] = now
            data.pop('file', None)

            db = firestore.client()
            update_time, response = db.collection("courses").add(data)
            if response.id:
                return {"data": response.id, "file_path": save_path}, 200
            else:
                return {"error": "Failed to save course"}, 500
        else:
            return {"error": "File not found"}, 400
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500
    
def GetCourses():
    try:
        db = firestore.client()
        courses_ref = db.collection("courses")
        docs = courses_ref.stream()
        courses = []
        for doc in docs:
            course_data = doc.to_dict()
            course_data['id'] = doc.id
            courses.append(course_data)
        return courses
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500    
    
def GetCourse(id):
    try:
        db = firestore.client()
        doc_ref = db.collection("courses").document(id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            print(f"No document found for ID: {id}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def UpdateCourse(id, request):
    try:
        db = firestore.client()
        doc_ref = db.collection("courses").document(id)
        doc = doc_ref.get()
        if not doc.exists:
            return {"error": "Course not found"}, 404

        data = request.form.to_dict()
        now = now = datetime.now(timezone.utc)
        data['editedAt'] = now
        # File handling logic
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                filename = secure_filename(file.filename)
                random_filename = f"{os.urandom(16).hex()}_{filename}"
                save_path = os.path.join('static', 'Images', random_filename)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                file.save(save_path)

                # Delete old image if it exists
                course_data = doc.to_dict()
                if 'image' in course_data:
                    old_image_path = os.path.join('static', 'Images', course_data['image'])
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)

                data['image'] = random_filename
                data.pop('file', None)

        doc_ref.update(data)
        return {"message": "Course updated successfully"}, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500

def DeleteCourse(id):
    try:
        db = firestore.client()
        doc_ref = db.collection("courses").document(id)
        doc = doc_ref.get()
        if doc.exists:
            course_data = doc.to_dict()
            if 'image' in course_data:
                image_path = os.path.join('static', 'Images', course_data['image'])
                if os.path.exists(image_path):
                    os.remove(image_path)
            doc_ref.delete()
            return {"message": "Course deleted successfully"}, 200
        else:
            return {"error": "Course not found"}, 404
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500      