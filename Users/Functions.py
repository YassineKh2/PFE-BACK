from firebase_admin import firestore
from datetime import datetime, timezone

def Enroll(id, request):
    try:
        db = firestore.client()
        data = request.get_json() if request.is_json else request.form.to_dict()
        course_id = data.get('courseId')
        if not course_id:
            return {"error": "Missing courseId in request"}, 400

        # Add course to user's enrolledCourses array as a map with additional attributes
        user_ref = db.collection("users").document(id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            return {"error": "User not found"}, 404

        # Prepare the course enrollment data
        course_enrollment = {
            "idCourse": course_id,
            "completedChapters": [],
            "progress": 0,
            "enrolledAt": datetime.now(timezone.utc).isoformat(),
            "lastActive": datetime.now(timezone.utc).isoformat()
        }

        # Update the user's enrolledCourses map
        user_ref.update({
            f"enrolledCourses.{course_id}": course_enrollment
        })

        # Add user to course's enrolledStudents array
        course_ref = db.collection("courses").document(course_id)
        course_doc = course_ref.get()
        if not course_doc.exists:
            return {"error": "Course not found"}, 404
        course_ref.update({
            "enrolledStudents": firestore.ArrayUnion([id])
        })

        return {"message": "Enrollment successful"}, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def GetCourses(id):
    try:
        db = firestore.client()
        user_ref = db.collection("users").document(id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            return None
        user_data = user_doc.to_dict()
        enrolled_courses = user_data.get("enrolledCourses", [])
        courses = []
        for course_id in enrolled_courses:
            course_ref = db.collection("courses").document(course_id)
            course_doc = course_ref.get()
            if course_doc.exists:
                course = course_doc.to_dict()
                course['id'] = course_id
                courses.append(course)
        return courses
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
