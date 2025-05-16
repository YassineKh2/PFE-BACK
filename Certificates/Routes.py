from flask import Blueprint, request, jsonify
from Certificates.Functions import AddCertificate, GetCertificate, GetMyCertificates

CertificateRoutes = Blueprint('CertificateRoutes', __name__)

baseurl = "/certificate"


@CertificateRoutes.route(baseurl, methods=['GET', 'POST'])
def Certificates():
    if request.method == 'POST':
        response, status = AddCertificate(request)
        return jsonify(response), status


@CertificateRoutes.route(baseurl + "/<id>", methods=['GET', 'POST'])
def Certificate(id):
    if request.method == 'GET':
        response, status = GetCertificate(id)
        return jsonify(response), status


@CertificateRoutes.route(baseurl + "/mine/<id>", methods=['GET', 'POST'])
def MyCertificates(id):
    if request.method == 'GET':
        response, status = GetMyCertificates(id)
        return jsonify(response), status
