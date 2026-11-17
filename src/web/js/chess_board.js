/**
 * Modular Chessboard Component for Subagent Lab.
 * Renders an 8x8 grid from FEN strings, manages square selection,
 * highlights legal move destinations, and emits validated moves.
 * Accessible SVG rendering without decorative emojis.
 */

export const DEFAULT_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

const PIECE_NAMES = {
    p: "Pawn",
    r: "Rook",
    n: "Knight",
    b: "Bishop",
    q: "Queen",
    k: "King",
};

/**
 * Generate clean SVG vectors for chess pieces to ensure crisp rendering
 * without emoji dependencies.
 */
function getPieceSvg(type, color) {
    const isWhite = color === "white";
    const fill = isWhite ? "#f0f4f8" : "#1a1f26";
    const stroke = isWhite ? "#2d3748" : "#cbd5e1";
    const strokeWidth = "1.5";

    const symbolMap = {
        p: `<circle cx="22.5" cy="14" r="6" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><path d="M16 34 L29 34 L26 22 L19 22 Z" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><rect x="13" y="34" width="19" height="5" rx="2" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/>`,
        r: `<rect x="14" y="12" width="17" height="8" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><rect x="17" y="20" width="11" height="13" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><rect x="12" y="33" width="21" height="6" rx="2" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><line x1="18" y1="12" x2="18" y2="16" stroke="${stroke}"/><line x1="27" y1="12" x2="27" y2="16" stroke="${stroke}"/>`,
        n: `<path d="M15 35 L30 35 L28 27 C28 23 32 19 30 13 C26 12 23 15 21 16 L20 13 L17 14 L16 19 L13 22 L14 26 L17 26 Z" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><circle cx="24" cy="18" r="1.5" fill="${stroke}"/>`,
        b: `<path d="M22.5 10 C18 15 17 23 20 28 L25 28 C28 23 27 15 22.5 10 Z" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><rect x="14" y="33" width="17" height="5" rx="2" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><circle cx="22.5" cy="9" r="2" fill="${fill}" stroke="${stroke}"/><line x1="20" y1="18" x2="25" y2="18" stroke="${stroke}"/>`,
        q: `<path d="M14 20 L18 31 L27 31 L31 20 L26 23 L22.5 14 L19 23 Z" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><circle cx="14" cy="18" r="2" fill="${fill}" stroke="${stroke}"/><circle cx="22.5" cy="12" r="2" fill="${fill}" stroke="${stroke}"/><circle cx="31" cy="18" r="2" fill="${fill}" stroke="${stroke}"/><rect x="13" y="33" width="19" height="5" rx="2" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/>`,
        k: `<path d="M16 22 L18 32 L27 32 L29 22 C29 18 26 16 22.5 16 C19 16 16 18 16 22 Z" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><rect x="13" y="34" width="19" height="5" rx="2" fill="${fill}" stroke="${stroke}" stroke-width="${strokeWidth}"/><line x1="22.5" y1="9" x2="22.5" y2="15" stroke="${stroke}" stroke-width="2"/><line x1="19.5" y1="11.5" x2="25.5" y2="11.5" stroke="${stroke}" stroke-width="2"/>`,
    };

    const inner = symbolMap[type.toLowerCase()] || "";
    return `<svg class="chess-piece-svg piece-${color}" viewBox="0 0 45 45" aria-label="${color} ${PIECE_NAMES[type.toLowerCase()] || type}">${inner}</svg>`;
}

export class ChessBoardComponent {
    constructor(containerEl, options = {}) {
        this.container = containerEl;
        this.onMove = options.onMove || null;
        this.selectedSquare = null;
        this.legalMoves = [];
        this.lastMove = null;
        this.fen = DEFAULT_FEN;
        this.playerColor = "spectator"; // "white", "black", or "spectator"
        this.isInteractive = false;
        this.orientation = "white"; // "white" or "black"
    }

    setPlayerMode(mode) {
        this.playerColor = mode;
        this.isInteractive = mode === "white" || mode === "black";
        this.orientation = mode === "black" ? "black" : "white";
        this.selectedSquare = null;
        this.render();
    }

    parseFEN(fen) {
        const board = {};
        const parts = fen.split(" ");
        const position = parts[0] || "";
        const ranks = position.split("/");

        ranks.forEach((rankStr, rankIndex) => {
            const rankNum = 8 - rankIndex;
            let fileIndex = 0;
            for (let i = 0; i < rankStr.length; i++) {
                const char = rankStr[i];
                if (char >= "1" && char <= "8") {
                    fileIndex += parseInt(char, 10);
                } else {
                    const fileLetter = String.fromCharCode(97 + fileIndex);
                    const square = `${fileLetter}${rankNum}`;
                    const color = char === char.toUpperCase() ? "white" : "black";
                    board[square] = {
                        type: char.toLowerCase(),
                        color: color,
                    };
                    fileIndex++;
                }
            }
        });

        return {
            pieces: board,
            activeColor: parts[1] === "b" ? "black" : "white",
            fullmoveNumber: parseInt(parts[5] || "1", 10),
        };
    }

