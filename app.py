import json

from flask import Flask
from flask_cors import CORS
from Predictions.Routes import MutualFundsRoutes
from Courses.Routes import CoursesRoutes
from Chapters.Routes import ChaptersRoutes
from Users.Routes import UsersRoutes
from Certificates.Routes import CertificateRoutes
from Comments.Routes import CommentsRoutes
from Firebase import setupfirebase


app = Flask(__name__)
CORS(app)
app.register_blueprint(MutualFundsRoutes)
app.register_blueprint(CoursesRoutes)
app.register_blueprint(ChaptersRoutes)
app.register_blueprint(UsersRoutes)
app.register_blueprint(CertificateRoutes)
app.register_blueprint(CommentsRoutes)
setupfirebase()





if __name__ == '__main__':

    app.run(debug=True)
