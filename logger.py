import logging

# Suppress overly detailed Pyrogram logs
logging.getLogger("pyrogram").setLevel(logging.WARNING)

# Main logger config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [TojiFushiguro] >> %(levelname)s << %(message)s",
    datefmt="[%d/%m/%Y %H:%M:%S]",
    handlers=[
        logging.FileHandler("tojifushiguro.log"),  # Save logs to file
        logging.StreamHandler()                 # Also show in console
    ],
)

# Example usage
logger = logging.getLogger("tojifushiguro")

logger.info("TojiFushiguro logging initialized successfully.")