from flask import Blueprint, request, jsonify
from Logs.Functions import GetLogs

logsRoutes = Blueprint('logsRoutes', __name__)

baseurl = "/logs"

@logsRoutes.route(baseurl + "/<userId>", methods=['GET', 'POST'])
def logs(userId):
    if request.method == 'GET':
        try:
            response = GetLogs(userId)
            if response is None:
                return jsonify({"message": "No logs found"}), 404

            return response
        except Exception as e:
            return jsonify({"error": str(e)}), 500
