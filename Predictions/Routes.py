from flask import Blueprint, request, jsonify
from Predictions.Functions import forecast_from_data,SavePredictions,GetPredictions


MutualFundsRoutes = Blueprint('MutualFundsRoutes', __name__)

@MutualFundsRoutes.route("/predict/<id>", methods=['GET','POST'])
def predict(id):
    if request.method == 'POST':
        try:
            data = request.get_json() 
            prediction = forecast_from_data(data)
            response = SavePredictions(id, prediction)  
            if(response):
                return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    if request.method == 'GET':
        try:
            response = GetPredictions(id)
            if response is None:
                return jsonify({"message": "No predictions found"}), 404
            
            return jsonify({"data": response}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
