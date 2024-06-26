from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_pymongo import PyMongo
import random
import time

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config["MONGO_URI"] = "mongodb://mongo:27017/minesweeper"
mongo = PyMongo(app)

# Game settings
ROWS = 8
COLS = 8
MINES = 10


def create_board(rows, cols, mines):
    board = [['' for _ in range(cols)] for _ in range(rows)]
    mines_locations = set()
    while len(mines_locations) < mines:
        location = (random.randint(0, rows - 1), random.randint(0, cols - 1))
        if location not in mines_locations:
            mines_locations.add(location)
            board[location[0]][location[1]] = 'M'
    for r in range(rows):
        for c in range(cols):
            if board[r][c] == 'M':
                continue
            count = sum(
                (board[r + dr][c + dc] == 'M')
                for dr in (-1, 0, 1) if 0 <= r + dr < rows
                for dc in (-1, 0, 1) if 0 <= c + dc < cols
            )
            board[r][c] = str(count) if count > 0 else ''
    return board


def save_game_state():
    game_state = {
        "board": session['board'],
        "revealed": session['revealed'],
        "flags": session['flags'],
        "start_time": session['start_time'],
        "game_over": session['game_over']
    }
    mongo.db.games.insert_one(game_state)


def load_game_state():
    game_state = mongo.db.games.find_one(sort=[('_id', -1)])
    if game_state:
        session['board'] = game_state['board']
        session['revealed'] = game_state['revealed']
        session['flags'] = game_state['flags']
        session['start_time'] = game_state['start_time']
        session['game_over'] = game_state['game_over']


def calculate_score(start_time, end_time, revealed, flags, board):
    time_taken = end_time - start_time
    revealed_count = sum(sum(row) for row in revealed)
    correct_flags = sum(1 for r in range(ROWS) for c in range(COLS) if flags[r][c] and board[r][c] == 'M')

    time_score = max(0, 1000 - int(time_taken))
    cell_score = revealed_count * 10
    flag_score = correct_flags * 50

    total_score = time_score + cell_score + flag_score
    return total_score


@app.route('/')
def main_menu():
    scores = list(mongo.db.scores.find().sort('score', -1).limit(10))
    return render_template('main_menu.html', scores=scores)


@app.route('/start_game', methods=['POST'])
def start_game():
    session['player_name'] = request.form['player_name']
    return redirect(url_for('index'))


@app.route('/index')
def index():
    session['board'] = create_board(ROWS, COLS, MINES)
    session['revealed'] = [[False for _ in range(COLS)] for _ in range(ROWS)]
    session['flags'] = [[False for _ in range(COLS)] for _ in range(ROWS)]
    session['start_time'] = time.time()
    session['game_over'] = False
    start_time = int(session['start_time'] * 1000)
    save_game_state()
    return render_template('game.html', start_time=start_time, game_over=session['game_over'],
                           board=session['board'], revealed=session['revealed'], flags=session['flags'])


@app.route('/game', methods=['POST'])
def game():
    if session['game_over']:
        return redirect(url_for('index'))

    cell = request.form['cell']
    row, col = map(int, cell.split('-'))
    board = session['board']
    revealed = session['revealed']
    flags = session['flags']

    for r in range(ROWS):
        for c in range(COLS):
            flag_value = request.form.get(f'flag-{r}-{c}')
            flags[r][c] = flag_value == '1'

    if not flags[row][col]:
        if board[row][col] == 'M':
            session['game_over'] = True
            revealed[row][col] = True
            end_time = time.time()
            score = calculate_score(session['start_time'], end_time, revealed, flags, board)
            mongo.db.scores.insert_one({
                'player_name': session['player_name'],
                'score': score,
                'clicks': sum(sum(row) for row in revealed) + sum(sum(row) for row in flags)
            })
            flash(f'Game Over! Your score is {score}')
            return redirect(url_for('game_over'))
        else:
            reveal_cell(row, col, board, revealed)

    session['revealed'] = revealed
    session['flags'] = flags
    start_time = int(session['start_time'] * 1000)
    save_game_state()
    return render_template('game.html', board=board, revealed=revealed, flags=flags, game_over=session['game_over'],
                           start_time=start_time)


def reveal_cell(row, col, board, revealed):
    if revealed[row][col]:
        return
    revealed[row][col] = True
    if board[row][col] == '':
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if 0 <= row + dr < ROWS and 0 <= col + dc < COLS:
                    reveal_cell(row + dr, col + dc, board, revealed)


@app.route('/game_over')
def game_over():
    scores = list(mongo.db.scores.find().sort('score', -1).limit(10))
    return render_template('main_menu.html', scores=scores, game_over=True)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
