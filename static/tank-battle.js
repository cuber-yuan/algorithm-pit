const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

canvas.width = 800;
canvas.height = 600;

let playerScore = 0;
let enemyScore = 0;

// 玩家坦克出生在下方中央
const playerTank = {
    x: canvas.width / 2 - 20,
    y: canvas.height - 60,
    width: 40,
    height: 40,
    speed: 5,
    color: "blue",
    direction: 0,
    bullets: [],
    moveUp: false,
    moveDown: false,
    moveLeft: false,
    moveRight: false,
};

// 敌人坦克出生在上方中央
const enemyTank = {
    x: canvas.width / 2 - 20,
    y: 20,
    width: 40,
    height: 40,
    speed: 3,
    color: "red",
    direction: 2,
    bullets: [],
};

class Bullet {
    constructor(x, y, direction, owner) {
        this.x = x;
        this.y = y;
        this.width = 5;
        this.height = 5;
        this.speed = 6;
        this.direction = direction;
        this.owner = owner;
    }

    move() {
        if (this.direction === 0) this.y -= this.speed;
        if (this.direction === 1) this.x += this.speed;
        if (this.direction === 2) this.y += this.speed;
        if (this.direction === 3) this.x -= this.speed;
    }

    draw() {
        ctx.fillStyle = this.owner === 'player' ? 'blue' : 'red';
        ctx.fillRect(this.x, this.y, this.width, this.height);
    }

    isOutOfBounds() {
        return (
            this.x < 0 || this.x > canvas.width ||
            this.y < 0 || this.y > canvas.height
        );
    }
}

function drawTank(tank) {
    ctx.fillStyle = tank.color;
    ctx.fillRect(tank.x, tank.y, tank.width, tank.height);
}

function movePlayerTank() {
    if (playerTank.moveUp) playerTank.y -= playerTank.speed;
    if (playerTank.moveDown) playerTank.y += playerTank.speed;
    if (playerTank.moveLeft) playerTank.x -= playerTank.speed;
    if (playerTank.moveRight) playerTank.x += playerTank.speed;
}

function moveEnemyTank() {
    const dx = playerTank.x - enemyTank.x;
    const dy = playerTank.y - enemyTank.y;
    const distance = Math.sqrt(dx * dx + dy * dy);

    let safeDistance = 100;

    // 避开玩家子弹
    for (let bullet of playerTank.bullets) {
        let dangerZoneY = enemyTank.y + enemyTank.height;
        if (
            bullet.direction === 0 &&
            Math.abs(bullet.x - enemyTank.x) < 40 &&
            bullet.y < dangerZoneY &&
            bullet.y > enemyTank.y
        ) {
            // 向左右躲避
            if (enemyTank.x > 50 && Math.random() > 0.5) {
                enemyTank.x -= enemyTank.speed;
            } else if (enemyTank.x < canvas.width - 50) {
                enemyTank.x += enemyTank.speed;
            }
            return;
        }
    }

    // AI靠近但保持安全距离
    if (distance > safeDistance) {
        if (Math.abs(dx) > 10) {
            enemyTank.x += dx > 0 ? enemyTank.speed : -enemyTank.speed;
        }
        if (Math.abs(dy) > 10) {
            enemyTank.y += dy > 0 ? enemyTank.speed : -enemyTank.speed;
        }
    }
}

function checkCollision(bullet, target) {
    return (
        bullet.x < target.x + target.width &&
        bullet.x + bullet.width > target.x &&
        bullet.y < target.y + target.height &&
        bullet.y + bullet.height > target.y
    );
}

function resetPositions() {
    playerTank.x = canvas.width / 2 - 20;
    playerTank.y = canvas.height - 60;
    playerTank.bullets = [];

    enemyTank.x = canvas.width / 2 - 20;
    enemyTank.y = 20;
    enemyTank.bullets = [];
}

function drawScores() {
    ctx.fillStyle = "black";
    ctx.font = "20px Arial";
    ctx.fillText(`Player: ${playerScore}`, 20, 30);
    ctx.fillText(`Enemy: ${enemyScore}`, canvas.width - 120, 30);
}

function updateGame() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    movePlayerTank();
    moveEnemyTank();

    drawTank(playerTank);
    drawTank(enemyTank);
    drawScores();

    // 玩家子弹处理
    playerTank.bullets.forEach((bullet, i) => {
        bullet.move();
        bullet.draw();

        if (checkCollision(bullet, enemyTank)) {
            playerScore += 1;
            resetPositions();
        }

        if (bullet.isOutOfBounds()) {
            playerTank.bullets.splice(i, 1);
        }
    });

    // 敌人子弹处理
    enemyTank.bullets.forEach((bullet, i) => {
        bullet.move();
        bullet.draw();

        if (checkCollision(bullet, playerTank)) {
            enemyScore += 1;
            resetPositions();
        }

        if (bullet.isOutOfBounds()) {
            enemyTank.bullets.splice(i, 1);
        }
    });

    requestAnimationFrame(updateGame);
}

// 键盘控制
document.addEventListener("keydown", (e) => {
    if (e.key === "w") playerTank.moveUp = true;
    if (e.key === "s") playerTank.moveDown = true;
    if (e.key === "a") playerTank.moveLeft = true;
    if (e.key === "d") playerTank.moveRight = true;
    if (e.key === " ") {
        const bullet = new Bullet(
            playerTank.x + playerTank.width / 2 - 2,
            playerTank.y,
            0,
            "player"
        );
        playerTank.bullets.push(bullet);
    }
});

document.addEventListener("keyup", (e) => {
    if (e.key === "w") playerTank.moveUp = false;
    if (e.key === "s") playerTank.moveDown = false;
    if (e.key === "a") playerTank.moveLeft = false;
    if (e.key === "d") playerTank.moveRight = false;
});

// 敌人定时发射子弹
setInterval(() => {
    const bullet = new Bullet(
        enemyTank.x + enemyTank.width / 2 - 2,
        enemyTank.y + enemyTank.height,
        2,
        "enemy"
    );
    enemyTank.bullets.push(bullet);
}, 2000);

updateGame();
