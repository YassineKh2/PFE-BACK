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


def GetStateCourses(id):
    try:
        db = firestore.client()
        user_ref = db.collection("users").document(id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            return None
        user_data = user_doc.to_dict()
        return user_data.get("enrolledCourses", {})
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def GetProgress(id):
    try:
        db = firestore.client()
        user_ref = db.collection("users").document(id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            return None
        user_data = user_doc.to_dict()
        enrolled_courses = user_data.get("enrolledCourses", {})
        progress_list = []
        for course_id, course_info in enrolled_courses.items():
            completed_chapters = course_info.get("completedChapters", [])
            current_chapter = None

            # Fetch chapters by course_id from the chapters collection
            chapters_query = db.collection("chapters").where("courseId", "==", course_id).order_by("order")
            chapters_docs = chapters_query.stream()
            chapters = [doc.id for doc in chapters_docs]
            total_chapters = len(chapters)

            # Calculate progress as percentage of completed chapters
            completed_count = sum(1 for ch in chapters if ch in completed_chapters)
            progress = (completed_count / total_chapters) * 100 if total_chapters > 0 else 0

            # Find the next chapter if the last completed is not the last chapter
            if chapters:
                if completed_chapters:
                    last_completed = completed_chapters[-1]
                    if last_completed in chapters:
                        idx = chapters.index(last_completed)
                        if idx < len(chapters) - 1:
                            current_chapter = chapters[idx + 1]
                        else:
                            current_chapter = last_completed
                    else:
                        current_chapter = chapters[0]
                else:
                    current_chapter = chapters[0]
            progress_list.append({
                "courseId": course_id,
                "progress": progress,
                "currentChapter": current_chapter
            })
        return progress_list
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    

def GetSingleProgress(id, course_id):
    try:
        db = firestore.client()
        user_ref = db.collection("users").document(id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            return None
        user_data = user_doc.to_dict()
        enrolled_courses = user_data.get("enrolledCourses", {})
        course_info = enrolled_courses.get(course_id)
        if not course_info:
            return None

        completed_chapters = course_info.get("completedChapters", [])
        current_chapter = None

        chapters_query = db.collection("chapters").where("courseId", "==", course_id).order_by("order")
        chapters_docs = chapters_query.stream()
        chapters = [doc.id for doc in chapters_docs]
        total_chapters = len(chapters)

        completed_count = sum(1 for ch in chapters if ch in completed_chapters)
        progress = (completed_count / total_chapters) * 100 if total_chapters > 0 else 0

        if chapters:
            if completed_chapters:
                last_completed = completed_chapters[-1]
                if last_completed in chapters:
                    idx = chapters.index(last_completed)
                    if idx < len(chapters) - 1:
                        current_chapter = chapters[idx + 1]
                    else:
                        current_chapter = last_completed
                else:
                    current_chapter = chapters[0]
            else:
                current_chapter = chapters[0]

        return {
            "courseId": course_id,
            "progress": progress,
            "currentChapter": current_chapter
        }
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def UpdateProgress(id,request):
    try:
        db = firestore.client()
        data = request.get_json() if request.is_json else request.form.to_dict()
        course_id = data.get('courseId')
        chapter_id = data.get('chapterId')

        if not course_id or not chapter_id:
            return {"error": "Missing courseId or chapterId in request"}, 400

        user_ref = db.collection("users").document(id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            return {"error": "User not found"}, 404

        user_data = user_doc.to_dict()
        enrolled_courses = user_data.get("enrolledCourses", {})
        course_info = enrolled_courses.get(course_id)
        if not course_info:
            return {"error": "User not enrolled in this course"}, 400

        completed_chapters = course_info.get("completedChapters", [])
        if chapter_id not in completed_chapters:
            completed_chapters.append(chapter_id)

        # Fetch all chapters for the course to calculate progress
        chapters_query = db.collection("chapters").where("courseId", "==", course_id).order_by("order")
        chapters_docs = chapters_query.stream()
        chapters = [doc.id for doc in chapters_docs]
        total_chapters = len(chapters)
        completed_count = sum(1 for ch in chapters if ch in completed_chapters)
        progress = (completed_count / total_chapters) * 100 if total_chapters > 0 else 0

        # Update the enrolledCourses.<course_id> map
        user_ref.update({
            f"enrolledCourses.{course_id}.completedChapters": completed_chapters,
            f"enrolledCourses.{course_id}.progress": progress,
            f"enrolledCourses.{course_id}.lastActive": datetime.now(timezone.utc).isoformat()
        })

        return {"message": "Progress updated successfully", "data": progress}, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500