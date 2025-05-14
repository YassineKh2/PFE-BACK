from flask import Blueprint, request, jsonify
from Chapters.Functions import SaveChapter, GetChapters, UpdateChapter, GetChapterByCourse, DeleteChapter,GetChapter

ChaptersRoutes = Blueprint('ChaptersRoutes', __name__)

baseurl = "/chapter"


@ChaptersRoutes.route(baseurl, methods=['POST', 'GET'])
def courses():
    if request.method == 'POST':
        response, status = SaveChapter(request)
        return jsonify(response), status
    if request.method == 'GET':
        try:
            response = GetChapters()
            if response is None:
                return jsonify({"message": "No courses found"}), 404

            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@ChaptersRoutes.route(baseurl+"/<id>", methods=['POST', 'GET', "DELETE"])
def course(id):
    if request.method == 'POST':
        response, status = UpdateChapter(id, request)
        return jsonify(response), status

    if request.method == 'GET':
        response = GetChapterByCourse(id)
        if response is None:
            return jsonify({"message": "No course found"}), 404

        return jsonify({"data": response}), 200
    if request.method == 'DELETE':
        response, status = DeleteChapter(id)
        return jsonify(response), status

@ChaptersRoutes.route(baseurl+"/single/<id>", methods=['GET'])
def course_by_id(id):
    if request.method == 'GET':
        response = GetChapter(id)
        if response is None:
            return jsonify({"message": "No course found"}), 404

        return jsonify({"data": response}), 200