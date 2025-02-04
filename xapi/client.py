import json
import socket
import logging
import time
import ssl
from threading import Thread

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('XTB_API')

class Client(object):
    def __init__(self):
        self.sock = None
        self.streaming_socket = None
        self.stream_session_id = None
        self.mutex = False
        self.symbol_array = []

    def connect(self, server='demo.xtb.com', port=5112):
        try:
            # Configuration spécifique pour le serveur démo avec l'IP directe
            server = 'xapi.xtb.com'  # Adresse IP du serveur démo XTB xapi.xtb.com
            port = 5124  # Port standard pour le démo 5124
            
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self.sock = context.wrap_socket(self.sock)
            self.sock.connect((server, port))
            self.sock.settimeout(30.0)
            logger.info('Connected to XTB demo server')
        except Exception as e:
            logger.error(f'Connection error: {str(e)}')
            raise

    def disconnect(self):
        if self.sock:
            self.sock.close()
        logger.info('Disconnected from XTB server')

    def login(self, user_id, password, app_name=''):
        login_cmd = {
            "command": "login",
            "arguments": {
                "userId": user_id,
                "password": password,
                "appName": "WebAPI"
            }
        }
        response = self._send_command(login_cmd)
        if response and 'status' in response and response['status']:
            self.stream_session_id = response.get('streamSessionId')
        return response

    def _send_command(self, dictionary):
        if not self.sock:
            raise ConnectionError("Not connected to XTB server")
        
        try:
            cmd = json.dumps(dictionary)
            cmd = cmd.encode('utf-8')
            self.sock.send(cmd + b'\n')
            return self._read_response()
        except Exception as e:
            logger.error(f'Send command error: {str(e)}')
            raise

    def _read_response(self):
        if not self.sock:
            raise ConnectionError("Not connected to XTB server")
        
        try:
            buffer = bytearray()
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                
                buffer.extend(chunk)
                
                if b'\n' in buffer:
                    try:
                        response = buffer.decode('utf-8').strip()
                        return json.loads(response)
                    except json.JSONDecodeError as e:
                        logger.error(f'JSON decode error: {str(e)}, Response: {response}')
                        raise
            
            if not buffer:
                raise ConnectionError("Empty response from server")
                
        except socket.timeout:
            logger.error('Socket timeout while reading response')
            raise
        except Exception as e:
            logger.error(f'Read response error: {str(e)}')
            raise

    def commandExecute(self, command, arguments=None):
        cmd = {
            "command": command,
        }
        if arguments:
            cmd["arguments"] = arguments
        return self._send_command(cmd)
