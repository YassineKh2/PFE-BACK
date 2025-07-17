from flask import Blueprint, request, jsonify
from Deposit.Functions import SaveDeposit,get_available_funds,add_funds,buy_asset,get_assets,get_portfolio_metrics,get_assets_with_fund_info,sell_asset,get_single_asset_info,get_quick_stats,get_managed_users_assets,get_manager_stats

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

@DepositRoutes.route(baseurl+"/sellAsset/<user_id>", methods=['POST'])
def sell_asset_route(user_id):
    sell_data = request.get_json(force=True, silent=True)
    response, status = sell_asset(user_id, sell_data)
    return jsonify(response), status

@DepositRoutes.route(baseurl+"/singleAssetInfo/<user_id>", methods=['POST'])
def single_asset_info(user_id):
    data = request.get_json(force=True, silent=True)
    response, status = get_single_asset_info(user_id, data)
    return jsonify(response), status

@DepositRoutes.route(baseurl+"/quickStats/<user_id>", methods=['GET'])
def quick_stats_route(user_id):
    response, status = get_quick_stats(user_id)
    return jsonify(response), status

@DepositRoutes.route(baseurl+"/managedUsersAssets/<manager_id>", methods=['GET'])
def managed_users_assets_route(manager_id):
    response, status = get_managed_users_assets(manager_id)
    return jsonify(response), status

@DepositRoutes.route(baseurl+"/managerStats/<manager_id>", methods=['GET'])
def manager_stats_route(manager_id):
    response, status = get_manager_stats(manager_id)
    return jsonify(response), status
