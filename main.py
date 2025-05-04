from src.main import run_session
from src.utils.utils import ConnectionStatus
from src.utils.config import Config
import asyncio

if __name__ == "__main__":
    try:
        connection_status = ConnectionStatus(Config.load_from_file())
        asyncio.run(run_session(connection_status))
    except KeyboardInterrupt:
        print("Terminated by user")
