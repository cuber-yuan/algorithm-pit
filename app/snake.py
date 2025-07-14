import json
import os
import pymysql
import time
from uuid import uuid4

from flask import Blueprint, request
from flask_socketio import emit, join_room

from .code_executor import CodeExecutor
from .cpp_judge_executor import CppJudgeExecutor

snake_bp = Blueprint('snake', __name__)
sessions = {}  # { user_id: { 'sid': ..., 'game': ... } }

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
            cursor.execute("SELECT source_code, language FROM bots WHERE id = %s", (bot_id,))
            result = cursor.fetchone()
        if result:
            return CodeExecutor(code=result['source_code'], language=result['language'])
    finally:
        if conn:
            conn.close()
    return None

class SnakeGameSession:
    def __init__(self, cpp_path, bot_1_code=None, bot_2_code=None):
        self.game_id = str(uuid4())
        self.cpp_judge = CppJudgeExecutor(cpp_path)
        self.bot_1 = CodeExecutor(code=bot_1_code) if bot_1_code else None
        self.bot_2 = CodeExecutor(code=bot_2_code) if bot_2_code else None
        self.bot_1_type = 'bot' if bot_1_code else 'human'
        self.bot_2_type = 'bot' if bot_2_code else 'human'

    def terminate(self):
        if self.bot_1: self.bot_1.cleanup()
        if self.bot_2: self.bot_2.cleanup()


def register_snake_events(socketio):
    @socketio.on('connect', namespace='/snake')
    def handle_connect():
        user_id = str(uuid4())
        sessions[user_id] = {'sid': request.sid}
        join_room(request.sid)
        emit('init', {'user_id': user_id})
        
    @socketio.on('new_game', namespace='/snake')
    def new_game(data):
        print("New game request received:", data)
        user_id = data['user_id']
        bot_1_code = data.get('bot_1_code')
        bot_2_code = data.get('bot_2_code')
        cpp_path = os.path.join(os.path.dirname(__file__), 'snake_judge.exe')
        game = SnakeGameSession(cpp_path, bot_1_code, bot_2_code)
        sessions[user_id] = {'sid': request.sid, 'game': game}

        # Get player selections from the frontend.
        player_1_id = data.get('left_player_id')
        player_2_id = data.get('right_player_id')

        player_1_type = 'human' if player_1_id == 'human' else 'bot'
        player_2_type = 'human' if player_2_id == 'human' else 'bot'

        executor_1 = _get_bot_executor(player_1_id) if player_1_type == 'bot' else None
        executor_2 = _get_bot_executor(player_2_id) if player_2_type == 'bot' else None

        game_state_dict = game.cpp_judge.run_raw_json({});
        print(game_state_dict);
        maxTurn = 100
        judge_input_dict = {'log':[], 'initdata': game_state_dict['initdata']}

        input_dict_1 = { "requests": [game_state_dict['content']['0']], "responses": [] }
        input_dict_2 = { "requests": [game_state_dict['content']['1']], "responses": [] }

        user_session = sessions.get(user_id)
        sid = user_session['sid']
        emit('game_started', {
            'state': game_state_dict['display'],
            'game_id': game.game_id
        }, room=sid)

        for turn in range(maxTurn):
            # time.sleep(1)
            print('this send to frontend', game_state_dict['display'])
            input_str_1 = json.dumps(input_dict_1)
            input_str_2 = json.dumps(input_dict_2)
            print(f"========== Turn {turn + 1} Input ==========\n {input_str_1}\n {input_str_2}")

            output_1 = executor_1.run(input_str_1)
            output_2 = executor_2.run(input_str_2)
            print(f"========== Turn {turn + 1} Output ==========\n {output_1}\n {output_2}")
            
            # 构造裁判输入
            judge_input_dict['log'].append({}) # 奇数个元素留空
            judge_input_dict['log'].append({"0": json.loads(output_1), "1": json.loads(output_2)})
            game_state_dict = game.cpp_judge.run_raw_json(judge_input_dict)

            response = {
                'state': game_state_dict['display'],
                'game_id': game.game_id
            }
            emit('update', response, room=sid)

            if game_state_dict['command'] == 'finish':
                print("Game finished by judge.")
                break
            input_dict_1['requests'].append(json.loads(output_2)['response'])
            input_dict_1['responses'].append(json.loads(output_1)['response'])
            input_dict_2['requests'].append(json.loads(output_1)['response'])
            input_dict_2['responses'].append(json.loads(output_2)['response'])

            

    @socketio.on('disconnect', namespace='/snake')
    def handle_disconnect():
        user_id_to_del = None
        for user_id, session_data in sessions.items():
            if session_data.get('sid') == request.sid:
                game = session_data.get('game')
                if game: game.terminate()
                user_id_to_del = user_id
                break
        if user_id_to_del:
            del sessions[user_id_to_del]