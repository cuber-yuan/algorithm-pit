// This script is loaded by tank.html after the Phaser game object is created.
// The 'mainScene' variable is globally available and points to the main Phaser scene.

const FIELD_WIDTH = 9; // The width of the field in tiles
const FIELD_HEIGHT = 9; // The height of the field in tiles

// --- Extend the main Phaser scene with our game logic ---

class TankScene extends Phaser.Scene {
    constructor() {
        super({ key: 'TankScene' });
        // These properties will be initialized in create()
        this.mapLayer = null;
        this.baseLayer = null;
        this.tankLayer = null;
        this.mapDrawn = false;
        this.CELL_SIZE = 0;
    }

    preload() {
        const assetPath = '/static/tank2/assets/';
        this.load.image('brick', assetPath + 'brick.png');
        this.load.image('steel', assetPath + 'steel.png');
        this.load.image('water', assetPath + 'water.png');
        this.load.image('base', assetPath + 'base.png');
        this.load.image('tank_blue', assetPath + 'tank_blue.png');
        this.load.image('tank_red', assetPath + 'tank_red.png');
    }

    create() {
        // 不再需要将场景实例赋值给全局变量
        // window.mainScene = this;

        const canvasWidth = this.game.config.width;
        this.CELL_SIZE = canvasWidth / 9; // FIELD_WIDTH is 9

        this.mapLayer = this.add.group();
        this.baseLayer = this.add.group();
        this.tankLayer = this.add.group();

        this.mapDrawn = false;
        
        // The mask is controlled by tank.html. We no longer show it here by default.
        // if (window.showPhaserMask) {
        //     window.showPhaserMask("Select players and start a new game.");
        // }
    }

    updateFromState(state) {
        // --- DEBUG ---
        console.log("[TankScene] updateFromState called with state:", state);
        // --- END DEBUG ---
        if (!state) return;

        if (!this.mapDrawn && state.brick_binary) {
            this.drawMap(state.brick_binary, state.water_binary, state.steel_binary);
            this.mapDrawn = true;
        }

        this.tankLayer.clear(true, true);
        this.baseLayer.clear(true, true);

        if (state.tanks) {
            // --- DEBUG ---
            console.log(`[TankScene] Processing ${state.tanks.length} tanks.`);
            // --- END DEBUG ---
            state.tanks.forEach(tank => {
                if (tank.alive) {
                    const spriteKey = tank.side === 'top' ? 'tank_blue' : 'tank_red';
                    const x = (tank.x + 0.5) * this.CELL_SIZE;
                    const y = (tank.y + 0.5) * this.CELL_SIZE;
                    // --- DEBUG ---
                    console.log(`[TankScene] Drawing tank for side ${tank.side} at (${x.toFixed(2)}, ${y.toFixed(2)})`);
                    // --- END DEBUG ---
                    const tankSprite = this.add.sprite(x, y, spriteKey);
                    tankSprite.setDisplaySize(this.CELL_SIZE * 0.9, this.CELL_SIZE * 0.9);
                    this.tankLayer.add(tankSprite);
                }
            });
        }

        if (state.bases) {
            if (state.bases.top.alive) {
                const x = (4.5) * this.CELL_SIZE; // FIELD_WIDTH / 2
                const y = (0.5) * this.CELL_SIZE;
                const baseSprite = this.add.sprite(x, y, 'base');
                baseSprite.setDisplaySize(this.CELL_SIZE, this.CELL_SIZE);
                this.baseLayer.add(baseSprite);
            }
            if (state.bases.bottom.alive) {
                const x = (4.5) * this.CELL_SIZE; // FIELD_WIDTH / 2
                const y = (8.5) * this.CELL_SIZE; // FIELD_HEIGHT - 0.5
                const baseSprite = this.add.sprite(x, y, 'base');
                baseSprite.setDisplaySize(this.CELL_SIZE, this.CELL_SIZE);
                this.baseLayer.add(baseSprite);
            }
        }

        const turnCounter = document.getElementById('turnCounter');
        if (turnCounter && state.turn) {
            turnCounter.textContent = `Turn: ${state.turn} / ${state.max_turn}`;
        }
    }

    drawMap(brickBinary, waterBinary, steelBinary) {
        // --- DEBUG ---
        console.log("[TankScene] drawMap called.");
        // --- END DEBUG ---
        this.mapLayer.clear(true, true);
        const FIELD_WIDTH = 9;

        const drawLayer = (binaryData, spriteKey) => {
            for (let i = 0; i < 3; i++) {
                let mask = 1;
                const chunk = binaryData[i];
                for (let y_offset = 0; y_offset < 3; y_offset++) {
                    for (let x_offset = 0; x_offset < FIELD_WIDTH; x_offset++) {
                        if (chunk & mask) {
                            const y = i * 3 + y_offset;
                            const x = x_offset;
                            const tileX = (x + 0.5) * this.CELL_SIZE;
                            const tileY = (y + 0.5) * this.CELL_SIZE;
                            // --- DEBUG ---
                            console.log(`[TankScene] Drawing tile '${spriteKey}' at (${x}, ${y})`);
                            // --- END DEBUG ---
                            const tile = this.add.sprite(tileX, tileY, spriteKey);
                            tile.setDisplaySize(this.CELL_SIZE, this.CELL_SIZE);
                            this.mapLayer.add(tile);
                        }
                        mask <<= 1;
                    }
                }
            }
        };

        drawLayer(waterBinary, 'water');
        drawLayer(brickBinary, 'brick');
        drawLayer(steelBinary, 'steel');
    }
}