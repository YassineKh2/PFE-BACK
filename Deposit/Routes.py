from flask import Blueprint, request, jsonify
from Deposit.Functions import SaveDeposit


DepositRoutes = Blueprint('DepositRoutes', __name__)

baseurl = "/deposit"

@DepositRoutes.route(baseurl+"/<id>", methods=['GET','POST'])
def deposit(id):
    if request.method == 'POST':
        response = SaveDeposit(id,request)
        return response
