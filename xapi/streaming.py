import json
import socket
import logging
import ssl
from threading import Thread, Lock

class Streaming(object):
    def __init__(self, client):
        self.client = client
        self.sock = None
        self.stop = False
        self._lock = Lock()
        self.connected = False

    def connect(self):
        with self._lock:
            try:
                if self.connected:
                    return True
                    
                STREAM_PORT = 5125  # Pour compte démo, 5113 pour réel
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(10.0)  # Timeout de 10 secondes
                self.sock = ssl.wrap_socket(self.sock)
                self.sock.connect(('xapi.xtb.com', STREAM_PORT))
                self.connected = True
                logging.info('Streaming connected')
                return True
            except Exception as e:
                logging.error(f'Streaming connection error: {str(e)}')
                self.disconnect()
                return False

    def disconnect(self):
        with self._lock:
            try:
                if self.sock:
                    self.sock.close()
                self.sock = None
                self.stop = True
                self.connected = False
                logging.info('Streaming disconnected')
            except Exception as e:
                logging.error(f'Error during streaming disconnect: {str(e)}')

    def read_stream(self):
        while not self.stop:
            if not self.connected:
                time.sleep(1)
                continue
                
            try:
                data = ""
                while not self.stop:
                    try:
                        char = self.sock.recv(1).decode()
                        if char == '\n':
                            break
                        data += char
                    except socket.timeout:
                        continue
                    except Exception as e:
                        logging.error(f'Stream read error: {str(e)}')
                        break
                        
                if data:
                    try:
                        parsed = json.loads(data)
                        logging.debug(f'Stream data: {parsed}')
                        yield parsed
                    except json.JSONDecodeError as e:
                        logging.error(f'JSON parse error: {str(e)}')
                        
            except Exception as e:
                logging.error(f'Stream processing error: {str(e)}')
                self.disconnect()
                time.sleep(5)  # Attente avant tentative de reconnexion
                self.connect()