    renderFromFEN(fen, legalMoves = [], lastMove = null) {
        this.fen = fen || this.fen;
        this.legalMoves = legalMoves || [];
        if (lastMove) {
            this.lastMove = lastMove;
        }
        this.render();
    }

    handleSquareClick(square) {
        if (!this.isInteractive) {
            return;
        }

        const parsed = this.parseFEN(this.fen);
        // Ensure it is currently the player's turn to move
        if (parsed.activeColor !== this.playerColor) {
            return;
        }

        const piece = parsed.pieces[square];

        // If a square is already selected
        if (this.selectedSquare) {
            // Clicking the same square deselects
            if (this.selectedSquare === square) {
                this.selectedSquare = null;
                this.render();
                return;
            }

            // Check if clicking another friendly piece
            if (piece && piece.color === this.playerColor) {
                this.selectedSquare = square;
                this.render();
                return;
            }

            // Attempt move from selectedSquare to square
            const attemptedUci = `${this.selectedSquare}${square}`;
            // Handle pawn promotion fallback to Queen if applicable
            const matchMove = this.legalMoves.find(
                (m) => m === attemptedUci || m === `${attemptedUci}q`
            );

            if (matchMove && this.onMove) {
                const moveToSend = matchMove;
                this.selectedSquare = null;
                this.onMove(moveToSend);
                return;
            }

            // Otherwise, invalid destination: clear selection
            this.selectedSquare = null;
            this.render();
            return;
        }

        // No square selected yet: select if square contains user piece
        if (piece && piece.color === this.playerColor) {
            this.selectedSquare = square;
            this.render();
        }
    }

    render() {
        if (!this.container) return;

        const parsed = this.parseFEN(this.fen);
        const pieces = parsed.pieces;

        const ranks = this.orientation === "black"
            ? [1, 2, 3, 4, 5, 6, 7, 8]
            : [8, 7, 6, 5, 4, 3, 2, 1];

        const files = this.orientation === "black"
            ? ["h", "g", "f", "e", "d", "c", "b", "a"]
            : ["a", "b", "c", "d", "e", "f", "g", "h"];

        // Determine destination targets for currently selected square
        const targetSquares = new Set();
        if (this.selectedSquare) {
            this.legalMoves.forEach((moveStr) => {
                if (moveStr.startsWith(this.selectedSquare)) {
                    targetSquares.add(moveStr.slice(2, 4));
                }
            });
        }

        // Parse last move squares (e.g. "e2e4" -> from "e2", to "e4")
        let lastFrom = null;
        let lastTo = null;
        if (this.lastMove && this.lastMove.length >= 4) {
            lastFrom = this.lastMove.slice(0, 2);
            lastTo = this.lastMove.slice(2, 4);
        }

        this.container.innerHTML = "";

        ranks.forEach((rank, rIdx) => {
            files.forEach((file, fIdx) => {
                const square = `${file}${rank}`;
                const isLight = (rIdx + fIdx) % 2 === 0;
                const squareEl = document.createElement("div");
                squareEl.className = `chess-square ${isLight ? "square-light" : "square-dark"}`;
                squareEl.dataset.square = square;

                if (square === this.selectedSquare) {
                    squareEl.classList.add("square-selected");
                }
                if (targetSquares.has(square)) {
                    squareEl.classList.add("square-target");
                }
                if (square === lastFrom || square === lastTo) {
                    squareEl.classList.add("square-last-move");
                }

                // Render piece if present
                const piece = pieces[square];
                if (piece) {
                    squareEl.innerHTML = getPieceSvg(piece.type, piece.color);
                }

                // Coordinate hints on border squares
                if (fIdx === 0) {
                    const rankLabel = document.createElement("span");
                    rankLabel.className = "coord-label coord-rank";
                    rankLabel.textContent = rank;
                    squareEl.appendChild(rankLabel);
                }
                if (rIdx === 7) {
                    const fileLabel = document.createElement("span");
                    fileLabel.className = "coord-label coord-file";
                    fileLabel.textContent = file;
                    squareEl.appendChild(fileLabel);
                }

                squareEl.setAttribute("role", "button");
                squareEl.tabIndex = 0;
                const pieceDesc = piece ? `, ${piece.color} ${PIECE_NAMES[piece.type] || piece.type}` : ", empty";
                squareEl.setAttribute("aria-label", `${square}${pieceDesc}`);
                squareEl.addEventListener("keydown", (e) => {
                    if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        this.handleSquareClick(square);
                    }
                });

                squareEl.addEventListener("click", () => this.handleSquareClick(square));
                this.container.appendChild(squareEl);
            });
        });
    }
}
