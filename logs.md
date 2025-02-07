# Guide des Logs du Trading Bot

## Logs de Connexion XTB
```log
INFO:root:🔄 Tentative de connexion à XTB - UserID: xxxxx
INFO:XTB_API:Connected to XTB demo server
INFO:root:✅ Connecté à XTB avec succès
ERROR:root:❌ Échec de la connexion initiale
ERROR:root:❌ Erreur de connexion: [détails erreur]
```

## Logs du Streaming
```log
INFO:root:Streaming connected
INFO:root:Streaming disconnected
ERROR:root:Stream read error: [détails erreur]
ERROR:root:Streaming error: [détails erreur]
ERROR:root:Stream processing error: [détails erreur]
```

## Logs Trading
```log
INFO:trading_bot:===== État du marché =====
Symbole: BITCOIN
Dernier prix: 123456.78
SMA20: 123400.00
SMA50: 123450.00
RSI: 65.43
Position ouverte: false

INFO:trading_bot:🔵 Signal d'achat détecté!
INFO:trading_bot:🔴 Signal de vente détecté!
INFO:trading_bot:⚪ Aucun signal généré - Conditions non remplies

INFO:trading_bot:===== Exécution du trade =====
Signal: BUY/SELL
Prix d'entrée: 123456.78
Stop Loss: 123400.00
Take Profit: 123500.00
Volume: 0.01

INFO:trading_bot:✅ Trade exécuté avec succès
ERROR:trading_bot:❌ Échec de l'exécution du trade
```

## Logs de Démarrage/Arrêt
```log
[xxxx-xx-xx xx:xx:xx +0000] [1] [INFO] Starting gunicorn 23.0.0
[xxxx-xx-xx xx:xx:xx +0000] [1] [INFO] Listening at: http://0.0.0.0:8080 (1)
[xxxx-xx-xx xx:xx:xx +0000] [1] [INFO] Using worker: gthread
[xxxx-xx-xx xx:xx:xx +0000] [2] [INFO] Booting worker with pid: 2
[xxxx-xx-xx xx:xx:xx +0000] [1] [INFO] Handling signal: term
[xxxx-xx-xx xx:xx:xx +0000] [2] [INFO] Worker exiting (pid: 2)
[xxxx-xx-xx xx:xx:xx +0000] [1] [INFO] Shutting down: Master
```

## Logs d'Initialisation
```log
INFO:trading_bot:Initialisation du bot...
INFO:trading_bot:Bot initialisé avec succès
INFO:trading_bot:Thread de trading démarré
ERROR:trading_bot:Échec de l'initialisation du bot
ERROR:trading_bot:Identifiants XTB manquants
```

## Logs de Gestion des Connexions
```log
INFO:trading_bot:Renouvellement préventif de la connexion
INFO:trading_bot:Ping échoué, reconnexion nécessaire
INFO:trading_bot:Bot réinitialisé avec succès
ERROR:trading_bot:Échec de la réinitialisation
```

## Logs Cloud Run
```log
Default STARTUP TCP probe succeeded after 1 attempt for container "placeholder-1" on port 8080
Shutting down user disabled instance
Ready condition status changed to True for Revision trading-bot-xxxxx
Ready condition status changed to True for Service trading-bot
```

## Gestion des Erreurs
```log
ERROR:trading_bot:❌ Erreur dans run_trading: [détails erreur]
ERROR:trading_bot:❌ Erreur lors de la déconnexion: [détails erreur]
ERROR:trading_bot:❌ Erreur dans /status: [détails erreur]
ERROR:trading_bot:❌ Erreur d'initialisation: [détails erreur]
```

## Messages de Status HTTP
```log
{"status": "connected", "bot_initialized": true, "is_running": true}
{"status": "disconnected", "error": "Non connecté à XTB"}
{"error": "Rate limit exceeded", "retry_after": 30}
```

## Logs Performance
```log
"latency": "0.152281005s"
"requestSize": "1128"
"responseSize": "450"
```

## Format des Logs
Chaque entrée de log contient généralement :
- Timestamp
- Niveau de log (INFO/ERROR/WARNING)
- Service/Module source
- Message détaillé
- Identifiants de trace/span pour Cloud Run
- Labels pour le monitoring

## Fichier : logs.md
