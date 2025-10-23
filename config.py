import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    
    # Database configuration
    DB_USER = os.getenv('DB_USER', os.getenv('user'))
    DB_PASSWORD = os.getenv('DB_PASSWORD', os.getenv('password'))
    DB_HOST = os.getenv('DB_HOST', os.getenv('host'))
    DB_PORT = os.getenv('DB_PORT', os.getenv('port'))
    DB_NAME = os.getenv('DB_NAME', os.getenv('dbname'))
    