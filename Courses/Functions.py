from firebase_admin import firestore
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timezone, timedelta
from Users.Functions import GetProgress,GetSingleProgress
import json


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

        # Ensure enrolledStudents is always an array
        if 'enrolledStudents' in data and not isinstance(data['enrolledStudents'], list):
            data['enrolledStudents'] = [s.strip() for s in data['enrolledStudents'].split(',') if s.strip()]

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

def GetCourseStatistics(course_id):
    try:
        db = firestore.client()
        course_ref = db.collection("courses").document(course_id)
        course_doc = course_ref.get()
        if not course_doc.exists:
            return {"error": "Course not found"}, 404

        course_data = course_doc.to_dict()
        enrolled_students = course_data.get("enrolledStudents", [])
        total_enrolled = len(enrolled_students)

        # Calculate overall completion rate
        total_completion = 0
        for user_id in enrolled_students:
            user_progress = GetProgress(user_id)
            if user_progress:
                course_progress = next((item for item in user_progress if item.get("courseId") == course_id), None)
                if course_progress:
                    total_completion += course_progress.get("progress", 0)
        completion_rate = (total_completion / total_enrolled) if total_enrolled > 0 else 0

        # Calculate enrollment rate this month, average completion time, and dropout rate
        users_ref = db.collection("users")
        users_docs = users_ref.stream()
        enrolled_this_month = 0
        completion_times = []
        dropout_count = 0
        now = datetime.now(timezone.utc)
        two_months_ago = now - timedelta(days=60)
        for user_doc in users_docs:
            user_data = user_doc.to_dict()
            enrolled_courses = user_data.get("enrolledCourses", {})
            course_info = enrolled_courses.get(course_id)
            if course_info:
                enrolled_at = course_info.get("enrolledAt")
                finished_at = course_info.get("finishedAt")
                progress = course_info.get("progress", 0)
                # Enrolled this month
                if enrolled_at:
                    try:
                        enrolled_at_dt = datetime.fromisoformat(enrolled_at)
                        if enrolled_at_dt.year == now.year and enrolled_at_dt.month == now.month:
                            enrolled_this_month += 1
                    except Exception:
                        pass
                # Average completion time for those who finished
                if enrolled_at and finished_at and progress == 100:
                    try:
                        enrolled_at_dt = datetime.fromisoformat(enrolled_at)
                        finished_at_dt = datetime.fromisoformat(finished_at)
                        completion_time = (finished_at_dt - enrolled_at_dt).total_seconds() / 3600  # in hours
                        completion_times.append(completion_time)
                    except Exception:
                        pass
                # Dropout: not finished and enrolledAt > 2 months ago
                if enrolled_at and (progress < 100 or not finished_at):
                    try:
                        enrolled_at_dt = datetime.fromisoformat(enrolled_at)
                        if enrolled_at_dt < two_months_ago:
                            dropout_count += 1
                    except Exception:
                        pass

        avg_completion_time = (sum(completion_times) / len(completion_times)) if completion_times else 0
        dropout_rate = (dropout_count / total_enrolled) * 100 if total_enrolled > 0 else 0

        return {
            "totalEnrolled": total_enrolled,
            "completionRate": completion_rate,
            "enrolledThisMonth": enrolled_this_month,
            "averageCompletionTimeHours": avg_completion_time,
            "dropoutRate": dropout_rate
        }, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def GetEnrolledStudents(course_id):
    try:
        db = firestore.client()
        course_ref = db.collection("courses").document(course_id)
        course_doc = course_ref.get()

        if not course_doc.exists:
            return {"error": "Course not found"}, 404

        course_data = course_doc.to_dict()
        enrolled_students = course_data.get("enrolledStudents", [])

        students_data = []
        for user_id in enrolled_students:
            # Retrieve the full user object
            user_ref = db.collection("users").document(user_id)
            user_doc = user_ref.get()
            if not user_doc.exists:
                continue

            user_data = user_doc.to_dict()
            user_data["id"] = user_id  # Include the user ID

            # Retrieve the progress for the course
            progress = GetSingleProgress(user_id, course_id)
            user_data["progress"] = progress if progress else {}

            students_data.append(user_data)

        return {"students": students_data}, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500