from flask import Blueprint, render_template

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
def gomoku():
    return render_template('gomoku.html')

@main_bp.route('/tank')
def tank():
    return render_template('tank.html')