from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from uuid import uuid4
from flask_socketio import SocketIO, emit, join_room

from gomoku_ai import GomokuGame

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

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
        print("userid 出错")
        emit('error', {'message': '无效 user_id'})
        return

    # Check if it's the player's turn
    if not game.is_player_turn:
        emit('error', {'message': '请等待 AI 落子完成'})
        return

    if not game.place_piece(x, y, 1):
        print('落子在无效位置')
        emit('error', {'message': '落子无效'})
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
    """后台任务：计算 AI 落子并推送给指定 sid"""
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