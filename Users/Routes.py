from flask import Blueprint, request, jsonify
from Users.Functions import Enroll, GetCourses, GetStateCourses, GetProgress, GetSingleProgress, UpdateProgress, \
    GetUserLearningStats, GetRecentActivity, GetAll, SavePreferences, GetInformation, SaveSystemPreferences, UpdateSystemPreferencesRefused

UsersRoutes = Blueprint('UsersRoutes', __name__)

baseurl = "/user"


@UsersRoutes.route(baseurl + "/enroll/<id>", methods=['GET', 'POST'])
def Courses(id):
    if request.method == 'POST':
        response, status = Enroll(id, request)
        return jsonify(response), status
    if request.method == 'GET':
        try:
            response = GetCourses(id)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@UsersRoutes.route(baseurl + "/courses/<id>", methods=['GET', 'POST'])
def EnrolledCourses(id):
    if request.method == 'GET':
        try:
            response = GetStateCourses(id)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@UsersRoutes.route(baseurl + "/progress/<id>", methods=['GET', 'POST'])
def Progress(id):
    if request.method == 'GET':
        try:
            response = GetProgress(id)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    if request.method == 'POST':
        response, status = UpdateProgress(id, request)
        return jsonify(response), status


@UsersRoutes.route(baseurl + "/progress/single/<id>/<courseid>", methods=['GET', 'POST'])
def SingleProgress(id, courseid):
    if request.method == 'GET':
        try:
            response = GetSingleProgress(id, courseid)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@UsersRoutes.route(baseurl + "/progress/overall/<id>", methods=['GET', 'POST'])
def OverAllProgress(id):
    if request.method == 'GET':
        try:
            response = GetUserLearningStats(id)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@UsersRoutes.route(baseurl + "/activity/<id>", methods=['GET'])
def Activity(id):
    if request.method == 'GET':
        try:
            response = GetRecentActivity(id)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@UsersRoutes.route(baseurl + "/all", methods=['GET'])
def Users():
    if request.method == 'GET':
        try:
            response = GetAll()
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@UsersRoutes.route(baseurl + "/preferences/<id>", methods=['GET', 'POST'])
def Preferences(id):
    if request.method == 'POST':
        try:
            response = SavePreferences(id, request)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@UsersRoutes.route(baseurl + "/systempreferences/<id>", methods=['GET', 'POST'])
def SystemPreferences(id):
    if request.method == 'POST':
        try:
            response = SaveSystemPreferences(id, request)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@UsersRoutes.route(baseurl + "/systempreferences/refuse/<id>", methods=['GET', 'POST'])
def RefuseSystemPreferences(id):
    if request.method == 'POST':
        try:
            response = UpdateSystemPreferencesRefused(id)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@UsersRoutes.route(baseurl + "/<id>", methods=['GET', 'POST'])
def User(id):
    if request.method == 'GET':
        try:
            response = GetInformation(id)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify(response)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
