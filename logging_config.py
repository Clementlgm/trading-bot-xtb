import google.cloud.logging
import logging

def setup_logging():
    client = google.cloud.logging.Client()
    client.setup_logging(log_level=logging.INFO)
    
    # Configure handlers
    logging.getLogger().setLevel(logging.INFO)
    
    # Format for structured logging
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Add stream handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logging.getLogger().addHandler(stream_handler)
    
    return client
