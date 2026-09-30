import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import database

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class DestiFC(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=discord.Intents.all(),
            help_command=commands.DefaultHelpCommand()
        )

    async def setup_hook(self):
        await database.setup()
        import asyncio
        asyncio.create_task(database.preload_official_cards_cache())
        
        # Load cogs
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('__'):
                await self.load_extension(f'cogs.{filename[:-3]}')
        
        # Sync slash commands
        await self.tree.sync()

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        await self.change_presence(activity=discord.Game(name="FC Mobile 27"))

if __name__ == '__main__':
    if not TOKEN or TOKEN == "your_token_here":
        print("Please set your DISCORD_TOKEN in the .env file!")
    else:
        bot = DestiFC()
        bot.run(TOKEN)
