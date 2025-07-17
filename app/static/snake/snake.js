// This script is loaded by tank.html after the Phaser game object is created.
// The 'mainScene' variable is globally available and points to the main Phaser scene.

let bgmAudio = new Audio('/static/snake/assets/snake.m4a');
bgmAudio.loop = true;
bgmAudio.volume = 1;
let moveAudio = new Audio('/static/snake/assets/move.mp3');
moveAudio.volume = 0.2;
let explosionAudio = new Audio('/static/snake/assets/explosion.mp3');
explosionAudio.volume = 0.3;
let gameoverAudio = new Audio('/static/snake/assets/gameover.m4a');
gameoverAudio.volume = 1;

// --- Extend the main Phaser scene with our game logic ---
class SnakeScene extends Phaser.Scene {
    constructor() {
        super({ key: 'SnakeScene' });

        this.fieldWidth = 0;
        this.fieldHeight = 0;
        this.snake1 = []; // 玩家1的蛇，格式: [{x, y, dir}]
        this.snake2 = []; // 玩家2的蛇，格式: [{x, y, dir}]
        this.obstacles = [];

        this.CELL_SIZE = 0;
        this.obstacleLayer = null;
        this.snake1Layer = null;
        this.snake2Layer = null;
        this.turn = 0; 
    }

    preload() {
        const assetPath = '/static/snake/assets/';
        const colors = ['red', 'blue'];

        colors.forEach(color => {
            this.load.image(`head_${color}_nodir`, `${assetPath}head_${color}_nodir.png`);
            this.load.image(`head_${color}_dir0`, `${assetPath}head_${color}_dir0.png`);
            this.load.image(`tail_${color}_dir0`, `${assetPath}tail_${color}_dir0.png`);
            this.load.image(`body_${color}_dir0`, `${assetPath}body_${color}_dir0.png`);
            this.load.image(`body_${color}_dir01`, `${assetPath}body_${color}_dir01.png`);
        });
        this.load.image('stone', `${assetPath}stone.png`);
    }

    create() {
        this.obstacleLayer = this.add.group();
        this.snake1Layer = this.add.group();
        this.snake2Layer = this.add.group();
    }

    updateFromState(state) {
        if (!state) return;

        if (state.width && state.height) {
            this.drawInitialState(state);
        } else {
            this.applyActions(state);
        }

        const turnCounter = document.getElementById('turnCounter');
        if (turnCounter) {
            turnCounter.textContent = `Turn: ${this.turn}`;
        }
    }

    drawInitialState(state) {
        this.fieldWidth = state.width;
        this.fieldHeight = state.height;
        this.obstacles = state.obstacle;
        this.turn = 0;

        this.snake1 = [{ x: state['0'].x, y: state['0'].y, dir: -1 }];
        this.snake2 = [{ x: state['1'].x, y: state['1'].y, dir: -1 }];

        resizeCanvas();
    }

    applyActions(actions) {
        this.turn += 1; // 回合数增加

        // 方向向量 (0:左, 1:下, 2:右, 3:上)
        const directions = [
            { x: -1, y: 0 }, // 0:左
            { x: 0, y: 1 },  // 1:下
            { x: 1, y: 0 },  // 2:右
            { x: 0, y: -1 }  // 3:上
        ];

        const head1 = this.snake1[0];
        const newHead1 = {
            x: head1.x + directions[actions['0']].x,
            y: head1.y + directions[actions['0']].y,
            dir: actions['0']
        };
        this.snake1.unshift(newHead1);

        const head2 = this.snake2[0];
        const newHead2 = {
            x: head2.x + directions[actions['1']].x,
            y: head2.y + directions[actions['1']].y,
            dir: actions['1']
        };
        this.snake2.unshift(newHead2);

        let shouldGrow = false;
        if (this.turn <= 25) {
            shouldGrow = true;
        } else if ((this.turn - 25) % 3 === 0) { // 28, 31, 34...
            shouldGrow = true;
        }

        if (!shouldGrow) {
            this.snake1.pop();
            this.snake2.pop();
        }
        this.renderAll();
    }

    renderAll() {
        this.obstacleLayer.clear(true, true);
        this.snake1Layer.clear(true, true);
        this.snake2Layer.clear(true, true);

        // 使用图片渲染障碍物
        this.obstacles.forEach(obs => {
            // 渲染时将1-based坐标转换为0-based
            const x = (obs.x - 1 + 0.5) * this.CELL_SIZE;
            const y = (obs.y - 1 + 0.5) * this.CELL_SIZE;
            const sprite = this.add.sprite(x, y, 'stone');
            sprite.setDisplaySize(this.CELL_SIZE, this.CELL_SIZE);
            this.obstacleLayer.add(sprite);
        });

        // 渲染两条蛇
        this.renderSnake(this.snake1, 'blue', this.snake1Layer);
        this.renderSnake(this.snake2, 'red', this.snake2Layer);
    }

