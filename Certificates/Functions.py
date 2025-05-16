from firebase_admin import firestore
from datetime import datetime, timezone


def AddCertificate(request):
    try:
        # Parse JSON body
        data = request.get_json()
        if not data:
            return {"error": "Invalid JSON body"}, 400

        # Save to Firestore
        db = firestore.client()

        idCertif = data.get("certificateNumber")
        prepared_data = {
            "certificateNumber": data.get("certificateNumber"),
            "courseName": data.get("courseName"),
            "completionDate": data.get("completionDate"),
            "instructorName": data.get("instructorName"),
            "userName": data.get("userName"),
            "idUser": data.get("idUser"),
            "issuedAt": datetime.now(timezone.utc).isoformat(),
            "courseId": data.get("courseId"),
            "CourseDescription": data.get("CourseDescription"),
            "courseImage": data.get("courseImage")
        }

        # Save the certificate document
        db.collection("certificates").document(idCertif).set(prepared_data)

        # Update the user's enrolledCourses
        idUser = data.get("idUser")
        courseId = data.get("courseId")
        finished_at = datetime.now(timezone.utc).isoformat()

        user_ref = db.collection("users").document(idUser)
        user_doc = user_ref.get()

        if user_doc.exists:
            user_data = user_doc.to_dict()
            enrolled_courses = user_data.get("enrolledCourses", [])

            # Update the course with finishedAt
            for course in enrolled_courses:
                if course.get("courseId") == courseId:
                    course["finishedAt"] = finished_at
                    break

            # Save the updated enrolledCourses back to Firestore
            user_ref.update({"enrolledCourses": enrolled_courses})

        # Return success response
        return {"data": idCertif}, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def GetCertificate(id):
    try:
        # Connect to Firestore
        db = firestore.client()

        # Retrieve the document by ID
        doc_ref = db.collection("certificates").document(id)
        doc = doc_ref.get()

        if doc.exists:
            # Return the document data
            certificate_data = doc.to_dict()
            return certificate_data, 200
        else:
            # Document not found
            return {"error": "Certificate not found"}, 404
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500


def GetMyCertificates(id):
    try:
        # Connect to Firestore
        db = firestore.client()

        # Query certificates by userId
        certificates_ref = db.collection("certificates")
        query = certificates_ref.where("idUser", "==", id)
        docs = query.stream()

        # Collect all matching certificates
        certificates = []
        for doc in docs:
            certificate_data = doc.to_dict()
            certificate_data['id'] = doc.id  # Include the document ID
            certificates.append(certificate_data)

        return {"data": certificates}, 200
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}, 500
