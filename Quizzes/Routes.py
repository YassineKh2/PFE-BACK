from flask import Blueprint, request, jsonify
from Quizzes.Functions import get_quizzes_by_course

QuizzesRoutes = Blueprint('QuizzesRoutes', __name__)

baseurl = "/quiz"

@QuizzesRoutes.route(baseurl+"/<id>", methods=['GET', 'POST'])
def Quizzes(id):
    if request.method == 'GET':
        try:
            response = get_quizzes_by_course(id)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

