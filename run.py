import asyncio
from client.bot import main as client_bot
from admin.bot import main as admin_bot

async def run_bots():
    await asyncio.gather(client_bot(), admin_bot())

if __name__ == "__main__":
    asyncio.run(run_bots())
