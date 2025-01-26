from xapi.client import Client
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO)

def test_connection():
    try:
        load_dotenv()
        client = Client()
        client.connect()
        response = client.login(
            os.getenv('XTB_USER_ID'),
            os.getenv('XTB_PASSWORD')
        )
        print("Réponse de connexion:", response)
        
    except Exception as e:
        print(f"Erreur: {str(e)}")
    finally:
        if client:
            client.disconnect()

if __name__ == "__main__":
    test_connection()