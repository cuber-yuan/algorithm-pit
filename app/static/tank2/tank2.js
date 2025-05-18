let map = [];
let playerTanks = [];
let aiTanks = [];
let bullets = [];
let gameOver = false;

const GRID_SIZE = 9;
const CELL_SIZE = 600 / GRID_SIZE;

// Cell types
const CELL_TYPES = {
    EMPTY: 0,
    TANK: 1,
    BASE: 2,
    BRICK: 3,
    STEEL: 4
};

// Cell colors
const CELL_COLORS = {
    [CELL_TYPES.EMPTY]: '#f3f4f6',
    [CELL_TYPES.BRICK]: '#b91c1c',
    [CELL_TYPES.BASE]: '#f59e42',
    [CELL_TYPES.STEEL]: '#6b7280'
};



// Store pending moves for both player tanks
let pendingMoves = [null, null];

// Bullet speed
const BULLET_SPEED = 4;

// Is the game animating?
let animating = false;

// Turn counter
let turn = 1;

// Helper function for random integers
function randomInt(n) {
    return Math.floor(Math.random() * n);
}

// Initialize the map and tanks
function createInitialMap() {
    const layout = [
        ['.', '.', 'T', 'b', 'B', 'b', 'T', '.', '.'],
        ['.', '.', '.', 'b', 'b', 'b', '.', '.', '.'],
        ['.', '.', '.', '.', 'b', '.', '.', '.', '.'],
        ['.', '.', '.', '.', 'b', '.', '.', '.', '.'],
        ['b', 'b', 'S', 'b', 'S', 'b', 'S', 'b', 'b'],
        ['.', '.', '.', '.', 'b', '.', '.', '.', '.'],
        ['.', '.', '.', '.', 'b', '.', '.', '.', '.'],
        ['.', '.', '.', 'b', 'b', 'b', '.', '.', '.'],
        ['.', '.', 'T', 'b', 'B', 'b', 'T', '.', '.']
    ];
    map = [];
    playerTanks = [];
    aiTanks = [];
    bullets = [];
    gameOver = false;
    turn = 1; // Reset turn counter
    updateTurnCounter();
    for (let y = 0; y < GRID_SIZE; y++) {
        let row = [];
        for (let x = 0; x < GRID_SIZE; x++) {
            let c = layout[y][x];
            if (y === Math.floor(GRID_SIZE / 2)) {
                // Add text to the steel blocks in the middle row
                // if (x === 2) row.push({ type: CELL_TYPES.STEEL, text: "Beijing" });
                // else if (x === 4) row.push({ type: CELL_TYPES.STEEL, text: "metro" });
                // else if (x === 6) row.push({ type: CELL_TYPES.STEEL, text: "line 1" });
                if (c === '.') row.push(CELL_TYPES.EMPTY);
                else if (c === 'b') row.push(CELL_TYPES.BRICK);
                else if (c === 'B') row.push(CELL_TYPES.BASE);
                // else if (c === 'S' && x !== 2 && x !== 4 && x !== 6) row.push(CELL_TYPES.STEEL);
                else if (c === 'S') row.push(CELL_TYPES.STEEL);
                else if (c === 'T') {
                    row.push(CELL_TYPES.TANK);
                    if (y >= 8) playerTanks.push({ x, y, color: 0x22d3ee, controlOpen: false });
                    else if (y <= 0) aiTanks.push({ x, y, color: 0xfacc15 });
                }
            } else {
                if (c === '.') row.push(CELL_TYPES.EMPTY);
                else if (c === 'b') row.push(CELL_TYPES.BRICK);
                else if (c === 'B') row.push(CELL_TYPES.BASE);
                else if (c === 'S') row.push(CELL_TYPES.STEEL);
                else if (c === 'T') {
                    row.push(CELL_TYPES.TANK);
                    if (y >= 8) playerTanks.push({ x, y, color: 0x22d3ee, controlOpen: false });
                    else if (y <= 0) aiTanks.push({ x, y, color: 0xfacc15 });
                }
            }
        }
        map.push(row);
    }
}

// Check if a cell is destructible
function isDestructible(cellType) {
    return cellType === CELL_TYPES.BRICK || cellType === CELL_TYPES.BASE || cellType === CELL_TYPES.TANK;
}