    renderSnake(snake, color, layer) {
        const dirToAngle = [0, 270, 180, 90]; // (0:左, 1:下, 2:右, 3:上)

        for (let i = 0; i < snake.length; i++) {
            const segment = snake[i];
            const x = (segment.x - 1 + 0.5) * this.CELL_SIZE;
            const y = (segment.y - 1 + 0.5) * this.CELL_SIZE;
            let spriteKey = '';
            let angle = 0;

            if (i === 0) { // 蛇头
                spriteKey = segment.dir === -1 ? `head_${color}_nodir` : `head_${color}_dir0`;
                if (segment.dir !== -1) angle = dirToAngle[segment.dir];
            } else if (i === snake.length - 1 && snake.length > 1) { // 蛇尾
                // 蛇尾方向应与倒数第二节指向蛇尾的方向一致
                const prevSegment = snake[i - 1];
                spriteKey = `tail_${color}_dir0`;
                angle = dirToAngle[prevSegment.dir];
            } else {
                const prevSegment = snake[i - 1];
                if (prevSegment.dir === segment.dir || (prevSegment.dir + 2) % 4 === segment.dir) { // 直线
                    spriteKey = `body_${color}_dir0`;
                    angle = dirToAngle[segment.dir];
                } else { // 转弯
                    const inDir = (segment.dir + 2) % 4;
                    const outDir = prevSegment.dir;
                    spriteKey = `body_${color}_dir01`;

                    if ((inDir + 1) % 4 === outDir) {
                        angle = dirToAngle[inDir];
                    } else if ((inDir + 3) % 4 === outDir) {
                        angle = dirToAngle[outDir];
                    }

                    const sprite = this.add.sprite(x, y, spriteKey);
                    sprite.setDisplaySize(this.CELL_SIZE, this.CELL_SIZE);
                    sprite.setAngle(angle);
                    layer.add(sprite);
                    continue;
                }
            }

            if (spriteKey) {
                const sprite = this.add.sprite(x, y, spriteKey);
                sprite.setDisplaySize(this.CELL_SIZE, this.CELL_SIZE);
                sprite.setAngle(angle);
                layer.add(sprite);
            }
        }
    }
}

// --- Game Configuration & State ---
let userId = null;
let currentGameId = null;
let gameOver = false;
const socket = io('/snake');

function getCanvasSize() {
    const padding = window.innerWidth < 600 ? 24 : 70;
    return Math.min(window.innerWidth - padding, 600); // Simplified calculation
}

let CANVAS_SIZE = getCanvasSize();
let phaserGame; // Will be initialized in the Phaser config


let maskRect = null;
let maskText = null;

function showPhaserMask(msg = "Waiting for new game...") {
    const scene = phaserGame.scene.getScene('SnakeScene');
    if (!scene) return;
    hidePhaserMask();

    const width = scene.scale.width;
    const height = scene.scale.height;

    maskRect = scene.add.rectangle(width / 2, height / 2, width, height, 0x000000, 0.35).setDepth(1000);
    maskText = scene.add.text(width / 2, height / 2, msg, {
        fontSize: Math.floor(Math.min(width, height) / 18) + 'px',
        color: '#fff',
        fontStyle: 'bold'
    }).setOrigin(0.5).setDepth(1001);
}

function hidePhaserMask() {
    if (maskRect) { maskRect.destroy(); maskRect = null; }
    if (maskText) { maskText.destroy(); maskText = null; }
}

// --- Game Logic & Server Communication ---
socket.on('init', (data) => { userId = data.user_id; });


socket.on('game_started', (data) => {
    currentGameId = data.game_id;
    gameOver = false;
    hidePhaserMask();
    const scene = phaserGame.scene.getScene('SnakeScene');
    if (scene && typeof scene.updateFromState === 'function') {
        scene.updateFromState(data.state);
        bgmAudio.currentTime = 0;
        bgmAudio.play();
    } else {
        console.error("SnakeScene or its updateFromState method is not available!");
    }
});

socket.on('update', (data) => {
    if (!currentGameId || data.game_id !== currentGameId) {
        console.log(`Ignoring update for irrelevant game: ${data.game_id}`);
        return;
    }

    const scene = phaserGame.scene.getScene('SnakeScene');
    if (scene && typeof scene.updateFromState === 'function') {
        scene.updateFromState(data.state);
    }
    moveAudio.play();
});



