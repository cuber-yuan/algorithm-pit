from flask import Blueprint, request
from . import socketio
from .services.gomoku_ai import GomokuGame
from uuid import uuid4
from flask_socketio import emit, join_room

gomoku_bp = Blueprint('gomoku', __name__)

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
        emit('error', {'message': 'Invalid user_id'})
        return

    if not game.is_player_turn:
        emit('error', {'message': 'Please wait for the AI to complete its move'})
        return

    if not game.place_piece(x, y, 1):
        emit('error', {'message': 'Invalid move'})
        return

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
    socketio.start_background_task(_do_ai_move, user_id, sid)

def _do_ai_move(user_id, sid):
    game = sessions.get(user_id)
    if not game or game.winner != 0:
        return

    ai_x, ai_y = game.ai_move()
    game.is_player_turn = True
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