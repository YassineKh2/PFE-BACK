from flask import Blueprint, request, jsonify
from Comments.Functions import AddComment,GetComments,UpdateComment,GetAllComments

CommentsRoutes = Blueprint('CommentsRoutes', __name__)

baseurl = "/comment"


@CommentsRoutes.route(baseurl, methods=['GET', 'POST'])
def Comments():
    if request.method == 'POST':
        response, status = AddComment(request)
        return jsonify(response), status
    if request.method == 'GET':
        try:
            response = GetAllComments()
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@CommentsRoutes.route(baseurl + "/<courseId>", methods=['GET', 'POST'])
def Comment(courseId):
    if request.method == 'POST':
        response, status = UpdateComment(courseId, request)
        return jsonify(response), status
    if request.method == 'GET':
        try:
            response = GetComments(courseId)
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
