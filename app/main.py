import asyncio
from ui.bot import start_bot
from jobs.db.init_db import init_db

def main():
    print("[DB INIT STARTED]")
    init_db()
    print("[DB INIT ENDED. STARTING BOT]")
    asyncio.run(start_bot())

if __name__ == "__main__":
    main()