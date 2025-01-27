import json
import logging
import websocket
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

    def connect(self, server='xapi.xtb.com', port=5124):
        try:
            logger.info("Connecting to XTB websocket...")
            # Utilisation de websocket au lieu de socket SSL
            self.sock = websocket.create_connection(
                "wss://ws.xtb.com/demo",
                sslopt={"cert_reqs": 0}
            )
            self.sock.settimeout(30.0)
            logger.info('Connected to XTB demo server')
            return True
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
            self.sock.send(cmd)
            return self._read_response()
        except Exception as e:
            logger.error(f'Send command error: {str(e)}')
            raise

    def _read_response(self):
        if not self.sock:
            raise ConnectionError("Not connected to XTB server")
        
        try:
            response = self.sock.recv()
            if response:
                return json.loads(response)
            raise ConnectionError("Empty response from server")
                
        except websocket.WebSocketTimeoutException:
            logger.error('WebSocket timeout while reading response')
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
