from flask import Blueprint, request, jsonify
from Deposit.Functions import SaveDeposit,get_available_funds,add_funds,buy_asset,get_assets,get_portfolio_metrics,get_assets_with_fund_info

DepositRoutes = Blueprint('DepositRoutes', __name__)

baseurl = "/deposit"

@DepositRoutes.route(baseurl+"/<id>", methods=['GET','POST'])
def deposit(id):
    if request.method == 'POST':
        response = SaveDeposit(id,request)
        return response

@DepositRoutes.route(baseurl+"/availableFunds/<id>", methods=['GET','POST'])
def available_funds(id):
     if request.method == 'GET':
        response = get_available_funds(id)
        return jsonify({'data': response})
     if request.method == 'POST':
        response = add_funds(id,request)
        return response

@DepositRoutes.route(baseurl+"/buyAsset/<user_id>", methods=['POST'])
def BuyAsset(user_id):
    asset_data = request.get_json(force=True, silent=True)
    response, status = buy_asset(user_id, asset_data)
    return jsonify(response), status

@DepositRoutes.route(baseurl+"/getAssets/<user_id>", methods=['GET'])
def get_user_assets(user_id):
    response, status = get_assets(user_id)
    return jsonify(response), status

@DepositRoutes.route(baseurl+"/portfolioMetrics/<user_id>", methods=['GET'])
def get_portfolio_metrics_route(user_id):
    response, status = get_portfolio_metrics(user_id)
    return jsonify(response), status

@DepositRoutes.route(baseurl+"/userAssetsInfo/<user_id>", methods=['GET'])
def user_assets_info(user_id):
    response, status = get_assets_with_fund_info(user_id)
    return jsonify(response), status