// AI tanks randomly fire bullets
function aiFireBullets() {
    if (gameOver) return;
    aiTanks.forEach(tank => {
        if (Math.random() < 0.5) {
            const dirs = [
                { dx: 0, dy: -1 }, { dx: 0, dy: 1 }, { dx: -1, dy: 0 }, { dx: 1, dy: 0 }
            ];
            const dir = dirs[Math.floor(Math.random() * dirs.length)];
            bullets.push({
                x: tank.x,
                y: tank.y,
                dx: dir.dx,
                dy: dir.dy,
                fromAI: true,
                px: tank.x * CELL_SIZE + CELL_SIZE / 2,
                py: tank.y * CELL_SIZE + CELL_SIZE / 2
            });
        }
    });
}

// Update bullets and return if redraw is needed
function updateBullets() {
    let changed = false;
    let allBulletsStopped = true; // Assume all bullets have stopped
    const speed = BULLET_SPEED;
    for (let i = bullets.length - 1; i >= 0; i--) {
        let b = bullets[i];
        if (gameOver) {
            bullets.splice(i, 1);
            changed = true;
            continue;
        }
        let tx = (b.x + b.dx) * CELL_SIZE + CELL_SIZE / 2;
        let ty = (b.y + b.dy) * CELL_SIZE + CELL_SIZE / 2;
        let nx = b.x + b.dx;
        let ny = b.y + b.dy;
        if (nx < 0 || nx >= GRID_SIZE || ny < 0 || ny >= GRID_SIZE) {
            bullets.splice(i, 1);
            changed = true;
            continue;
        }
        let cellType = map[ny][nx];
        if (cellType === CELL_TYPES.STEEL) {
            bullets.splice(i, 1);
            changed = true;
            continue;
        }
        let vx = b.dx * speed;
        let vy = b.dy * speed;
        b.px += vx;
        b.py += vy;
        let reached = (
            (b.dx !== 0 && Math.abs(b.px - tx) < speed) ||
            (b.dy !== 0 && Math.abs(b.py - ty) < speed)
        );
        if (reached) {
            b.x = nx;
            b.y = ny;
            b.px = b.x * CELL_SIZE + CELL_SIZE / 2;
            b.py = b.y * CELL_SIZE + CELL_SIZE / 2;
            if (isDestructible(cellType)) {
                if (cellType === CELL_TYPES.TANK) {
                    let idx = aiTanks.findIndex(t => t.x === b.x && t.y === b.y);
                    if (idx !== -1) aiTanks.splice(idx, 1);
                    idx = playerTanks.findIndex(t => t.x === b.x && t.y === b.y);
                    if (idx !== -1) playerTanks.splice(idx, 1);
                }
                if (cellType === CELL_TYPES.BASE) {
                    gameOver = true;
                    setTimeout(() => alert(b.y < GRID_SIZE / 2 ? 'Player wins!' : 'AI wins!'), 10);
                }
                map[b.y][b.x] = CELL_TYPES.EMPTY;
                bullets.splice(i, 1);
                changed = true;
                continue;
            }
        } else {
            allBulletsStopped = false; // Bullets are still moving
        }
    }
    animating = !allBulletsStopped; // Set animation status
    return changed;
}

