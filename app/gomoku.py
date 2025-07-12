from flask import Blueprint, request
from . import socketio
from .gomoku_judge import GomokuJudge
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

sessions = {}

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
            cursor.execute("SELECT source_code FROM bots WHERE id = %s", (bot_id,))
            result = cursor.fetchone()
        if result:
            return CodeExecutor(code=result['source_code'])
    finally:
        if conn:
            conn.close()
    return None

def _trigger_next_turn(game, sid):
    """核心函数：根据当前玩家类型决定下一步操作"""
    if game.winner != 0:
        return

    current_player_type = game.black_player_type if game.current_player == 1 else game.white_player_type
    
    if current_player_type == 'human':
        # 等待人类玩家操作
        return

    if current_player_type == 'bot':
        executor = game.black_executor if game.current_player == 1 else game.white_executor
        if not executor:
            print(f"Error: Player {game.current_player} is a bot but has no executor.")
            return

        socketio.sleep(0.5) # 增加延迟，改善Bot vs Bot的观感

        input_str = game.send_action_to_ai()
        output = executor.run(input_str)
        
        try:
            move_data = json.loads(output)
            ai_x, ai_y = move_data['x'], move_data['y']
        except (json.JSONDecodeError, KeyError) as e:
            print(f"AI for player {game.current_player} returned invalid data: {output}. Error: {e}")
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
            'winner': game.winner
        }
        emit('update', response, room=sid)

        # 游戏继续，触发下一回合
        if game.winner == 0:
            _trigger_next_turn(game, sid)

# --- SocketIO 事件处理器 ---
def register_gomoku_events(socketio):
    @socketio.on('connect', namespace='/gomoku')
    def handle_connect():
        user_id = str(uuid4())
        sessions[user_id] = GomokuJudge()
        sessions[user_id].sid = request.sid
        join_room(request.sid)
        emit('init', {'user_id': user_id, 'board': sessions[user_id].board}, room=request.sid)
        print(f'new gomoku user connected: {user_id}')

    @socketio.on('new_game', namespace='/gomoku')
    def new_game(data):
        user_id = data['user_id']
        game = sessions.get(user_id)
        if not game: return

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
        game.game_id = str(uuid.uuid4())

        emit('update', {'board': game.board, 'game_id': game.game_id}, room=game.sid)

        # 开始游戏循环
        _trigger_next_turn(game, game.sid)

    @socketio.on('player_move', namespace='/gomoku')
    def handle_player_move(data):
        user_id = data['user_id']
        game = sessions.get(user_id)
        sid = request.sid

        # 验证
        if not game or game.game_id != data.get('game_id') or game.winner != 0:
            return

        is_black_human_turn = game.current_player == 1 and game.black_player_type == 'human'
        is_white_human_turn = game.current_player == 2 and game.white_player_type == 'human'

        if not (is_black_human_turn or is_white_human_turn):
            return # 不是当前人类玩家的回合

        x, y = data['x'], data['y']
        if not game.apply_move(x, y):
            # 无效落子，可以给前端发一个错误提示，但暂时忽略
            return

        winner = game.check_win(x, y)
        if winner != 0:
            game.winner = winner

        response = {
            'board': game.board,
            'move': {'x': x, 'y': y, 'player': 3 - game.current_player},
            'winner': game.winner
        }
        emit('update', response, room=sid)

        # 移交控制权给下一回合
        if game.winner == 0:
            _trigger_next_turn(game, sid)

    @socketio.on('disconnect', namespace='/gomoku')
    def handle_disconnect():
        # ... (保持不变) ...
        for user_id, game in list(sessions.items()):
            if hasattr(game, 'sid') and game.sid == request.sid:
                # 可以在这里清理执行器等资源
                if game.black_executor: game.black_executor.cleanup()
                if game.white_executor: game.white_executor.cleanup()
                del sessions[user_id]
                print(f'User {user_id} disconnected and session cleaned up')
                break