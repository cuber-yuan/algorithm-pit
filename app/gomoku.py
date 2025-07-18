from flask import Blueprint, request
from . import socketio
from judges.gomoku_judge import GomokuJudge
from uuid import uuid4
from flask_socketio import emit, join_room
import sys
import json
import io
from unittest.mock import patch
import contextlib
import subprocess
import tempfile
import os
from .code_executor import CodeExecutor
import uuid
import pymysql
from dotenv import load_dotenv

load_dotenv()

gomoku_bp = Blueprint('gomoku', __name__)

sessions = {} # sessions 结构将变为 { user_id: { 'active_game_id': '...', game_id_1: game_obj_1, game_id_2: game_obj_2 } }

# --- 辅助函数 ---
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
            cursor.execute("SELECT source_code, file_path, language FROM bots WHERE id = %s", (bot_id,))
            result = cursor.fetchone()
        if result:
            return CodeExecutor(code=result['source_code'], language=result['language'], path=result['file_path'])
    finally:
        if conn:
            conn.close()
    return None

def _trigger_next_turn(game, sid):
    """核心函数：根据当前玩家类型决定下一步操作"""
    # 在开始时检查终止状态
    if game.winner != 0 or game.is_terminated:
        return

    current_player_type = game.black_player_type if game.current_player == 1 else game.white_player_type
    
    if current_player_type == 'human':
        return

    if current_player_type == 'bot':
        executor = game.black_executor if game.current_player == 1 else game.white_executor
        if not executor:
            return

        socketio.sleep(0.5)

        # 在耗时操作后再次检查终止状态
        if game.is_terminated:
            return

        input_str = game.send_action_to_ai()
        output = executor.run(input_str)
        
        # 在IO操作后再次检查
        if game.is_terminated:
            return

        try:
            move_data = json.loads(output)
            ai_x, ai_y = move_data['x'], move_data['y']
        except (json.JSONDecodeError, KeyError):
            print(f"AI for player {game.current_player} returned invalid data: {output}.")
            # 可以设置一个默认的惩罚机制，比如判负
            game.winner = 3 - game.current_player
            emit('update', {'board': game.board, 'winner': game.winner, 'error_msg': 'AI returned invalid move.'}, room=sid)
            return

        if not game.apply_move(ai_x, ai_y):
            # AI走了一步无效棋
            game.winner = 3 - game.current_player
            emit('update', {'board': game.board, 'winner': game.winner, 'error_msg': 'AI made an invalid move.'}, room=sid)
            return

        winner = game.check_win(ai_x, ai_y)
        if winner != 0:
            game.winner = winner

        response = {
            'board': game.board,
            'ai_move': {'x': ai_x, 'y': ai_y, 'player': 3 - game.current_player},
            'winner': game.winner,
            'game_id': game.game_id
        }
        emit('update', response, room=sid)

        # 递归调用前最后一次检查
        if game.winner == 0 and not game.is_terminated:
            _trigger_next_turn(game, sid)

# --- SocketIO 事件处理器 ---
def register_gomoku_events(socketio):
    @socketio.on('connect', namespace='/gomoku')
    def handle_connect():
        user_id = str(uuid4())
        # 初始化用户的 session 存储
        sessions[user_id] = {'sid': request.sid}
        join_room(request.sid)
        # 不再创建默认的 GomokuJudge 实例
        emit('init', {'user_id': user_id}, room=request.sid)
        print(f'new gomoku user connected: {user_id}')

    @socketio.on('new_game', namespace='/gomoku')
    def new_game(data):
        user_id = data['user_id']
        user_session = sessions.get(user_id)
        if not user_session: return

        # 1. 终止该用户所有正在运行的旧游戏
        for key, value in user_session.items():
            if isinstance(value, GomokuJudge):
                value.terminate()

        # 2. 创建一个全新的游戏实例
        game = GomokuJudge()
        game.game_id = str(uuid.uuid4())
        
        # 3. 将新游戏实例存入用户会话中 (可以先清理旧的)
        # 为了简化，我们只保留sid和新的游戏实例
        sid = user_session['sid']
        sessions[user_id] = {'sid': sid, game.game_id: game}

        # 获取前端选择
        black_is_human = data.get('black_is_human', False)
        white_is_human = data.get('white_is_human', False)
        black_bot_id = data.get('black_bot')
        white_bot_id = data.get('white_bot')

        black_player_type = 'human' if black_is_human else 'bot'
        white_player_type = 'human' if white_is_human else 'bot'

        # 为Bot创建执行器
        black_executor = _get_bot_executor(black_bot_id) if not black_is_human else None
        white_executor = _get_bot_executor(white_bot_id) if not white_is_human else None

        # 初始化游戏
        game.new_game(
            black_player_type=black_player_type,
            white_player_type=white_player_type,
            black_executor=black_executor,
            white_executor=white_executor
        )

        # 4. 发送一个明确的 `game_started` 事件
        emit('game_started', {'board': game.board, 'game_id': game.game_id}, room=sid)

        # 5. 开始新游戏的游戏循环
        _trigger_next_turn(game, sid)

    @socketio.on('player_move', namespace='/gomoku')
    def handle_player_move(data):
        user_id = data.get('user_id')
        game_id = data.get('game_id') # 获取前端传来的 game_id
        user_session = sessions.get(user_id)

        # 验证 game_id 是否存在
        if not user_id or not game_id or not user_session:
            return

        # 3. 使用 game_id 精确查找游戏实例
        game = user_session.get(game_id)
        
        # 核心验证：确保游戏存在，且未结束
        if not game or game.winner != 0:
            return
        
        sid = user_session['sid']

        is_black_human_turn = game.current_player == 1 and game.black_player_type == 'human'
        is_white_human_turn = game.current_player == 2 and game.white_player_type == 'human'

        if not (is_black_human_turn or is_white_human_turn):
            return # 不是当前人类玩家的回合

        x, y = data['x'], data['y']
        if not game.apply_move(x, y):
            return

        winner = game.check_win(x, y)
        if winner != 0:
            game.winner = winner

        response = {
            'board': game.board,
            'move': {'x': x, 'y': y, 'player': 3 - game.current_player},
            'winner': game.winner,
            'game_id': game.game_id # 每次更新都带上 game_id
        }
        emit('update', response, room=sid)

        if game.winner == 0:
            _trigger_next_turn(game, sid)

    @socketio.on('disconnect', namespace='/gomoku')
    def handle_disconnect():
        user_id_to_del = None
        for user_id, session_data in sessions.items():
            if session_data.get('sid') == request.sid:
                # 清理该用户的所有游戏实例
                for key, value in list(session_data.items()):
                    if isinstance(value, GomokuJudge):
                        if value.black_executor: value.black_executor.cleanup()
                        if value.white_executor: value.white_executor.cleanup()
                user_id_to_del = user_id
                break
        
        if user_id_to_del:
            del sessions[user_id_to_del]
            print(f'User {user_id_to_del} disconnected and all sessions cleaned up')