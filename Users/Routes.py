from flask import Blueprint, request, jsonify
from Users.Functions import Enroll,GetCourses


UsersRoutes = Blueprint('UsersRoutes', __name__)

baseurl = "/user"

@UsersRoutes.route(baseurl+"/enroll/<id>", methods=['GET', 'POST'])
def Courses(id):
    if request.method == 'POST':
        response, status = Enroll(id,request)
        return jsonify(response), status
    if request.method == 'GET':
        try:
            response = GetCourses(id)
            if response is None:
                return jsonify({"message": "No courses found"}), 404
            
            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

       