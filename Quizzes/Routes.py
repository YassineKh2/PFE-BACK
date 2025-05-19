from flask import Blueprint, request, jsonify

QuizzesRoutes = Blueprint('QuizzesRoutes', __name__)

baseurl = "/quiz"

# @QuizzesRoutes.route(baseurl, methods=['GET', 'POST'])
# def courses():
#     if request.method == 'GET':
#         try:
#             response = GetCourses()
#             if response is None:
#                 return jsonify({"message": "No courses found"}), 404
#
#             return jsonify({"data": response}), 200
#         except Exception as e:
#             return jsonify({"error": str(e)}), 500

