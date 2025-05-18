from flask import Blueprint, request
from . import socketio
from .tank2_judge import TankBotInterface
from uuid import uuid4
from flask_socketio import emit, join_room

tank_bp = Blueprint('tank', __name__)

sessions = {}

def register_tank_events(socketio):
    @socketio.on('connect', namespace='/tank2')
    def handle_connect():
        user_id = str(uuid4())
        sessions[user_id] = TankBotInterface()
        join_room(request.sid)
        emit('init', {
            'user_id': user_id,
            'state': sessions[user_id].send_to_client(True, 0)
        }, room=request.sid)
        print(f'New tank2 user connected: {user_id}')

    @socketio.on('player_move', namespace='/tank2')
    def handle_player_move(data):
        user_id = data['user_id']
        move = data.get('move')
        game = sessions.get(user_id)
        sid = request.sid

        if not game:
            emit('error', {'message': 'Invalid user_id'})
            return

        if not game.is_player_turn:
            emit('error', {'message': 'Please wait for the AI to complete its move'})
            return

        # Process the player's move
        if not game.process_player_move(move):
            emit('error', {'message': 'Invalid move'})
            return

        response = {
            'state': game.get_state(),
            'move': move
        }

        # Check if the player has won
        if game.check_winner():
            response['winner'] = 'player'
            emit('update', response, room=sid)
            return

        emit('update', response, room=sid)

        # Start AI move in the background
        socketio.start_background_task(_do_ai_move, user_id, sid)

    def _do_ai_move(user_id, sid):
        game = sessions.get(user_id)
        if not game or game.check_winner():
            return

        # Process AI move
        ai_move = game.process_ai_move()

        response = {
            'state': game.get_state(),
            'ai_move': ai_move
        }

        # Check if the AI has won
        if game.check_winner():
            response['winner'] = 'ai'

        socketio.emit('update', response, room=sid)

    @socketio.on('new_game', namespace='/tank2')
    def new_game(data):
        user_id = data['user_id']
        game = sessions.get(user_id)
        game.new_game()
        response = {
            'state': game.get_state()
        }
        emit('update', response)