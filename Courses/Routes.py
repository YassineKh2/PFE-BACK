from flask import Blueprint, request, jsonify
from Courses.Functions import SaveCourse,GetCourses,GetCourse,UpdateCourse,DeleteCourse,GetCourseStatistics

CoursesRoutes = Blueprint('CoursesRoutes', __name__)

baseurl = "/course"

@CoursesRoutes.route(baseurl, methods=['GET', 'POST'])
def courses():
    if request.method == 'POST':
        response, status = SaveCourse(request)
        return jsonify(response), status
    if request.method == 'GET':
        try:
            response = GetCourses()
            if response is None:
                return jsonify({"message": "No courses found"}), 404
            
            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    

@CoursesRoutes.route(baseurl+"/<id>", methods=['GET',"POST", 'DELETE'])
def course(id):
    if request.method == 'POST':
        response, status = UpdateCourse(id, request)
        return jsonify(response), status
       
       
    if request.method == 'GET':
        
        response = GetCourse(id)
        if response is None:
            return jsonify({"message": "No course found"}), 404
            
        return jsonify({"data": response}), 200

 
    if request.method == 'DELETE':
        
        response, status = DeleteCourse(id)
        return jsonify(response), status


@CoursesRoutes.route(baseurl + "/stats/<id>", methods=['GET', "POST", 'DELETE'])
def CourseStatistics(id):
    if request.method == 'GET':
        response = GetCourseStatistics(id)
        if response is None:
            return jsonify({"message": "No course found"}), 404

        return jsonify({"data": response}), 200

