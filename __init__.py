def __init__(self, symbol='EURUSD', timeframe='1h'):
        load_dotenv()
        self.userId = os.getenv('XTB_USER_ID') 
        self.password = os.getenv('XTB_PASSWORD') 
        if not self.userId or not self.password:
            raise ValueError("XTB_USER_ID et XTB_PASSWORD doivent être définis dans .env")
        self.symbol = symbol
        self.timeframe = timeframe
        self.client = None
        self.streaming = None
        self.position_open = False
        self.current_order_id = None
        self.last_reconnect = time.time()
        self.reconnect_interval = 60
        self.min_volume = 0.001
        self.risk_percentage = 0.01
        self.active_positions = set()  # Ajout de l'attribut manquant
