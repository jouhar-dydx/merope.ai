import logging
import os

def get_logger(name, log_file="app.log"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(file_handler)
    logger.addHandler(logging.StreamHandler())

    return logger
