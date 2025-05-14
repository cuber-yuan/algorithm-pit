from flask import Flask
from flask_socketio import SocketIO
from flask_login import LoginManager
from flask_cors import CORS

socketio = SocketIO(cors_allowed_origins="*")
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object('config.Config')  
    
    CORS(app)
    socketio.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from .main import main_bp
    from .auth import auth_bp
    from .upload import upload_bp
    from .gomoku import gomoku_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(gomoku_bp)

    return app