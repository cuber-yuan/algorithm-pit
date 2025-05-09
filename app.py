from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/games')
def games():
    return render_template('games.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route("/gomoku")
def gomoku():
    return render_template("gomoku.html")

@app.route("/tank")
def tank():
    return render_template("tank.html")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)