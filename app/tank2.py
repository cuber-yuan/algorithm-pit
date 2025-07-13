from flask import Blueprint, request
from . import socketio
from .tank2_judge import TankBotInterface # Assuming this is your game logic class
from .code_executor import CodeExecutor
from uuid import uuid4
import uuid
import json
from flask_socketio import emit, join_room
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

tank_bp = Blueprint('tank', __name__)

sessions = {} # { user_id: { 'sid': '...', game_id: game_obj, ... } }

# --- Helper Functions (from Gomoku) ---
def _get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def _get_bot_executor(bot_id):
    if not bot_id:
        return None
    try:
        conn = _get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT source_code FROM bots WHERE id = %s", (bot_id,))
            result = cursor.fetchone()
        if result:
            return CodeExecutor(code=result['source_code'])
    finally:
        if conn:
            conn.close()
    return None

# --- Core Game Loop for Simultaneous Moves ---
def _process_turn_if_ready(game, sid):
    """
    Checks if all moves for the current turn are collected. 
    If so, processes the turn and starts the next one.
    """
    if game.is_terminated or game.winner or not game.are_all_moves_collected():
        return

    # 1. All moves are in, process the turn
    game.process_turn() # This method resolves all collected moves

    # 2. Check for a winner after processing
    winner = game.check_winner() # This method should now return the winner if any

    # 3. Send the result of the turn to the client
    response = {
        'state': game.get_state(),
        'winner': winner,
        'game_id': game.game_id
    }
    emit('update', response, room=sid)

    # 4. If the game is not over, start the next turn
    if not winner and not game.is_terminated:
        socketio.sleep(1.0) # Pause for 1 second between turns for better UX
        _start_new_turn(game, sid)

def _start_new_turn(game, sid):
    """
    Starts a new turn by clearing old moves and running any bots.
    """
    if game.is_terminated or game.winner:
        return
    
    game.start_new_turn() # This method should prepare the game for the next set of moves

    # Automatically run bots
    if game.top_player_type == 'bot':
        input_str = game.get_bot_input('top')
        print(f"Running bot for top player with input: {input_str}")
        
        # --- 修改后的调试代码 ---
        code_str = game.top_executor.code
        lines = code_str.splitlines()
        line_count = len(lines)
        
        print("--- Verifying Bot Code (Top Player) ---")
        print(f"Total lines: {line_count}")
        print("First 5 lines:")
        print('\n'.join(lines[:5]))
        print("Last 5 lines:")
        print('\n'.join(lines[-5:]))
        print("------------------------------------")
        # --- 调试代码结束 ---

        output = game.top_executor.run(input_str)
        game.collect_move('top', json.loads(output))

    if game.bottom_player_type == 'bot':
        input_str = game.get_bot_input('bottom')
        print(f"Running bot for bottom player with input: {input_str}")

        # --- 修改后的调试代码 ---
        code_str = game.bottom_executor.code
        lines = code_str.splitlines()
        line_count = len(lines)

        print("--- Verifying Bot Code (Bottom Player) ---")
        print(f"Total lines: {line_count}")
        print("First 5 lines:")
        print('\n'.join(lines[:5]))
        print("Last 5 lines:")
        print('\n'.join(lines[-5:]))
        print("------------------------------------")
        # --- 调试代码结束 ---

        output = game.bottom_executor.run(input_str)
        game.collect_move('bottom', json.loads(output))
    
    # After running bots, check if the turn is ready to be processed
    # (This handles the bot vs. bot case automatically)
    _process_turn_if_ready(game, sid)

# --- SocketIO Event Handlers ---
def register_tank_events(socketio):
    @socketio.on('connect', namespace='/tank2')
    def handle_connect():
        user_id = str(uuid4())
        sessions[user_id] = {'sid': request.sid}
        join_room(request.sid)
        emit('init', {'user_id': user_id})
        print(f'New tank user connected: {user_id}')

    @socketio.on('new_game', namespace='/tank2')
    def new_game(data):
        user_id = data['user_id']
        user_session = sessions.get(user_id)
        if not user_session: return

        # Terminate any old games for this user
        for key, value in user_session.items():
            if isinstance(value, TankBotInterface):
                value.terminate()

        # Create and configure the new game instance
        game = TankBotInterface() # Or your main game class
        game.game_id = str(uuid.uuid4())
        
        sid = user_session['sid']
        sessions[user_id] = {'sid': sid, game.game_id: game}

        # Get player selections from the frontend.
        # Assumes frontend sends 'top_player_id' and 'bottom_player_id'
        # where the value is 'human' or a bot ID string.
        top_player_id = data.get('top_player_id', 'human')
        bottom_player_id = data.get('bottom_player_id')

        top_player_type = 'human' if top_player_id == 'human' else 'bot'
        bottom_player_type = 'human' if bottom_player_id == 'human' else 'bot'

        top_executor = _get_bot_executor(top_player_id) if top_player_type == 'bot' else None
        bottom_executor = _get_bot_executor(bottom_player_id) if bottom_player_type == 'bot' else None
        
        game.configure_players(
            top_player_type=top_player_type,
            bottom_player_type=bottom_player_type,
            top_executor=top_executor,
            bottom_executor=bottom_executor
        )

        # Send a specific "game_started" event
        emit('game_started', {
            'state': game.get_state(),
            'game_id': game.game_id
        }, room=sid)

        # Start the first turn
        _start_new_turn(game, sid)

    @socketio.on('player_move', namespace='/tank2')
    def handle_player_move(data):
        user_id = data.get('user_id')
        game_id = data.get('game_id')
        move = data.get('move')
        user_session = sessions.get(user_id)

        if not user_id or not game_id or not user_session: return
        
        game = user_session.get(game_id)
        if not game or game.is_terminated or game.winner: return

        # Collect the human player's move (assuming human is always 'top' player)
        game.collect_move('top', move)

        # Check if the turn is now ready to be processed
        _process_turn_if_ready(game, user_session['sid'])

    @socketio.on('disconnect', namespace='/tank2')
    def handle_disconnect():
        user_id_to_del = None
        for user_id, session_data in sessions.items():
            if session_data.get('sid') == request.sid:
                for key, value in list(session_data.items()):
                    if isinstance(value, TankBotInterface):
                        value.terminate()
                user_id_to_del = user_id
                break
        
        if user_id_to_del:
            del sessions[user_id_to_del]
            print(f'User {user_id_to_del} disconnected and all tank sessions cleaned up')