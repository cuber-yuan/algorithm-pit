from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

upload_bp = Blueprint('upload', __name__)

# 文件上传目录
UPLOAD_FOLDER = 'uploads/bots'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_user_id_by_username(username):
    """通过用户名查询用户ID"""
    conn = pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def save_bot_to_db(user_id, bot_name, description, language, source_code=None, file_path=None, game=None):
    """保存Bot信息到数据库"""
    conn = pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset='utf8mb4'
    )
    print(f"Saving bot for user_id: {user_id}, bot_name: {bot_name}, game: {game}")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO bots (user_id, bot_name, description, language, source_code, file_path, game)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, bot_name, description, language, source_code, file_path, game)
    )
    conn.commit()
    conn.close()

@upload_bp.route('/upload-bot', methods=['POST'])
@login_required
def upload_bot():
    bot_name = request.form.get('botName')
    description = request.form.get('botDescription')
    language = request.form.get('language')
    source_code = request.form.get('sourceCode')
    bot_file = request.files.get('botFile')
    game = request.form.get('game')
    
    # username = request.form.get('username')  # 客户端传递的用户名

    # 验证输入
    if not bot_name or len(bot_name) < 4:
        return jsonify({"message": "Bot name must be at least 4 characters."}), 400
    if not description or len(description) < 4:
        return jsonify({"message": "Bot description must be at least 4 characters."}), 400
    if not source_code and not bot_file:
        return jsonify({"message": "Please upload a file or enter source code."}), 400
    

    # 查询用户ID
    user_id = get_user_id_by_username(current_user.id)
    if not user_id:
        return jsonify({"message": "User not found."}), 404

    # 保存文件或源代码
    file_path = None
    if bot_file:
        # 构建保存路径 bots/用户名/bot名/
        user_dir = os.path.join(UPLOAD_FOLDER, str(current_user.id), bot_name)
        os.makedirs(user_dir, exist_ok=True)
        file_path = os.path.join(user_dir, bot_file.filename)
        bot_file.save(file_path)

    # 保存到数据库
    save_bot_to_db(
        user_id=user_id,
        bot_name=bot_name,
        description=description,
        language=language,
        source_code=source_code if not bot_file else None,
        file_path=file_path,
        game=game,
    )

    return jsonify({"message": "Bot uploaded successfully!"})