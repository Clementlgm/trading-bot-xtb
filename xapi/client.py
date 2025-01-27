import json
import logging
import websocket
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
        self.is_connected = False

    def connect(self, server='xapi.xtb.com', port=5124):
        try:
            logger.info("Connecting to XTB websocket...")
            
            # Configuration du WebSocket
            websocket.enableTrace(True)  # Active le debug
            
            # Construction de l'URL correcte
            if port == 5124:  # DEMO
                url = "wss://ws.xtb.com/demo"
            else:  # REAL
                url = "wss://ws.xtb.com/real"
                
            # Configuration SSL personnalisée
            ssl_opts = {
                "cert_reqs": ssl.CERT_NONE,
                "check_hostname": False
            }
            
            # Création de la connexion
            self.sock = websocket.create_connection(
                url,
                sslopt=ssl_opts,
                header=["User-Agent: Python"],
                timeout=30
            )
            
            self.is_connected = True
            logger.info(f'Connected successfully to {url}')
            return True
            
        except websocket.WebSocketBadStatusException as e:
            logger.error(f'Bad status during connection: {str(e)}')
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f'Connection error: {str(e)}')
            self.is_connected = False
            return False

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
                self.is_connected = False
                logger.info('Disconnected from XTB server')
            except Exception as e:
                logger.error(f'Error during disconnection: {str(e)}')

    def login(self, user_id, password, app_name=''):
        if not self.is_connected:
            logger.error("Not connected to server. Please connect first.")
            return {"status": False, "errorCode": "NOT_CONNECTED"}

        login_cmd = {
            "command": "login",
            "arguments": {
                "userId": user_id,
                "password": password,
                "appName": app_name if app_name else "Python Trading Bot"
            }
        }
        
        try:
            response = self._send_command(login_cmd)
            if response and 'status' in response and response['status']:
                self.stream_session_id = response.get('streamSessionId')
                logger.info('Login successful')
                return response
            else:
                logger.error(f'Login failed: {response.get("errorCode", "Unknown error")}')
                return response
        except Exception as e:
            logger.error(f'Login error: {str(e)}')
            return {"status": False, "errorCode": str(e)}

    def _send_command(self, dictionary):
        if not self.sock:
            raise ConnectionError("Not connected to XTB server")
        
        try:
            cmd = json.dumps(dictionary)
            logger.debug(f"Sending command: {cmd}")
            self.sock.send(cmd)
            return self._read_response()
        except websocket.WebSocketConnectionClosedException:
            logger.error("Connection lost. Attempting to reconnect...")
            self.is_connected = False
            if self.connect():
                return self._send_command(dictionary)
            raise
        except Exception as e:
            logger.error(f'Send command error: {str(e)}')
            raise

    def _read_response(self):
        if not self.sock:
            raise ConnectionError("Not connected to XTB server")
        
        try:
            response = self.sock.recv()
            if response:
                parsed_response = json.loads(response)
                logger.debug(f"Received response: {parsed_response}")
                return parsed_response
            raise ConnectionError("Empty response from server")
                
        except websocket.WebSocketTimeoutException:
            logger.error('WebSocket timeout while reading response')
            raise
        except json.JSONDecodeError as e:
            logger.error(f'JSON decode error: {str(e)}')
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

    def ping(self):
        """Envoie un ping pour vérifier la connexion"""
        try:
            response = self.commandExecute('ping')
            return response and response.get('status', False)
        except:
            return False
