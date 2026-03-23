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

class UIState:
    MENU = 0
    PLAYING = 1
    DEAD = 2

current_ui_state = UIState.MENU
sock = None

def receive_state(socket_conn):
    global running, current_ui_state
    buffer = ""
    while running:
        try:
            data = socket_conn.recv(4096)
            if not data:
                print("Server closed connection.")
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
            break
            
    # If connection dies, we go back to menu
    if current_ui_state in [UIState.PLAYING, UIState.DEAD]:
        current_ui_state = UIState.MENU

def draw_grid(screen):
    grid_color = (40, 40, 45)
    for x in range(0, config.BOARD_WIDTH, config.GRID_SIZE):
        pygame.draw.line(screen, grid_color, (x, 0), (x, config.BOARD_HEIGHT))
    for y in range(0, config.BOARD_HEIGHT, config.GRID_SIZE):
        pygame.draw.line(screen, grid_color, (0, y), (config.BOARD_WIDTH, y))

def draw_glow(screen, color, center, radius):
    surf = pygame.Surface((radius*4, radius*4), pygame.SRCALPHA)
    pygame.draw.circle(surf, (*color, 40), (radius*2, radius*2), radius*2)
    pygame.draw.circle(surf, (*color, 80), (radius*2, radius*2), radius*1.4)
    pygame.draw.circle(surf, color, (radius*2, radius*2), radius*0.8)
    screen.blit(surf, (center[0]-radius*2, center[1]-radius*2))

