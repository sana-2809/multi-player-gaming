import socket
import threading
import json
import time
import random
import sys
import config

class GameState:
    def __init__(self):
        self.players = {}  # addr_str -> player_data
        self.food = self.spawn_food()
        self.lock = threading.Lock()
        self.colors = [
            (255, 50, 50),    # Red
            (50, 255, 50),    # Green
            (50, 100, 255),   # Blue
            (255, 255, 50),   # Yellow
            (255, 50, 255),   # Magenta
            (50, 255, 255),   # Cyan
            (255, 165, 0),    # Orange
        ]
        self.available_colors = self.colors.copy()
        random.shuffle(self.available_colors)

    def spawn_food(self):
        return [
            random.randint(0, config.GRID_WIDTH - 1),
            random.randint(0, config.GRID_HEIGHT - 1)
        ]

    def add_player(self, addr_str):
        with self.lock:
            start_x = random.randint(5, config.GRID_WIDTH - 6)
            start_y = random.randint(5, config.GRID_HEIGHT - 6)
            
            color = self.available_colors.pop() if self.available_colors else (255, 255, 255)
            
            self.players[addr_str] = {
                "body": [[start_x, start_y], [start_x - 1, start_y], [start_x - 2, start_y]],
                "dir": "RIGHT",
                "color": color,
                "alive": True,
                "score": 0,
                "death_timer": 0
            }
            print(f"Player {addr_str} added.")

    def remove_player(self, addr_str):
        with self.lock:
            if addr_str in self.players:
                color = self.players[addr_str]["color"]
                if color in self.colors and color not in self.available_colors:
                    self.available_colors.append(color)
                    
                del self.players[addr_str]
                print(f"Player {addr_str} removed.")

    def update_player_dir(self, addr_str, new_dir):
        with self.lock:
            if addr_str in self.players and self.players[addr_str]["alive"]:
                current_dir = self.players[addr_str]["dir"]
                opposites = {"UP": "DOWN", "DOWN": "UP", "LEFT": "RIGHT", "RIGHT": "LEFT"}
                if new_dir != opposites.get(current_dir, ""):
                    self.players[addr_str]["dir"] = new_dir

    def update_state(self):
        with self.lock:
            for addr_str, player in self.players.items():
                if not player["alive"]:
                    player["death_timer"] += 1
                    if player["death_timer"] > config.FPS * 2:
                        start_x = random.randint(5, config.GRID_WIDTH - 6)
                        start_y = random.randint(5, config.GRID_HEIGHT - 6)
                        player["body"] = [[start_x, start_y], [start_x - 1, start_y], [start_x - 2, start_y]]
                        player["dir"] = "RIGHT"
                        player["alive"] = True
                        player["score"] = 0
                        player["death_timer"] = 0
                    continue

                head = player["body"][0]
                new_head = list(head)

                if player["dir"] == "UP": new_head[1] -= 1
                elif player["dir"] == "DOWN": new_head[1] += 1
                elif player["dir"] == "LEFT": new_head[0] -= 1
                elif player["dir"] == "RIGHT": new_head[0] += 1

                if (new_head[0] < 0 or new_head[0] >= config.GRID_WIDTH or 
                    new_head[1] < 0 or new_head[1] >= config.GRID_HEIGHT):
                    player["alive"] = False
                    continue

                ate_food = False
                if new_head == self.food:
                    ate_food = True
                    player["score"] += 10
                    while True:
                        self.food = self.spawn_food()
                        conflict = False
                        for p in self.players.values():
                            if self.food in p["body"]:
                                conflict = True
                        if not conflict:
                            break

                player["body"].insert(0, new_head)
                if not ate_food:
                    player["body"].pop()

            for addr_str1, p1 in self.players.items():
                if not p1["alive"]: continue
                head1 = p1["body"][0]
                
                for addr_str2, p2 in self.players.items():
                    if not p2["alive"]: continue
                    
                    if addr_str1 == addr_str2:
                        if head1 in p1["body"][1:]:
                            p1["alive"] = False
                    else:
                        if head1 in p2["body"]:
                            p1["alive"] = False

state = GameState()
clients = {}
clients_lock = threading.Lock()

def remove_client(conn):
    with clients_lock:
        if conn in clients:
            addr_str = clients[conn]
            del clients[conn]
            try:
                conn.close()
            except:
                pass
            state.remove_player(addr_str)

def handle_client(conn, addr):
    addr_str = f"{addr[0]}:{addr[1]}"
    with clients_lock:
        clients[conn] = addr_str
    
    state.add_player(addr_str)

    try:
        buffer = ""
        while True:
            data = conn.recv(1024)
            if not data:
                break
            
            buffer += data.decode('utf-8')
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line:
                    try:
                        msg = json.loads(line)
                        if "dir" in msg:
                            state.update_player_dir(addr_str, msg["dir"])
                    except json.JSONDecodeError:
                        pass
    except socket.error:
        pass
    except Exception as e:
        print(f"Disconnect {addr_str}: {e}")
    finally:
        remove_client(conn)

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    
    try:
        server.bind(('0.0.0.0', config.SERVER_PORT))
        server.listen()
        print(f"Server listening on all interfaces (0.0.0.0) at port {config.SERVER_PORT} for controllers...")
        
        def accept_clients():
            while True:
                try:
                    conn, addr = server.accept()
                    threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
                except OSError:
                    break
                except Exception as e:
                    print(f"Accept error: {e}")
                    break
        
        threading.Thread(target=accept_clients, daemon=True).start()
        
        tick_time = 1.0 / config.FPS
        last_tick = time.time()

        while True:
            current_time = time.time()
            if current_time - last_tick >= tick_time:
                state.update_state()
                last_tick = current_time
                
                with state.lock:
                    state_data = {
                        "players": state.players,
                        "food": state.food
                    }
                try:
                    state_json = json.dumps(state_data) + "\n"
                    state_bytes = state_json.encode('utf-8')
                    
                    with clients_lock:
                        for conn in list(clients.keys()):
                            try:
                                conn.sendall(state_bytes)
                            except Exception:
                                pass
                except Exception as e:
                    print(f"State broadcast error: {e}")
            
            time.sleep(0.001)

    except KeyboardInterrupt:
        print("Server shutting down...")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server.close()
        sys.exit()

if __name__ == "__main__":
    main()
