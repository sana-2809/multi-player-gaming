import socket
import json
import sys
import threading
import pygame
import config

# Global state for rendering
game_state = {
    "players": {},
    "food": None
}
state_lock = threading.Lock()
running = True

def receive_state(sock):
    global running
    buffer = ""
    while running:
        try:
            data = sock.recv(4096)
            if not data:
                print("Server closed connection.")
                running = False
                break
            
            buffer += data.decode('utf-8')
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line:
                    try:
                        new_state = json.loads(line)
                        with state_lock:
                            game_state["players"] = new_state.get("players", {})
                            game_state["food"] = new_state.get("food", None)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            if running:
                print(f"Disconnected from server: {e}")
            running = False
            break

def main():
    global running
    
    host = sys.argv[1] if len(sys.argv) > 1 else config.SERVER_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else config.SERVER_PORT

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        print(f"Connected to server at {host}:{port}!")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    # Start network thread
    threading.Thread(target=receive_state, args=(sock,), daemon=True).start()

    # Pygame setup
    pygame.init()
    screen = pygame.display.set_mode((config.BOARD_WIDTH, config.BOARD_HEIGHT))
    pygame.display.set_caption("Multiplayer Snake Game - Client")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 24)

    try:
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    action = None
                    if event.key in (pygame.K_w, pygame.K_UP):
                        action = {"dir": "UP"}
                    elif event.key in (pygame.K_s, pygame.K_DOWN):
                        action = {"dir": "DOWN"}
                    elif event.key in (pygame.K_a, pygame.K_LEFT):
                        action = {"dir": "LEFT"}
                    elif event.key in (pygame.K_d, pygame.K_RIGHT):
                        action = {"dir": "RIGHT"}
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                    
                    if action:
                        try:
                            msg = json.dumps(action) + "\n"
                            sock.sendall(msg.encode('utf-8'))
                        except Exception:
                            running = False

            # Rendering
            screen.fill((30, 30, 30))
            
            with state_lock:
                food = game_state.get("food")
                if food:
                    fx, fy = food
                    center_x = fx * config.GRID_SIZE + config.GRID_SIZE // 2
                    center_y = fy * config.GRID_SIZE + config.GRID_SIZE // 2
                    radius = config.GRID_SIZE // 2
                    pygame.draw.circle(
                        screen,
                        (255, 255, 255),
                        (center_x, center_y),
                        radius
                    )

                players = game_state.get("players", {})
                for addr_str, player in players.items():
                    if not player.get("alive", False):
                        continue

                    color = player.get("color", [200, 200, 200])
                    body = player.get("body", [])
                    
                    if len(body) > 0:
                        hx, hy = body[0]
                        head_color = (min(255, color[0] + 50), min(255, color[1] + 50), min(255, color[2] + 50))
                        pygame.draw.rect(
                            screen, head_color,
                            (hx * config.GRID_SIZE, hy * config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                        )
                        
                        for segment in body[1:]:
                            sx, sy = segment
                            pygame.draw.rect(
                                screen, color,
                                (sx * config.GRID_SIZE, sy * config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                            )
                            
                # Draw Scores UI
                y_offset = 10
                for addr_str, player in players.items():
                    color = player.get("color", (255, 255, 255))
                    score_text = font.render(f"P: {player.get('score', 0)}", True, color)
                    screen.blit(score_text, (config.BOARD_WIDTH - 100, y_offset))
                    y_offset += 30

            pygame.display.flip()
            clock.tick(60)

    except KeyboardInterrupt:
        pass
    finally:
        running = False
        sock.close()
        pygame.quit()
        print("Disconnected.")
        sys.exit()

if __name__ == "__main__":
    main()
