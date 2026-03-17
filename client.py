import socket
import json
import sys
import config
import msvcrt
import time

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((config.SERVER_HOST, config.SERVER_PORT))
        print("Connected to server!")
        print("This terminal is your controller.")
        print("Use WASD or Arrow Keys to move your snake on the main server screen.")
        print("Press 'Q' or 'ESC' to quit.")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    try:
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                action = None
                
                # Check for WASD
                if key in (b'w', b'W'):
                    action = {"dir": "UP"}
                elif key in (b's', b'S'):
                    action = {"dir": "DOWN"}
                elif key in (b'a', b'A'):
                    action = {"dir": "LEFT"}
                elif key in (b'd', b'D'):
                    action = {"dir": "RIGHT"}
                elif key in (b'q', b'Q', b'\x1b'): # Escape or Q
                    print("Exiting...")
                    break
                elif key == b'\xe0': # Extended key for arrows
                    key2 = msvcrt.getch()
                    if key2 == b'H': action = {"dir": "UP"}
                    elif key2 == b'P': action = {"dir": "DOWN"}
                    elif key2 == b'K': action = {"dir": "LEFT"}
                    elif key2 == b'M': action = {"dir": "RIGHT"}
                    
                if action:
                    try:
                        msg = json.dumps(action) + "\n"
                        sock.sendall(msg.encode('utf-8'))
                    except Exception:
                        print("Server disconnected.")
                        break
            
            # Small sleep to avoid eating 100% CPU
            time.sleep(0.01)

    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        print("Disconnected.")
        sys.exit()

if __name__ == "__main__":
    main()
