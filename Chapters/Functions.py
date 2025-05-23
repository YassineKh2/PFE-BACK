from firebase_admin import firestore
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timezone
import threading
from Quizzes.Functions import create_and_save_quiz

def SaveChapter(request):
    try:
        db = firestore.client()
        data = request.form.to_dict()
        now = datetime.now(timezone.utc)
        data['createdAt'] = now
        data['editedAt'] = now

        # File handling logic
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                random_filename = f"{os.urandom(16).hex()}_{filename}"
                save_path = os.path.join('static', 'Images', random_filename)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                file.save(save_path)
                data['image'] = random_filename
                data.pop('file', None)

        # Get chapters for the same course to determine the order
        course_id = data.get("courseId")
        if course_id:
            chapters_ref = db.collection("chapters").where("courseId", "==", course_id)
            existing_chapters = list(chapters_ref.stream())
            data["order"] = str(len(existing_chapters) + 1)
        else:
            data["order"] = "1"

        # Update the course duration
        if course_id:
            course_ref = db.collection("courses").document(course_id)
            course_doc = course_ref.get()
            if course_doc.exists:
                course_data = course_doc.to_dict()
                current_duration = int(course_data.get("duration", 0))
                chapter_duration = int(data.get("duration", 0))
                new_duration = current_duration + chapter_duration
                course_ref.update({"duration": new_duration})

        date, response = db.collection("chapters").add(data)
        resp = {"data": response.id}, 200
        # Handle quiz creation in background
        def async_quiz():
            course_id = data.get("courseId")
            title = data.get("title", "")
            if course_id and title:
                create_and_save_quiz(course_id, title)
        threading.Thread(target=async_quiz).start()
        return resp
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500

def GetChapters():
    try:
        db = firestore.client()
        chapters_ref = db.collection("chapters")
        docs = chapters_ref.stream()
        chapters = []
        for doc in docs:
            chapter_data = doc.to_dict()
            chapter_data['id'] = doc.id
            chapters.append(chapter_data)
        return chapters
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500

def GetChapter(id):
    try:
        db = firestore.client()
        doc_ref = db.collection("chapters").document(id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        else:
            print(f"No document found for ID: {id}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def UpdateChapter(id, request):
    try:
        db = firestore.client()
        doc_ref = db.collection("chapters").document(id)
        doc = doc_ref.get()
        if not doc.exists:
            return {"error": "Chapter not found"}, 404

        chapter_data = doc.to_dict()
        data = request.form.to_dict()
        now = datetime.now(timezone.utc)
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
                old_image = chapter_data.get('image')
                if old_image:
                    old_image_path = os.path.join('static', 'Images', old_image)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)

                data['image'] = random_filename
                data.pop('file', None)

        # Use chapter_data to avoid multiple fetches
        course_id = data.get("courseId") or chapter_data.get("courseId")

        # Fetch all chapters for the course once if needed
        chapters = []
        if course_id and ("order" in data or "duration" in data):
            chapters_ref = db.collection("chapters").where("courseId", "==", course_id)
            chapters = [c for c in chapters_ref.stream()]

        # Handle order update
        if "order" in data:
            new_order = int(data["order"])
            # Exclude current chapter and get orders
            other_chapters = [c for c in chapters if c.id != id]
            orders = [int(c.to_dict().get("order", 0)) for c in other_chapters]
            if new_order in orders:
                for c in other_chapters:
                    c_order = int(c.to_dict().get("order", 0))
                    if c_order >= new_order:
                        db.collection("chapters").document(c.id).update({"order": str(c_order + 1)})
            data["order"] = str(new_order)

        # Update the course duration if duration is changed
        if course_id and "duration" in data:
            course_ref = db.collection("courses").document(course_id)
            course_doc = course_ref.get()
            if course_doc.exists:
                course_data = course_doc.to_dict()
                old_chapter_duration = int(chapter_data.get("duration", 0))
                new_chapter_duration = int(data.get("duration", 0))
                current_course_duration = int(course_data.get("duration", 0))
                updated_course_duration = current_course_duration - old_chapter_duration + new_chapter_duration
                course_ref.update({"duration": updated_course_duration})

        doc_ref.update(data)
        # Call create_and_save_quiz after updating a chapter
        course_id = data.get("courseId") or chapter_data.get("courseId")
        title = data.get("title") or chapter_data.get("title", "")
        resp = {"data": "chapter updated !"}, 200
        # Handle quiz creation in background
        def async_quiz():
            if course_id and title:
                create_and_save_quiz(course_id, title)
        threading.Thread(target=async_quiz).start()
        return resp
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500

def DeleteChapter(id):
    try:
        db = firestore.client()
        doc_ref = db.collection("chapters").document(id)
        doc = doc_ref.get()
        if not doc.exists:
            return {"error": "Chapter not found"}, 404

        # Delete the associated image file if it exists
        chapter_data = doc.to_dict()
        if chapter_data and 'file' in chapter_data:
            image_path = os.path.join('static', 'Images', chapter_data['file'])
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as file_err:
                    print(f"Failed to delete image: {file_err}")

        # Reorder the remaining chapters in the same course
        course_id = chapter_data.get("courseId")
        if course_id:
            chapters_ref = db.collection("chapters").where("courseId", "==", course_id)
            chapters = [c for c in chapters_ref.stream() if c.id != id]
            # Sort chapters by order (as int), but store as string
            chapters_sorted = sorted(chapters, key=lambda c: int(c.to_dict().get("order", "0")))
            for idx, c in enumerate(chapters_sorted, start=1):
                db.collection("chapters").document(c.id).update({"order": str(idx)})

        # Update the course duration after deleting the chapter
        if course_id:
            course_ref = db.collection("courses").document(course_id)
            course_doc = course_ref.get()
            if course_doc.exists:
                course_data = course_doc.to_dict()
                current_duration = int(course_data.get("duration", 0))
                chapter_duration = int(chapter_data.get("duration", 0))
                new_duration = max(0, current_duration - chapter_duration)
                course_ref.update({"duration": new_duration})

        # Delete the document from Firestore
        db.collection("chapters").document(id).delete()
        # Call create_and_save_quiz after deleting a chapter
        chapter_data = doc.to_dict()
        course_id = chapter_data.get("courseId")
        title = chapter_data.get("title", "")
        resp = {"data": "chapter deleted !"}, 200
        # Handle quiz creation in background
        def async_quiz():
            if course_id and title:
                create_and_save_quiz(course_id, title)
        threading.Thread(target=async_quiz).start()
        return resp
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500

def GetChapterByCourse(course_id):
    try:
        db = firestore.client()
        chapters_ref = db.collection("chapters").where("courseId", "==", course_id).order_by("order")
        docs = chapters_ref.stream()
        chapters = []
        for doc in docs:
            chapter_data = doc.to_dict()
            chapter_data['id'] = doc.id
            chapters.append(chapter_data)
        return chapters
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500