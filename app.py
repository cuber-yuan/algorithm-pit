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
    sid     = request.sid   # 当前连接的 socket id

    if not game:
        emit('error', {'message': '无效 user_id'})
        #return

    if not game.place_piece(x, y, 1):
        emit('error', {'message': '落子无效'})
        #return

    response = {
        'board': game.board,
        'winner': game.winner,
        'move': {'x': x, 'y': y, 'player': 1}
    }

    emit('update', response)

    socketio.start_background_task(_do_ai_move, user_id, sid)

    

def _do_ai_move(user_id, sid):
    """后台任务：计算 AI 落子并推送给指定 sid"""
    game = sessions.get(user_id)
    if not game or game.winner != 0:
        return

    # 耗时计算
    ai_x, ai_y = game.ai_move()

    # 直接向 room=sid 的客户端发消息
    socketio.emit('update', {
        'board':   game.board,
        'winner':  game.winner,
        'ai_move': {'x': ai_x, 'y': ai_y, 'player': 2}
    }, room=sid)

@app.route('/gomoku/new_game', methods=['GET'])
def new_game():
    user_id = str(uuid4())
    sessions[user_id] = GomokuGame()
    return jsonify({'user_id': user_id})



@app.route('/gomoku/get_move', methods=['POST'])
def get_move():
    data = request.get_json()
    user_id = data.get('user_id')
    x, y = data.get('x'), data.get('y')
    game = sessions.get(user_id)

    if not game:
        return jsonify({'error': 'invalid user_id'}), 400

    if not game.place_piece(x, y, 1):
        return jsonify({'error': 'invalid move'}), 400

    print("debug")
    print(data)
    ai_x, ai_y = game.ai_move() if game.winner == 0 else (None, None)

    return jsonify({
        'board': game.board,
        'current_player': game.current_player,
        'winner': game.winner,
        'ai_move': {'x': ai_x, 'y': ai_y}
    })

@app.route("/tank")
def tank():
    return render_template("tank.html")

if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)