// Draw the map, tanks, bullets, and player tank controls
function drawMap(scene) {
    if (!scene || !scene.children) {
        console.error("Scene is not valid:", scene);
        return;
    }

    // Clear all children in the scene
    scene.children.removeAll();

    // Draw the map
    for (let y = 0; y < GRID_SIZE; y++) {
        for (let x = 0; x < GRID_SIZE; x++) {
            let cell = map[y][x];
            let cellType;
            let text = null;

            if (typeof cell === 'object' && cell !== null && cell.type !== undefined) {
                // It's a steel block with text
                cellType = cell.type;
                text = cell.text;
            } else {
                // It's a regular cell
                cellType = cell;
            }

            let color = CELL_COLORS[cellType] || '#f3f4f6';
            scene.add.rectangle(
                x * CELL_SIZE + CELL_SIZE / 2,
                y * CELL_SIZE + CELL_SIZE / 2,
                CELL_SIZE, CELL_SIZE,
                Phaser.Display.Color.HexStringToColor(color).color
            ).setStrokeStyle(1, 0xcccccc);

            if (cellType === CELL_TYPES.BASE) {
                scene.add.star(
                    x * CELL_SIZE + CELL_SIZE / 2,
                    y * CELL_SIZE + CELL_SIZE / 2,
                    5, CELL_SIZE * 0.2, CELL_SIZE * 0.4,
                    0xf59e42
                );
            }

            if (text) {
                // Render the text on the steel block
                scene.add.text(
                    CELL_SIZE * x + CELL_SIZE / 2, // X position
                    y * CELL_SIZE + CELL_SIZE / 2, // Y position
                    text,
                    { font: `${Math.floor(CELL_SIZE * 0.3)}px Arial`, color: "#fff" }
                ).setOrigin(0.5);
            }
        }
    }

    // Draw player tanks
    playerTanks.forEach((t, idx) => {
        scene.add.rectangle(
            t.x * CELL_SIZE + CELL_SIZE / 2,
            t.y * CELL_SIZE + CELL_SIZE / 2,
            CELL_SIZE * 0.7, CELL_SIZE * 0.7,
            t.color
        );
    });

    // Draw AI tanks
    aiTanks.forEach(t => {
        scene.add.rectangle(
            t.x * CELL_SIZE + CELL_SIZE / 2,
            t.y * CELL_SIZE + CELL_SIZE / 2,
            CELL_SIZE * 0.7, CELL_SIZE * 0.7,
            t.color
        );
    });

    // Draw bullets
    bullets.forEach(b => {
        scene.add.circle(
            b.px,
            b.py,
            CELL_SIZE * 0.12,
            0x222222
        );
    });
}

// AI synchronous action logic
function randomAIMoves() {
    const actions = [
        { dx: 0, dy: -1, shoot: false }, // up
        { dx: 0, dy: 1, shoot: false },  // down
        { dx: -1, dy: 0, shoot: false }, // left
        { dx: 1, dy: 0, shoot: false },  // right
        { dx: 0, dy: 0, shoot: false },  // stop
        { dx: 0, dy: -1, shoot: true },  // shoot up
        { dx: 0, dy: 1, shoot: true },   // shoot down
        { dx: -1, dy: 0, shoot: true },  // shoot left
        { dx: 1, dy: 0, shoot: true }    // shoot right
    ];
    let moves = [];
    for (let i = 0; i < aiTanks.length; i++) {
        moves.push(actions[Math.floor(Math.random() * actions.length)]);
    }
    return moves;
}

// Update turn counter
function updateTurnCounter() {
    document.getElementById('turnCounter').innerText = `Turn: ${turn}`;
}

// When a move is selected for a tank
function selectMove(idx, dx, dy, shoot) {
    if (gameOver || animating) return; // Prevent actions during animation or after game over
    pendingMoves[idx] = { dx, dy, shoot: !!shoot };

    // Only proceed if both tanks have moves selected
    if (pendingMoves[0] && pendingMoves[1]) {
        animating = true; // Set animating to true before actions
        // Player actions
        for (let i = 0; i < 2; i++) {
            let t = playerTanks[i];
            let move = pendingMoves[i];
            if (move.shoot && (move.dx !== 0 || move.dy !== 0)) {
                bullets.push({
                    x: t.x,
                    y: t.y,
                    dx: move.dx,
                    dy: move.dy,
                    fromAI: false,
                    px: t.x * CELL_SIZE + CELL_SIZE / 2,
                    py: t.y * CELL_SIZE + CELL_SIZE / 2
                });
            } else if (!move.shoot) {
                let nx = t.x + move.dx, ny = t.y + move.dy;
                if (canMove(nx, ny)) {
                    map[t.y][t.x] = CELL_TYPES.EMPTY;
                    t.x = nx;
                    t.y = ny;
                    map[t.y][t.x] = CELL_TYPES.TANK;
                }
            }
        }
        // AI actions (synchronous)
        let aiActions = randomAIMoves();
        for (let i = 0; i < aiTanks.length; i++) {
            let t = aiTanks[i];
            let move = aiActions[i];
            if (move.shoot && (move.dx !== 0 || move.dy !== 0)) {
                bullets.push({
                    x: t.x,
                    y: t.y,
                    dx: move.dx,
                    dy: move.dy,
                    fromAI: true,
                    px: t.x * CELL_SIZE + CELL_SIZE / 2,
                    py: t.y * CELL_SIZE + CELL_SIZE / 2
                });
            } else if (!move.shoot) {
                let nx = t.x + move.dx, ny = t.y + move.dy;
                if (canMove(nx, ny)) {
                    map[t.y][t.x] = CELL_TYPES.EMPTY;
                    t.x = nx;
                    t.y = ny;
                    map[t.y][t.x] = CELL_TYPES.TANK;
                }
            }
        }
        pendingMoves = [null, null];
        // Redraw after both moves
        this.drawMap();
        // Increment turn counter
        turn++;
        updateTurnCounter();
    }
}

