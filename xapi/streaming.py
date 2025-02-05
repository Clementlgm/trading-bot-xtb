import json
import socket
import logging
import ssl
from threading import Thread

class Streaming(object):
    def __init__(self, client):
        self.client = client
        self.sock = None
        self.stop = False

    def connect(self):
        #STREAM_PORT = 5113  # Pour compte démo, 5125 pour réel
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock = ssl.wrap_socket(self.sock)
        self.sock.connect(('xapi.xtb.com', 5125))
        logging.info('Streaming connected')

    def disconnect(self):
        if self.sock:
            self.sock.close()
        self.stop = True
        logging.info('Streaming disconnected')

    def read_stream(self):
        while not self.stop:
            try:
                data = ""
                while True:
                    char = self.sock.recv(1).decode()
                    if char == '\n':
                        break
                    data += char
                if data:
                    logging.debug(data)
                    yield json.loads(data)
            except Exception as e:
                logging.error(f'Streaming error: {str(e)}')
                break
