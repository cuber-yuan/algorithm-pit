from flask import Blueprint, request
from . import socketio
from .services.gomoku_ai import GomokuGame
from uuid import uuid4
from flask_socketio import emit, join_room

gomoku_bp = Blueprint('gomoku', __name__)

sessions = {}

def register_gomoku_events(socketio):
    @socketio.on('connect', namespace='/gomoku')
    def handle_connect():
        user_id = str(uuid4())
        sessions[user_id] = GomokuGame()
        join_room(request.sid)
        emit('init', {
            'user_id': user_id,
            'board': sessions[user_id].board
        }, room=request.sid)
        print(f'new gomoku user connected: {user_id}')

    @socketio.on('player_move', namespace='/gomoku')
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
            response['winner'] = game.winner

        emit('update', response)
        
        ai_x, ai_y = game.ai_move()
        game.is_player_turn = True
        emit('update', {
            'board': game.board,
            'winner': game.winner,
            'ai_move': {'x': ai_x, 'y': ai_y, 'player': 2}
        }, room=sid)


    @socketio.on('new_game', namespace='/gomoku')
    def new_game(data):
        user_id = data['user_id']
        game = sessions.get(user_id)
        if not game:
            emit('error', {'message': 'Invalid user_id'})
            return

        game.new_game()
        response = {
            'board': game.board,
        }
        emit('update', response)

    @socketio.on('disconnect', namespace='/gomoku')
    def handle_disconnect():
        for user_id, game in list(sessions.items()):
            if game.sid == request.sid:
                del sessions[user_id]
                print(f'User {user_id} disconnected and session cleaned up')
                break