// Check if a tank can move to a cell
function canMove(x, y) {
    return x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE && map[y][x] === CELL_TYPES.EMPTY;
}

// Create control buttons
function createControlButtons(scene) {
    const buttonContainer = document.createElement('div');
    buttonContainer.id = 'control-buttons';
    buttonContainer.style.display = 'flex';
    buttonContainer.style.flexWrap = 'wrap';
    buttonContainer.style.justifyContent = 'center';
    buttonContainer.style.marginTop = '20px';

    const actions = [
        { dx: 0, dy: -1, shoot: false, label: "↑ Move" },
        { dx: 0, dy: 1, shoot: false, label: "↓ Move" },
        { dx: -1, dy: 0, shoot: false, label: "← Move" },
        { dx: 1, dy: 0, shoot: false, label: "→ Move" },
        { dx: 0, dy: -1, shoot: true, label: "↑ Shoot" },
        { dx: 0, dy: 1, shoot: true, label: "↓ Shoot" },
        { dx: -1, dy: 0, shoot: true, label: "← Shoot" },
        { dx: 1, dy: 0, shoot: true, label: "→ Shoot" },
        { dx: 0, dy: 0, shoot: false, label: "Stop" }
    ];

    // Create buttons for each tank
    for (let tankIdx = 0; tankIdx < 2; tankIdx++) {
        const tankLabel = document.createElement('div');
        tankLabel.textContent = `Tank ${tankIdx + 1}`;
        tankLabel.style.width = '100%';
        tankLabel.style.textAlign = 'center';
        tankLabel.style.margin = '10px 0';
        tankLabel.style.fontWeight = 'bold';
        buttonContainer.appendChild(tankLabel);

        actions.forEach(action => {
            const button = document.createElement('button');
            button.textContent = action.label;
            button.style.margin = '5px';
            button.style.padding = '10px 15px';
            button.style.border = '1px solid #ccc';
            button.style.borderRadius = '5px';
            button.style.backgroundColor = '#f3f4f6';
            button.style.cursor = 'pointer';

            button.addEventListener('click', () => {
                selectMove(tankIdx, action.dx, action.dy, action.shoot);
            });

            buttonContainer.appendChild(button);
        });
    }

    // Append the buttons to the DOM
    const container = document.getElementById('phaser-container');
    container.parentNode.appendChild(buttonContainer);
}

// Phaser config:
const config = {
    type: Phaser.AUTO,
    width: 600,
    height: 600,
    parent: 'phaser-container',
    backgroundColor: '#e5e7eb',
    scene: {
        preload: function () { },
        create: function () {
            // Bind drawMap to the scene
            this.drawMap = () => drawMap(this);
            // Initial map
            createInitialMap();

            // Create control buttons
            createControlButtons(this);

            // New Game button
            document.getElementById('newGameBtn').onclick = () => {
                socket.emit('new_game', { user_id: userId });
                this.drawMap(); // Pass the scene instance here
            };
        },
        update: function () {
            // Update bullets and redraw if needed
            let needRedraw = updateBullets();
            if (needRedraw) {
                this.drawMap();
            }
        }
    }
};
let game = new Phaser.Game(config);

const socket = io('/tank2');

socket.on('connect', () => {

});

socket.on('init', (data) => {
    userId = data.user_id;
    console.debug(data.state);
    // map[1][1] = CELL_TYPES.BRICK;
    drawMap(config.scene);
});