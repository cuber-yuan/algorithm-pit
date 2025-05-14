from flask_login import UserMixin
from werkzeug.security import generate_password_hash

users = {
    'admin': generate_password_hash('algorithmpit')
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id