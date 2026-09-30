import main

if __name__ == '__main__':
    if not main.TOKEN or main.TOKEN == "your_token_here":
        print("Please set your DISCORD_TOKEN in the .env file!")
    else:
        bot = main.DestiFC()
        bot.run(main.TOKEN)
