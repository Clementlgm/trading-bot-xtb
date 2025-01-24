from xapi.client import Client
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO)

def test_connection():
    try:
        # Charger les variables d'environnement
        load_dotenv()
        
        # Créer une instance du client
        client = Client()
        
        # Se connecter
        client.connect()
        
        # Login
        response = client.login(
            os.getenv('XTB_USER_ID'),
            os.getenv('XTB_PASSWORD')
        )
        
        print("Réponse de connexion:", response)
        
        if response.get('status') == True:
            print("✅ Connexion réussie!")
            # Tester la récupération des données du compte
            account_response = client.commandExecute("getMarginLevel")
            print("Info compte:", account_response)
        else:
            print("❌ Échec de la connexion")
            
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
    finally:
        if client:
            client.disconnect()

if __name__ == "__main__":
    test_connection()
