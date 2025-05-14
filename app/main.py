from flask import Blueprint, render_template
from flask_login import login_required, current_user
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def home():
    return render_template('index.html')

@main_bp.route('/games')
def games():
    return render_template('games.html')

@main_bp.route('/about')
def about():
    return render_template('about.html')

@main_bp.route('/gomoku')
# @login_required
def gomoku():
    # 查询当前用户的 AI 列表
    conn = pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT id, bot_name FROM bots ")
    bots = cursor.fetchall()
    conn.close()

    # 将 AI 列表传递到模板
    return render_template('gomoku.html', bots=bots)

@main_bp.route('/tank')
def tank():
    return render_template('tank.html')

@main_bp.route('/catking')
def catking():
    return render_template('catking.html')