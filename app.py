from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS
from uuid import uuid4
from flask_socketio import SocketIO, emit, join_room
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from gomoku_ai import GomokuGame

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Required for Flask-Login
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Hardcoded user credentials
users = {
    'admin': generate_password_hash('algorithmpit')  # Ensure this is generated at runtime
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(user_id)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in users:
            print(f"Stored hash for {username}: {users[username]}")  # Debug log
            print(f"Password hash matches: {check_password_hash(users[username], password)}")  # Debug log

        if username in users and check_password_hash(users[username], password):
            user = User(username)
            login_user(user)
            return jsonify({"message": "Login successful"})
        else:
            print("Invalid credentials")  # Debug log
            return jsonify({"message": "Invalid credentials"}), 401

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    next_page = request.referrer or url_for('home')
    return redirect(next_page)

@app.route('/protected')
@login_required
def protected():
    return jsonify({"message": f"Hello, {current_user.id}! This is a protected route."})

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/games')
def games():
    return render_template('games.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route("/gomoku")
def gomoku():
    return render_template("gomoku.html")

sessions = {}

@socketio.on('connect')
def handle_connect():
    user_id = str(uuid4())
    sessions[user_id] = GomokuGame()
    emit('init', {'user_id': user_id, 'board': sessions[user_id].board})
    print(f'new user connected: {user_id}')

    user_id = str(uuid4())
    sessions[user_id] = GomokuGame()
    join_room(request.sid)
    emit('init', {
        'user_id': user_id,
        'board': sessions[user_id].board
    }, room=request.sid)

    game = sessions.get(user_id)
    response = {
        'board': game.board,
    }
    emit('update', response)

@socketio.on('player_move')
def handle_player_move(data):
    user_id = data['user_id']
    x, y = data['x'], data['y']
    game = sessions.get(user_id)
    sid = request.sid

    if not game:
        print("Invalid user_id")
        emit('error', {'message': 'Invalid user_id'})
        return

    # Check if it's the player's turn
    if not game.is_player_turn:
        emit('error', {'message': 'Please wait for the AI to complete its move'})
        return

    if not game.place_piece(x, y, 1):
        print('Invalid move position')
        emit('error', {'message': 'Invalid move'})
        return

    # Update the game state and switch turn to AI
    game.is_player_turn = False
    response = {
        'board': game.board,
        'winner': game.winner,
        'move': {'x': x, 'y': y, 'player': 1}
    }
    if game.check_win(x, y, 1):
        response = {
            'board': game.board,
            'winner': game.winner,
            'move': {'x': x, 'y': y, 'player': 1}
        }

    emit('update', response)

    # Start AI move in the background
    socketio.start_background_task(_do_ai_move, user_id, sid)

def _do_ai_move(user_id, sid):
    """Background task: Calculate AI move and push to the specified sid"""
    game = sessions.get(user_id)
    if not game or game.winner != 0:
        return

    ai_x, ai_y = game.ai_move()
    game.is_player_turn = True  # Switch turn back to the player
    socketio.emit('update', {
        'board': game.board,
        'winner': game.winner,
        'ai_move': {'x': ai_x, 'y': ai_y, 'player': 2}
    }, room=sid)

@socketio.on('new_game')
def new_game(data):
    user_id = data['user_id']
    game = sessions.get(user_id)
    game.new_game()
    response = {
            'board': game.board,
        }

    emit('update', response)

@app.route("/tank")
def tank():
    return render_template("tank.html")

if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)