def main():
    global running, current_ui_state, sock
    
    host = sys.argv[1] if len(sys.argv) > 1 else config.SERVER_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else config.SERVER_PORT

    pygame.init()
    screen = pygame.display.set_mode((config.BOARD_WIDTH, config.BOARD_HEIGHT))
    pygame.display.set_caption("Multiplayer Snake - Enhanced UI")
    clock = pygame.time.Clock()
    
    font_title = pygame.font.SysFont("Verdana", 54, bold=True)
    font_large = pygame.font.SysFont("Arial", 48, bold=True)
    font_medium = pygame.font.SysFont("Arial", 32, bold=True)
    font_small = pygame.font.SysFont("Arial", 20, bold=True)

    btn_w, btn_h = 300, 70
    btn_rect = pygame.Rect((config.BOARD_WIDTH - btn_w)//2, (config.BOARD_HEIGHT - btn_h)//2 + 50, btn_w, btn_h)

    def connect_to_server():
        global sock
        nonlocal host, port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((host, port))
            print(f"Connected to server at {host}:{port}!")
            threading.Thread(target=receive_state, args=(sock,), daemon=True).start()
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    try:
        while running:
            # Determine self state for "YOU DIED" flow
            my_local_addr = None
            if sock and current_ui_state in [UIState.PLAYING, UIState.DEAD]:
                try:
                    my_local_addr = f"{sock.getsockname()[0]}:{sock.getsockname()[1]}"
                    with state_lock:
                        me = game_state["players"].get(my_local_addr)
                        if me:
                            if not me.get("alive", False) and current_ui_state == UIState.PLAYING:
                                current_ui_state = UIState.DEAD
                            elif me.get("alive", True) and current_ui_state == UIState.DEAD:
                                current_ui_state = UIState.PLAYING
                except Exception:
                    pass

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if current_ui_state == UIState.MENU:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1 and btn_rect.collidepoint(event.pos):
                            if connect_to_server():
                                current_ui_state = UIState.PLAYING
                
                elif current_ui_state == UIState.PLAYING:
                    if event.type == pygame.KEYDOWN:
                        action = None
                        if event.key in (pygame.K_w, pygame.K_UP): action = {"dir": "UP"}
                        elif event.key in (pygame.K_s, pygame.K_DOWN): action = {"dir": "DOWN"}
                        elif event.key in (pygame.K_a, pygame.K_LEFT): action = {"dir": "LEFT"}
                        elif event.key in (pygame.K_d, pygame.K_RIGHT): action = {"dir": "RIGHT"}
                        elif event.key == pygame.K_ESCAPE: running = False
                        
                        if action and sock:
                            try:
                                msg = json.dumps(action) + "\n"
                                sock.sendall(msg.encode('utf-8'))
                            except Exception:
                                pass
            
            # Rendering
            screen.fill((20, 22, 28)) # Dark modern bluish-gray background

            if current_ui_state == UIState.MENU:
                # Title
                title = font_title.render("MULTIPLAYER SNAKE", True, (240, 240, 250))
                
                # Title Shadow
                shadow = font_title.render("MULTIPLAYER SNAKE", True, (0, 0, 0))
                screen.blit(shadow, (config.BOARD_WIDTH//2 - title.get_width()//2 + 3, 153))
                screen.blit(title, (config.BOARD_WIDTH//2 - title.get_width()//2, 150))
                
                # Connect Button
                mouse_pos = pygame.mouse.get_pos()
                color = (60, 200, 100) if btn_rect.collidepoint(mouse_pos) else (40, 160, 80)
                
                # Button shadow
                pygame.draw.rect(screen, (20, 80, 40), btn_rect.move(0, 5), border_radius=15)
                pygame.draw.rect(screen, color, btn_rect, border_radius=15)
                
                btn_txt = font_medium.render("PLAY NOW", True, (255, 255, 255))
                screen.blit(btn_txt, (btn_rect.x + (btn_rect.width - btn_txt.get_width())//2, btn_rect.y + (btn_rect.height - btn_txt.get_height())//2))
            
            elif current_ui_state in [UIState.PLAYING, UIState.DEAD]:
                draw_grid(screen)
                
                with state_lock:
                    food = game_state.get("food")
                    if food:
                        fx, fy = food
                        center_x = fx * config.GRID_SIZE + config.GRID_SIZE // 2
                        center_y = fy * config.GRID_SIZE + config.GRID_SIZE // 2
                        draw_glow(screen, (255, 60, 60), (center_x, center_y), config.GRID_SIZE // 2)

                    players = game_state.get("players", {})
                    scores = []

                    for addr_str, player in players.items():
                        base_color = player.get("color", [200, 200, 200])
                        scores.append((addr_str, player.get("score", 0), base_color))
                        
                        if not player.get("alive", False):
                            continue
                        
                        body = player.get("body", [])
                        if len(body) > 0:
                            # Draw body (rounded rectangles)
                            for segment in body[1:]:
                                sx, sy = segment
                                rect = (sx * config.GRID_SIZE + 1, sy * config.GRID_SIZE + 1, config.GRID_SIZE - 2, config.GRID_SIZE - 2)
                                pygame.draw.rect(screen, base_color, rect, border_radius=5)
                            
                            # Draw head (brighter, slightly larger)
                            hx, hy = body[0]
                            head_color = (min(255, base_color[0] + 80), min(255, base_color[1] + 80), min(255, base_color[2] + 80))
                            rect = (hx * config.GRID_SIZE, hy * config.GRID_SIZE, config.GRID_SIZE, config.GRID_SIZE)
                            pygame.draw.rect(screen, head_color, rect, border_radius=7)

                # Draw Scoreboard
                if scores:
                    scores.sort(key=lambda x: x[1], reverse=True)
                    panel_w, panel_h = 180, 40 + len(scores) * 35
                    panel_rect = pygame.Rect(config.BOARD_WIDTH - panel_w - 20, 20, panel_w, panel_h)
                    
                    # Frosted glass overlay
                    overlay = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 160))
                    screen.blit(overlay, panel_rect.topleft)
                    pygame.draw.rect(screen, (80, 80, 90), panel_rect, width=2, border_radius=10)
                    
                    y_offset = 35
                    title_txt = font_small.render("LEADERBOARD", True, (220, 220, 230))
                    screen.blit(title_txt, (panel_rect.x + (panel_w - title_txt.get_width())//2, panel_rect.y + 10))
                    pygame.draw.line(screen, (100, 100, 110), (panel_rect.x + 10, panel_rect.y + 35), (panel_rect.x + panel_w - 10, panel_rect.y + 35))
                    
                    for i, (addr_str, sc, color) in enumerate(scores):
                        name = f"Player {i+1}"
                        if my_local_addr and addr_str == my_local_addr:
                            name = "YOU"
                        txt = font_small.render(f"{name}: {sc}", True, color)
                        screen.blit(txt, (panel_rect.x + 15, panel_rect.y + y_offset + 5))
                        y_offset += 30

                if current_ui_state == UIState.DEAD:
                    overlay = pygame.Surface((config.BOARD_WIDTH, config.BOARD_HEIGHT), pygame.SRCALPHA)
                    overlay.fill((200, 0, 0, 90)) # Red tint for death screen
                    screen.blit(overlay, (0, 0))
                    
                    dead_txt = font_large.render("YOU DIED", True, (255, 50, 50))
                    # Add shadow
                    shadow = font_large.render("YOU DIED", True, (0,0,0))
                    screen.blit(shadow, (config.BOARD_WIDTH//2 - dead_txt.get_width()//2 + 2, config.BOARD_HEIGHT//2 - 60 + 2))
                    screen.blit(dead_txt, (config.BOARD_WIDTH//2 - dead_txt.get_width()//2, config.BOARD_HEIGHT//2 - 60))
                    
                    respawn_txt = font_medium.render("Respawning shortly...", True, (255, 255, 255))
                    screen.blit(respawn_txt, (config.BOARD_WIDTH//2 - respawn_txt.get_width()//2, config.BOARD_HEIGHT//2 + 10))

            pygame.display.flip()
            clock.tick(60)

    except KeyboardInterrupt:
        pass
    finally:
        running = False
        if sock:
            sock.close()
        pygame.quit()
        print("Disconnected.")
        sys.exit()

if __name__ == "__main__":
    main()
