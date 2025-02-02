def __init__(self, symbol='BITCOIN', timeframe='1m'):
    load_dotenv()  # Charge les variables d'environnement
    self.userId = os.getenv('XTB_USER_ID')
    self.password = os.getenv('XTB_PASSWORD')
    if not self.userId or not self.password:
        raise ValueError("XTB_USER_ID et XTB_PASSWORD doivent être définis dans .env")
