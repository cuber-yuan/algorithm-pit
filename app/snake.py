from flask import Blueprint, request
from . import socketio
from .cpp_judge_executor import CppJudgeExecutor
from .code_executor import CodeExecutor
from flask_socketio import emit, join_room
from uuid import uuid4
import os
import json
import pymysql
import time


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

class snakeGameSession:
    def __init__(self, cpp_path, bot_top_code=None, bot_bottom_code=None):
        self.game_id = str(uuid4())
        self.cpp_judge = CppJudgeExecutor(cpp_path)
        self.bot_top = CodeExecutor(code=bot_top_code) if bot_top_code else None
        self.bot_bottom = CodeExecutor(code=bot_bottom_code) if bot_bottom_code else None
        self.bot_top_type = 'bot' if bot_top_code else 'human'
        self.bot_bottom_type = 'bot' if bot_bottom_code else 'human'
        

    def run_turn(self, judge_input_json):
        """
        judge_input_json: dict, 包含完整历史和地图信息，由前端维护和传递
        1. 若有bot，则为bot生成输入，运行bot，获得动作，填入judge_input_json
        2. 调用cpp裁判，返回裁判输出
        """
        # 1. 运行bot（如果有），生成双方动作
        # 假设 judge_input_json["requests"] 和 "responses" 都是完整历史
        # 只需为当前回合的bot补全动作即可
        # 这里假设前端会把需要bot决策的回合留空或传None
        # 你可以根据实际前端协议调整
        if self.bot_top:
            bot_input = self._make_bot_input(judge_input_json, side='top')
            bot_output = self.bot_top.run(bot_input)
            action = json.loads(bot_output)["response"]
            # 补全responses最后一项
            if len(judge_input_json["responses"]) < len(judge_input_json["requests"]) - 1:
                judge_input_json["responses"].append(action)
            else:
                judge_input_json["responses"][-1] = action
        if self.bot_bottom:
            bot_input = self._make_bot_input(judge_input_json, side='bottom')
            bot_output = self.bot_bottom.run(bot_input)
            action = json.loads(bot_output)["response"]
            # 补全requests最后一项
            if len(judge_input_json["requests"]) < len(judge_input_json["responses"]) + 1:
                judge_input_json["requests"].append(action)
            else:
                judge_input_json["requests"][-1] = action

        # 2. 调用cpp裁判
        judge_output = self.cpp_judge.run_raw_json(judge_input_json)
        return judge_output

    def _make_bot_input(self, judge_input_json, side):
        # 生成bot输入格式，兼容bot协议
        # side: 'top' or 'bottom'
        side_idx = 0 if side == 'top' else 1
        opponent = 'bottom' if side == 'top' else 'top'
        # 取地图
        map_obj = judge_input_json["requests"][0].copy()
        map_obj["mySide"] = side_idx
        # 取历史
        my_history = judge_input_json["responses"]
        opponent_history = judge_input_json["requests"][1:]
        return json.dumps({
            "requests": [map_obj] + opponent_history,
            "responses": my_history
        })

    def terminate(self):
        if self.bot_top: self.bot_top.cleanup()
        if self.bot_bottom: self.bot_bottom.cleanup()

# --- SocketIO事件注册 ---
def register_snake_events(socketio):
    @socketio.on('connect', namespace='/snake')
    def handle_connect():
        user_id = str(uuid4())
        sessions[user_id] = {'sid': request.sid}
        join_room(request.sid)
        emit('init', {'user_id': user_id})

    @socketio.on('new_game', namespace='/snake')
    def new_game(data):
        user_id = data['user_id']
        bot_top_code = data.get('bot_top_code')
        bot_bottom_code = data.get('bot_bottom_code')
        cpp_path = os.path.join(os.path.dirname(__file__), 'snake_judge.exe')
        game = SnakeGameSession(cpp_path, bot_top_code, bot_bottom_code)
        sessions[user_id] = {'sid': request.sid, 'game': game}

        # Get player selections from the frontend.
        # Assumes frontend sends 'top_player_id' and 'bottom_player_id'
        # where the value is 'human' or a bot ID string.
        top_player_id = data.get('top_player_id')
        bottom_player_id = data.get('bottom_player_id')

        top_player_type = 'human' if top_player_id == 'human' else 'bot'
        bottom_player_type = 'human' if bottom_player_id == 'human' else 'bot'

        top_executor = _get_bot_executor(top_player_id) if top_player_type == 'bot' else None
        bot_executor = _get_bot_executor(bottom_player_id) if bottom_player_type == 'bot' else None

        game_state_dict = game.cpp_judge.run_raw_json({});
        print(game_state_dict);
        maxTurn = game_state_dict['initdata']['maxTurn']
        judge_input_dict = {'log':[], 'initdata': game_state_dict['initdata']}

        top_input_dict = { "requests": [game_state_dict['content']['0']], "responses": [] }
        bot_input_dict = { "requests": [game_state_dict['content']['1']], "responses": [] }

        user_session = sessions.get(user_id)
        sid = user_session['sid']
        emit('game_started', {
            'state': game_state_dict['display'],
            'game_id': game.game_id
        }, room=sid)

        for turn in range(maxTurn):
            # time.sleep(1)
            print('this send to frontend', game_state_dict['display'])

            top_input_str = json.dumps(top_input_dict)
            bot_input_str = json.dumps(bot_input_dict)
            print(f"========== Turn {turn + 1} Input ==========\n {top_input_str}\n {bot_input_str}")

            top_output = top_executor.run(top_input_str)
            bot_output = bot_executor.run(bot_input_str)
            print(f"========== Turn {turn + 1} Output ==========\n {top_output}\n {bot_output}")
            
            # 构造裁判输入
            judge_input_dict['log'].append({}) # 奇数个元素留空
            judge_input_dict['log'].append({"0": json.loads(top_output), "1": json.loads(bot_output)})
            game_state_dict = game.cpp_judge.run_raw_json(judge_input_dict)

            response = {
                'state': game_state_dict['display'],
                # 'winner': winner,
                'game_id': game.game_id
            }
            emit('update', response, room=sid)
            # emit('update', game_state_dict['display'], room=sid)

            if game_state_dict['command'] == 'finish':
                print("Game finished by judge.")
                break
            top_input_dict['requests'].append(json.loads(bot_output)['response'])
            top_input_dict['responses'].append(json.loads(top_output)['response'])
            bot_input_dict['requests'].append(json.loads(top_output)['response'])
            bot_input_dict['responses'].append(json.loads(bot_output)['response'])

            
            

    @socketio.on('player_move', namespace='/snake')
    def handle_player_move(data):
        user_id = data.get('user_id')
        judge_input_json = data.get('judge_input_json')  # 前端传来的完整json
        if not user_id or not judge_input_json: return
        game = sessions.get(user_id, {}).get('game')
        if not game: return
        judge_output = game.run_turn(judge_input_json)
        emit('update', judge_output, room=sessions[user_id]['sid'])

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