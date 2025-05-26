from flask import Blueprint, request, jsonify


DepositRoutes = Blueprint('DepositRoutes', __name__)

@DepositRoutes.route("/<id>", methods=['GET','POST'])
def deposit(id):
    if request.method == 'POST':
        print('hi')