socket.on('finish', (data) => {
    if (!currentGameId || data.game_id !== currentGameId) {
        console.log(`Ignoring finish for irrelevant game: ${data.game_id}`);
        return;
    }

    if (bgmAudio) {
        bgmAudio.pause();
        bgmAudio.currentTime = 0;
    }

    explosionAudio.play();
    gameoverAudio.play();

    let winner = data.winner;
    if (winner == 0) {
        showPhaserMask('Blue wins!');
    } else if (winner == 1) {
        showPhaserMask('Red wins!');
    } else {
        showPhaserMask('Draw!');
    }
    gameOver = true;
});

function newGame() {
    if (!userId) {
        alert("Not connected to server yet.");
        return;
    }

    const leftPlayerId = document.getElementById('aiSelectLeft').value;
    const rightPlayerId = document.getElementById('aiSelectRight').value;

    socket.emit('new_game', {
        user_id: userId,
        left_player_id: leftPlayerId,
        right_player_id: rightPlayerId,
        left_is_human: document.getElementById('left-is-human').checked,
        right_is_human: document.getElementById('right-is-human').checked
    });
}

function resizeCanvas() {
    const scene = phaserGame.scene.getScene('SnakeScene');
    const maxScreenWidth = Math.min(window.innerWidth - 60, 900); // 60px边距，最大900
    const cellSize = Math.floor(maxScreenWidth / scene.fieldWidth);
    const canvasWidth = cellSize * scene.fieldWidth;
    const canvasHeight = cellSize * scene.fieldHeight;

    const container = document.getElementById('phaser-container');
    container.style.width = canvasWidth + 'px';
    container.style.height = canvasHeight + 'px';

    scene.scale.resize(canvasWidth, canvasHeight);

    scene.CELL_SIZE = cellSize;

    scene.renderAll();
}

// --- Event Listeners & Phaser Initialization ---
window.addEventListener('resize', () => {
    resizeCanvas();
});

document.addEventListener('DOMContentLoaded', () => {
    // Attach event listener for the new game button
    document.getElementById('newGameBtn').addEventListener('click', () => {
        newGame();
    });

    // 只允许两个checkbox最多勾选一个
    const leftCheckbox = document.getElementById('left-is-human');
    const rightCheckbox = document.getElementById('right-is-human');
    const leftSelect = document.getElementById('aiSelectLeft');
    const rightSelect = document.getElementById('aiSelectRight');

    leftCheckbox.addEventListener('change', () => {
        if (leftCheckbox.checked) {
            rightCheckbox.checked = false;
            rightSelect.disabled = false;
            rightSelect.classList.remove('bg-gray-200', 'cursor-not-allowed');
        }
        leftSelect.disabled = leftCheckbox.checked;
        leftSelect.classList.toggle('bg-gray-200', leftCheckbox.checked);
        leftSelect.classList.toggle('cursor-not-allowed', leftCheckbox.checked);
    });

    rightCheckbox.addEventListener('change', () => {
        if (rightCheckbox.checked) {
            leftCheckbox.checked = false;
            leftSelect.disabled = false;
            leftSelect.classList.remove('bg-gray-200', 'cursor-not-allowed');
        }
        rightSelect.disabled = rightCheckbox.checked;
        rightSelect.classList.toggle('bg-gray-200', rightCheckbox.checked);
        rightSelect.classList.toggle('cursor-not-allowed', rightCheckbox.checked);
    });

    // 方向按钮点击事件
    document.getElementById('arrow-left').onclick = function () {
        sendHumanDirection(0); // 左
    };
    document.getElementById('arrow-down').onclick = function () {
        sendHumanDirection(1); // 下
    };
    document.getElementById('arrow-right').onclick = function () {
        sendHumanDirection(2); // 右
    };
    document.getElementById('arrow-up').onclick = function () {
        sendHumanDirection(3); // 上
    };

    // --- PHASER INITIALIZATION ---
    const config = {
        type: Phaser.AUTO,
        width: CANVAS_SIZE,
        height: CANVAS_SIZE,
        parent: 'phaser-container',

        scene: [SnakeScene]
    };
    phaserGame = new Phaser.Game(config);


});

document.addEventListener('keydown', (e) => {
    let dir = null;
    if (e.key === 'a' || e.key === 'A') dir = 0;      // 左
    else if (e.key === 's' || e.key === 'S') dir = 1; // 下
    else if (e.key === 'd' || e.key === 'D') dir = 2; // 右
    else if (e.key === 'w' || e.key === 'W') dir = 3; // 上
    if (dir !== null) {
        humanDirection = dir;
        socket.emit('player_move',
            {
                user_id: userId,
                game_id: currentGameId,
                move: JSON.stringify({ response: { direction: dir } })
            });
    }
});

// 发送人类玩家方向
function sendHumanDirection(dir) {
    humanDirection = dir;
    socket.emit('player_move', {
        user_id: userId,
        game_id: currentGameId,
        move: JSON.stringify({ response: { direction: dir } })
    });
}

