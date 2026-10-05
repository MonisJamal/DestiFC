import discord
from discord.ext import commands
from discord import app_commands
import database
from auth import is_team_admin_or_owner
import random
import time
import ai_engine

# --- Interactive Views for Skill Games ---

class PenaltyView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id

    async def handle_shot(self, interaction: discord.Interaction, direction: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your skill game!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        gk_dive = random.choice(["Left", "Middle", "Right"])
        
        if gk_dive == direction:
            await interaction.response.edit_message(
                content=f"🧤 **GK dived {gk_dive} and SAVED your shot to the {direction}!**\n❌ **Skill Game Failed!** You get 0 rewards. Try again when cooldown expires!",
                view=self
            )
        else:
            eco = await database.get_economy_config()
            vouchers = int(eco.get('penalty_reward_vouchers', 1))
            coins = int(eco.get('penalty_reward_coins', 3_000_000))
            if vouchers > 0: await database.add_vouchers(interaction.user.id, vouchers)
            if coins > 0: await database.add_coins(interaction.user.id, coins)
            
            rew_txt = []
            if vouchers > 0: rew_txt.append(f"**{vouchers}x Draft Voucher{'s' if vouchers > 1 else ''} 🎫**")
            if coins > 0: rew_txt.append(f"**+{coins:,} Coins 💰**")
            reward_str = " and ".join(rew_txt) if rew_txt else "Bragging rights!"

            await interaction.response.edit_message(
                content=f"⚽ **You shot {direction}, GK dived {gk_dive}... GOAL!**\n🎯 **Skill Game Passed!** You earned {reward_str}!",
                view=self
            )
            
    @discord.ui.button(label="Left", style=discord.ButtonStyle.primary, emoji="◀️")
    async def shoot_left(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_shot(interaction, "Left")

    @discord.ui.button(label="Middle", style=discord.ButtonStyle.primary, emoji="🔼")
    async def shoot_middle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_shot(interaction, "Middle")
        
    @discord.ui.button(label="Right", style=discord.ButtonStyle.primary, emoji="▶️")
    async def shoot_right(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_shot(interaction, "Right")


class FreeKickView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id

    async def handle_shot(self, interaction: discord.Interaction, technique: str):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your skill game!", ephemeral=True)

        for child in self.children:
            child.disabled = True

        # 70% success probability
        success = random.random() < 0.70
        if success:
            eco = await database.get_economy_config()
            vouchers = int(eco.get('freekick_reward_vouchers', 1))
            coins = int(eco.get('freekick_reward_coins', 4_000_000))
            if vouchers > 0: await database.add_vouchers(interaction.user.id, vouchers)
            if coins > 0: await database.add_coins(interaction.user.id, coins)
            
            rew_txt = []
            if vouchers > 0: rew_txt.append(f"**{vouchers}x Draft Voucher{'s' if vouchers > 1 else ''} 🎫**")
            if coins > 0: rew_txt.append(f"**+{coins:,} Coins 💰**")
            reward_str = " and ".join(rew_txt) if rew_txt else "Bragging rights!"

            msg = (
                f"🎯 **WHAT A STRIKE!** Your **{technique}** sailed right into the top corner off the crossbar!\n"
                f"🎉 **Challenge Passed!** You earned {reward_str}!"
            )
        else:
            block_type = random.choice(["smashed against the defensive wall", "was tipped over the bar by the keeper", "clipped the outside of the post"])
            msg = (
                f"❌ **Unlucky!** Your **{technique}** {block_type}!\n"
                f"Try again when the cooldown expires."
            )
        await interaction.response.edit_message(content=msg, view=self)

    @discord.ui.button(label="Top Corner Curl", style=discord.ButtonStyle.success, emoji="🎯")
    async def curl(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_shot(interaction, "Top Corner Curl")

    @discord.ui.button(label="Knuckleball Blast", style=discord.ButtonStyle.primary, emoji="🚀")
    async def knuckle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_shot(interaction, "Knuckleball Blast")

    @discord.ui.button(label="Low Driven Whipped", style=discord.ButtonStyle.secondary, emoji="⚡")
    async def low_driven(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_shot(interaction, "Low Driven Whipped")


class DribbleView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id

    async def handle_move(self, interaction: discord.Interaction, move: str):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your skill game!", ephemeral=True)

        for child in self.children:
            child.disabled = True

        # 65% success rate
        success = random.random() < 0.65
        if success:
            eco = await database.get_economy_config()
            vouchers = int(eco.get('dribble_reward_vouchers', 2))
            coins = int(eco.get('dribble_reward_coins', 5_000_000))
            if vouchers > 0: await database.add_vouchers(interaction.user.id, vouchers)
            if coins > 0: await database.add_coins(interaction.user.id, coins)
            
            rew_txt = []
            if vouchers > 0: rew_txt.append(f"**{vouchers}x Draft Voucher{'s' if vouchers > 1 else ''} 🎫**")
            if coins > 0: rew_txt.append(f"**+{coins:,} Coins 💰**")
            reward_str = " and ".join(rew_txt) if rew_txt else "Bragging rights!"

            msg = (
                f"🕺 **FILTHY SKILLS!** You pulled off a stunning **{move}**, sending two defenders sliding the wrong way!\n"
                f"🔥 **Gauntlet Cleared!** You earned {reward_str}!"
            )
        else:
            msg = (
                f"🛑 **Tackled!** The defender anticipated your **{move}** and intercepted the ball!\n"
                f"❌ **Gauntlet Failed!** Better luck next time."
            )
        await interaction.response.edit_message(content=msg, view=self)

    @discord.ui.button(label="Marseille Roulette", style=discord.ButtonStyle.primary, emoji="🔄")
    async def roulette(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, "Marseille Roulette")

    @discord.ui.button(label="Rainbow Flick", style=discord.ButtonStyle.success, emoji="🌈")
    async def rainbow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, "Rainbow Flick")

    @discord.ui.button(label="Stepover & Burst", style=discord.ButtonStyle.secondary, emoji="⚡")
    async def stepover(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_move(interaction, "Stepover & Burst")


class GKHeroView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id

    async def handle_dive(self, interaction: discord.Interaction, dive: str):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your skill game!", ephemeral=True)

        for child in self.children:
            child.disabled = True

        success = random.random() < 0.68
        if success:
            eco = await database.get_economy_config()
            vouchers = int(eco.get('gk_reward_vouchers', 1))
            coins = int(eco.get('gk_reward_coins', 4_000_000))
            if vouchers > 0: await database.add_vouchers(interaction.user.id, vouchers)
            if coins > 0: await database.add_coins(interaction.user.id, coins)
            
            rew_txt = []
            if vouchers > 0: rew_txt.append(f"**{vouchers}x Draft Voucher{'s' if vouchers > 1 else ''} 🎫**")
            if coins > 0: rew_txt.append(f"**+{coins:,} Coins 💰**")
            reward_str = " and ".join(rew_txt) if rew_txt else "Bragging rights!"

            msg = (
                f"🧤 **UNBELIEVABLE SAVE!** You pulled off a miraculous **{dive}** to deny a guaranteed goal!\n"
                f"👑 **Clean Sheet Kept!** You earned {reward_str}!"
            )
        else:
            msg = (
                f"⚽ **GOAL CONCEDED!** The striker hit it past your **{dive}** right into the side netting!\n"
                f"❌ **Save Failed!** Try again later."
            )
        await interaction.response.edit_message(content=msg, view=self)

    @discord.ui.button(label="Top Left Reflex", style=discord.ButtonStyle.primary, emoji="🧤")
    async def dive_tl(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_dive(interaction, "Top Left Reflex")

    @discord.ui.button(label="Rush & Smother", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def rush(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_dive(interaction, "Rush & Smother")

    @discord.ui.button(label="Bottom Corner Stretch", style=discord.ButtonStyle.primary, emoji="🧤")
    async def dive_br(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_dive(interaction, "Bottom Corner Stretch")


class VolleyView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id

    async def handle_strike(self, interaction: discord.Interaction, strike: str):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ This is not your skill game!", ephemeral=True)

        for child in self.children:
            child.disabled = True

        success = random.random() < 0.70
        if success:
            eco = await database.get_economy_config()
            vouchers = int(eco.get('volley_reward_vouchers', 1))
            coins = int(eco.get('volley_reward_coins', 4_000_000))
            if vouchers > 0: await database.add_vouchers(interaction.user.id, vouchers)
            if coins > 0: await database.add_coins(interaction.user.id, coins)
            
            rew_txt = []
            if vouchers > 0: rew_txt.append(f"**{vouchers}x Draft Voucher{'s' if vouchers > 1 else ''} 🎫**")
            if coins > 0: rew_txt.append(f"**+{coins:,} Coins 💰**")
            reward_str = " and ".join(rew_txt) if rew_txt else "Bragging rights!"

            msg = (
                f"🚀 **PUSKAS WORTHY!** You executed an exquisite **{strike}** on the full volley into the top netting!\n"
                f"🎯 **Challenge Completed!** You earned {reward_str}!"
            )
        else:
            msg = (
                f"💨 **Over the bar!** You miscued the **{strike}** into the stands!\n"
                f"❌ **Failed!** Come back when cooldown ends."
            )
        await interaction.response.edit_message(content=msg, view=self)

    @discord.ui.button(label="Acrobatic Bicycle Kick", style=discord.ButtonStyle.success, emoji="🚲")
    async def bicycle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_strike(interaction, "Acrobatic Bicycle Kick")

    @discord.ui.button(label="Bullet Power Header", style=discord.ButtonStyle.primary, emoji="💥")
    async def header(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_strike(interaction, "Bullet Power Header")

    @discord.ui.button(label="Scorpion Kick", style=discord.ButtonStyle.danger, emoji="🦂")
    async def scorpion(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_strike(interaction, "Scorpion Kick")


TRIVIA_QUESTIONS = [
    {
        "q": "Which country won the 2022 FIFA World Cup in Qatar?",
        "options": ["Argentina", "France", "Croatia", "Brazil"],
        "answer": "Argentina"
    },
    {
        "q": "Who has won the most Ballon d'Or awards in football history?",
        "options": ["Lionel Messi", "Cristiano Ronaldo", "Johan Cruyff", "Michel Platini"],
        "answer": "Lionel Messi"
    },
    {
        "q": "Which club has won the most UEFA Champions League titles?",
        "options": ["Real Madrid", "AC Milan", "Bayern Munich", "Liverpool"],
        "answer": "Real Madrid"
    },
    {
        "q": "Who scored the famous 'Hand of God' goal in the 1986 World Cup?",
        "options": ["Diego Maradona", "Pelé", "Zico", "Mario Kempes"],
        "answer": "Diego Maradona"
    },
    {
        "q": "Which player is known as 'El Fenomeno'?",
        "options": ["Ronaldo Nazário", "Cristiano Ronaldo", "Ronaldinho", "Romário"],
        "answer": "Ronaldo Nazário"
    },
    {
        "q": "Which manager achieved 'The Invincibles' Premier League season with Arsenal in 2003-04?",
        "options": ["Arsène Wenger", "Alex Ferguson", "José Mourinho", "Pep Guardiola"],
        "answer": "Arsène Wenger"
    },
    {
        "q": "Who scored the winning volley goal for Real Madrid in the 2002 UCL Final against Leverkusen?",
        "options": ["Zinedine Zidane", "Raúl", "Luís Figo", "Roberto Carlos"],
        "answer": "Zinedine Zidane"
    },
    {
        "q": "Which country won the UEFA Euro 2004 in one of football's biggest upsets?",
        "options": ["Greece", "Portugal", "Czech Republic", "Netherlands"],
        "answer": "Greece"
    },
    {
        "q": "Which legendary goalkeeper played 648 Serie A matches for Juventus?",
        "options": ["Gianluigi Buffon", "Dino Zoff", "Iker Casillas", "Manuel Neuer"],
        "answer": "Gianluigi Buffon"
    },
    {
        "q": "Who is the all-time top scorer in UEFA Champions League history?",
        "options": ["Cristiano Ronaldo", "Lionel Messi", "Robert Lewandowski", "Karim Benzema"],
        "answer": "Cristiano Ronaldo"
    }
]

class TriviaView(discord.ui.View):
    def __init__(self, user_id: int, question_data: dict):
        super().__init__(timeout=25)
        self.user_id = user_id
        self.question_data = question_data

        shuffled_options = list(question_data["options"])
        random.shuffle(shuffled_options)

        for opt in shuffled_options:
            btn = discord.ui.Button(label=opt, style=discord.ButtonStyle.secondary)
            btn.callback = self.make_callback(opt)
            self.add_item(btn)

    def make_callback(self, chosen: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ This is not your trivia game!", ephemeral=True)

            for child in self.children:
                child.disabled = True
                if child.label == self.question_data["answer"]:
                    child.style = discord.ButtonStyle.success
                elif child.label == chosen:
                    child.style = discord.ButtonStyle.danger

            correct = (chosen == self.question_data["answer"])
            if correct:
                eco = await database.get_economy_config()
                vouchers = int(eco.get('trivia_reward_vouchers', 1))
                coins = int(eco.get('trivia_reward_coins', 5_000_000))
                if vouchers > 0: await database.add_vouchers(interaction.user.id, vouchers)
                if coins > 0: await database.add_coins(interaction.user.id, coins)
                
                rew_txt = []
                if vouchers > 0: rew_txt.append(f"**{vouchers}x Draft Voucher{'s' if vouchers > 1 else ''} 🎫**")
                if coins > 0: rew_txt.append(f"**+{coins:,} Coins 💰**")
                reward_str = " and ".join(rew_txt) if rew_txt else "Bragging rights!"

                msg = f"🧠 **CORRECT!** The answer was **{self.question_data['answer']}**.\n🎯 **Quiz Passed!** You earned {reward_str}!"
            else:
                msg = f"❌ **WRONG!** You chose **{chosen}**, but the correct answer was **{self.question_data['answer']}**!\nBetter luck next time."

            await interaction.response.edit_message(content=msg, view=self)
        return callback


# --- Economy Cog ---

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="quest_daily", description="Claim your daily login Draft Vouchers & Coins")
    async def quest_daily(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        current_time = int(time.time())
        eco_cfg = await database.get_economy_config()
        cooldown = int(eco_cfg.get('daily_cooldown_hours', 24)) * 3600

        p = await database.get_db()
        last_daily = await p.fetchval('SELECT last_quest_daily FROM users WHERE user_id = $1', user_id) or 0

        if cooldown > 0 and (current_time - last_daily < cooldown):
            remaining = cooldown - (current_time - last_daily)
            hours, rem = divmod(remaining, 3600)
            mins, _ = divmod(rem, 60)
            return await interaction.followup.send(f"⏳ You already claimed your daily reward! Come back in **{int(hours)}h {int(mins)}m**.")

        daily_vouchers = int(eco_cfg.get('daily_vouchers', 2))
        min_coins = int(eco_cfg.get('daily_coins_min', 5_000_000))
        max_coins = int(eco_cfg.get('daily_coins_max', 20_000_000))
        daily_coins = random.randint(min(min_coins, max_coins), max(min_coins, max_coins)) if max_coins > 0 else 0

        await p.execute('UPDATE users SET vouchers = vouchers + $1, coins = coins + $2, last_quest_daily = $3 WHERE user_id = $4', daily_vouchers, daily_coins, current_time, user_id)

        await interaction.followup.send(f"🎁 **Daily Reward Claimed!** You received **{daily_vouchers}x Draft Vouchers 🎫** and **+{daily_coins:,} Coins 💰**!")

    @app_commands.command(name="quest_skill_game", description="Play a Penalty Shootout skill game for vouchers and coins")
    async def quest_skill_game(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        current_time = int(time.time())
        eco_cfg = await database.get_economy_config()
        cooldown = int(eco_cfg.get('penalty_cooldown_mins', 60)) * 60

        p = await database.get_db()
        last_skill = await p.fetchval('SELECT last_quest_skill FROM users WHERE user_id = $1', user_id) or 0

        if cooldown > 0 and (current_time - last_skill < cooldown):
            remaining = cooldown - (current_time - last_skill)
            mins, secs = divmod(remaining, 60)
            return await interaction.response.send_message(f"⏳ Penalty Shootout is on cooldown! Come back in **{int(mins)}m {int(secs)}s**.", ephemeral=True)

        await p.execute('UPDATE users SET last_quest_skill = $1 WHERE user_id = $2', current_time, user_id)

        view = PenaltyView(interaction.user.id)
        await interaction.response.send_message("🥅 **Penalty Shootout!**\nWhere are you going to shoot? Choose quickly!", view=view)

    @app_commands.command(name="quest_freekick", description="Take a high-stakes Free Kick past the wall and goalkeeper")
    async def quest_freekick(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        current_time = int(time.time())
        eco_cfg = await database.get_economy_config()
        cooldown = int(eco_cfg.get('freekick_cooldown_mins', 90)) * 60

        p = await database.get_db()
        last_fk = await p.fetchval('SELECT last_quest_freekick FROM users WHERE user_id = $1', user_id) or 0

        if cooldown > 0 and (current_time - last_fk < cooldown):
            remaining = cooldown - (current_time - last_fk)
            hours, rem = divmod(remaining, 3600)
            mins, _ = divmod(rem, 60)
            time_str = f"{int(hours)}h {int(mins)}m" if hours > 0 else f"{int(mins)}m"
            return await interaction.response.send_message(f"⏳ Free Kick Master is on cooldown! Come back in **{time_str}**.", ephemeral=True)

        await p.execute('UPDATE users SET last_quest_freekick = $1 WHERE user_id = $2', current_time, user_id)

        view = FreeKickView(interaction.user.id)
        await interaction.response.send_message("🎯 **Free Kick Master!**\nBall is placed 25 yards out. Choose your shooting technique:", view=view)

    @app_commands.command(name="quest_dribble", description="Take on defenders in the Dribbling Gauntlet")
    async def quest_dribble(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        current_time = int(time.time())
        eco_cfg = await database.get_economy_config()
        cooldown = int(eco_cfg.get('dribble_cooldown_mins', 120)) * 60

        p = await database.get_db()
        last_dr = await p.fetchval('SELECT last_quest_dribble FROM users WHERE user_id = $1', user_id) or 0

        if cooldown > 0 and (current_time - last_dr < cooldown):
            remaining = cooldown - (current_time - last_dr)
            hours, rem = divmod(remaining, 3600)
            mins, _ = divmod(rem, 60)
            return await interaction.response.send_message(f"⏳ Dribbling Gauntlet is on cooldown! Come back in **{int(hours)}h {int(mins)}m**.", ephemeral=True)

        await p.execute('UPDATE users SET last_quest_dribble = $1 WHERE user_id = $2', current_time, user_id)

        view = DribbleView(interaction.user.id)
        await interaction.response.send_message("⚡ **Dribbling Gauntlet!**\nTwo defenders are closing in on you! Pick your skill move to burst through:", view=view)

    @app_commands.command(name="quest_trivia", description="Test your Football IQ in a 4-choice trivia challenge")
    async def quest_trivia(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        current_time = int(time.time())
        eco_cfg = await database.get_economy_config()
        cooldown = int(eco_cfg.get('trivia_cooldown_mins', 60)) * 60

        p = await database.get_db()
        last_tr = await p.fetchval('SELECT last_quest_trivia FROM users WHERE user_id = $1', user_id) or 0

        if cooldown > 0 and (current_time - last_tr < cooldown):
            remaining = cooldown - (current_time - last_tr)
            mins, secs = divmod(remaining, 60)
            return await interaction.response.send_message(f"⏳ Football Trivia is on cooldown! Come back in **{int(mins)}m {int(secs)}s**.", ephemeral=True)

        await p.execute('UPDATE users SET last_quest_trivia = $1 WHERE user_id = $2', current_time, user_id)

        q_data = random.choice(TRIVIA_QUESTIONS)
        view = TriviaView(interaction.user.id, q_data)
        await interaction.response.send_message(f"🧠 **Football IQ Trivia Challenge!**\n\n**Question:** {q_data['q']}\n*You have 25 seconds to answer:*", view=view)

    @app_commands.command(name="quest_gk", description="Play as the Goalkeeper and make a match-winning 1v1 save")
    async def quest_gk(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        current_time = int(time.time())
        eco_cfg = await database.get_economy_config()
        cooldown = int(eco_cfg.get('gk_cooldown_mins', 90)) * 60

        p = await database.get_db()
        last_gk = await p.fetchval('SELECT last_quest_gk FROM users WHERE user_id = $1', user_id) or 0

        if cooldown > 0 and (current_time - last_gk < cooldown):
            remaining = cooldown - (current_time - last_gk)
            hours, rem = divmod(remaining, 3600)
            mins, _ = divmod(rem, 60)
            time_str = f"{int(hours)}h {int(mins)}m" if hours > 0 else f"{int(mins)}m"
            return await interaction.response.send_message(f"⏳ Goalkeeper Hero is on cooldown! Come back in **{time_str}**.", ephemeral=True)

        await p.execute('UPDATE users SET last_quest_gk = $1 WHERE user_id = $2', current_time, user_id)

        view = GKHeroView(interaction.user.id)
        await interaction.response.send_message("🧤 **Goalkeeper Hero!**\nA striker is bearing down 1v1 on goal in the 90th minute! Make your move:", view=view)

    @app_commands.command(name="quest_volley", description="Finish a whipped cross with a spectacular volley")
    async def quest_volley(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        current_time = int(time.time())
        eco_cfg = await database.get_economy_config()
        cooldown = int(eco_cfg.get('volley_cooldown_mins', 90)) * 60

        p = await database.get_db()
        last_vl = await p.fetchval('SELECT last_quest_volley FROM users WHERE user_id = $1', user_id) or 0

        if cooldown > 0 and (current_time - last_vl < cooldown):
            remaining = cooldown - (current_time - last_vl)
            hours, rem = divmod(remaining, 3600)
            mins, _ = divmod(rem, 60)
            time_str = f"{int(hours)}h {int(mins)}m" if hours > 0 else f"{int(mins)}m"
            return await interaction.response.send_message(f"⏳ Cross & Volley is on cooldown! Come back in **{time_str}**.", ephemeral=True)

        await p.execute('UPDATE users SET last_quest_volley = $1 WHERE user_id = $2', current_time, user_id)

        view = VolleyView(interaction.user.id)
        await interaction.response.send_message("🎯 **Cross & Volley Challenge!**\nA pinpoint cross is whipped towards the back post! Choose your finish:", view=view)

    @app_commands.command(name="quest_h2h", description="Play a quick Head to Head match against AI")
    async def quest_h2h(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        current_time = int(time.time())
        eco_cfg = await database.get_economy_config()
        cooldown = int(eco_cfg.get('h2h_ai_cooldown_mins', 120)) * 60

        p = await database.get_db()
        last_h2h = await p.fetchval('SELECT last_quest_h2h FROM users WHERE user_id = $1', user_id) or 0

        if cooldown > 0 and (current_time - last_h2h < cooldown):
            remaining = cooldown - (current_time - last_h2h)
            hours, rem = divmod(remaining, 3600)
            mins, _ = divmod(rem, 60)
            return await interaction.response.send_message(f"⏳ AI H2H match is on cooldown! Come back in **{int(hours)}h {int(mins)}m**.", ephemeral=True)

        await interaction.response.defer()

        await p.execute('UPDATE users SET last_quest_h2h = $1 WHERE user_id = $2', current_time, user_id)

        is_win = random.random() < 0.50
        user_name = interaction.user.display_name
        score_str = "2 - 1" if is_win else "1 - 2"
        
        prompt = (
            f"Match: {user_name} vs AI FC\n"
            f"Score: {score_str}\n"
            f"Outcome: {'Victory for ' + user_name if is_win else 'Loss for ' + user_name}\n"
            f"Write a 1-sentence dramatic summary of how the match ended (mention a winning goal or defensive stop). Bold {user_name}."
        )
        messages = [
            {"role": "system", "content": "You are a witty, fast-paced football commentator. Output exactly 1 punchy sentence."},
            {"role": "user", "content": prompt}
        ]
        
        recap = None
        try:
            recap = await ai_engine._call_ai_stream(messages, max_tokens=70, temperature=0.8, timeout_sec=6.0)
        except Exception:
            pass

        if is_win:
            vouchers = int(eco_cfg.get('h2h_ai_reward_vouchers', 2))
            coins = int(eco_cfg.get('h2h_ai_reward_coins', 10_000_000))
            if vouchers > 0: await database.add_vouchers(interaction.user.id, vouchers)
            if coins > 0: await database.add_coins(interaction.user.id, coins)
            
            rew_txt = []
            if vouchers > 0: rew_txt.append(f"**{vouchers}x Draft Voucher{'s' if vouchers > 1 else ''} 🎫**")
            if coins > 0: rew_txt.append(f"**+{coins:,} Coins 💰**")
            reward_str = " and ".join(rew_txt) if rew_txt else "Bragging rights!"

            msg = f"⚔️ **H2H Victory!** You beat the AI `{score_str}` and earned {reward_str}!"
            if recap: msg += f"\n\n🎙️ *\"{recap}\"*"
            await interaction.followup.send(msg)
        else:
            msg = f"💀 **H2H Defeat!** The AI edged you `{score_str}`. Better luck next time!"
            if recap: msg += f"\n\n🎙️ *\"{recap}\"*"
            await interaction.followup.send(msg)

    @app_commands.command(name="quests", description="View all available skill games & quests to earn rewards")
    async def quests_list(self, interaction: discord.Interaction):
        eco = await database.get_economy_config()
        embed = discord.Embed(
            title="📜 DestiFC Quests & Skill Games", 
            description="Play interactive mini-games and complete quests to earn **Draft Vouchers 🎫** and **Coins 💰**!",
            color=0xd946ef
        )
        
        def fmt_mins(m):
            if m <= 0: return "Instant"
            if m < 60: return f"{m}m"
            return f"{m//60}h" if m % 60 == 0 else f"{m/60:.1f}h"

        embed.add_field(
            name="🎁 `/quest_daily`", 
            value=f"**Reward:** {eco.get('daily_vouchers', 2)}x Vouchers 🎫 + {eco.get('daily_coins_min', 5_000_000):,} - {eco.get('daily_coins_max', 20_000_000):,} Coins 💰\n**Cooldown:** {eco.get('daily_cooldown_hours', 24)}h\nGuaranteed login reward every single day.", 
            inline=False
        )
        embed.add_field(
            name="⚡ `/quest_dribble`", 
            value=f"**Reward:** {eco.get('dribble_reward_vouchers', 2)}x Vouchers 🎫 + {eco.get('dribble_reward_coins', 5_000_000):,} Coins 💰\n**Cooldown:** {fmt_mins(eco.get('dribble_cooldown_mins', 120))}\nDribbling Gauntlet — Beat defenders with skill moves.", 
            inline=False
        )
        embed.add_field(
            name="⚔️ `/quest_h2h`", 
            value=f"**Reward:** {eco.get('h2h_ai_reward_vouchers', 2)}x Vouchers 🎫 + {eco.get('h2h_ai_reward_coins', 10_000_000):,} Coins 💰\n**Cooldown:** {fmt_mins(eco.get('h2h_ai_cooldown_mins', 120))}\nHead-to-Head match against dynamic AI.", 
            inline=False
        )
        embed.add_field(
            name="🥅 `/quest_skill_game`", 
            value=f"**Reward:** {eco.get('penalty_reward_vouchers', 1)}x Voucher 🎫 + {eco.get('penalty_reward_coins', 3_000_000):,} Coins 💰\n**Cooldown:** {fmt_mins(eco.get('penalty_cooldown_mins', 60))}\nPenalty Shootout — Pick your corner and score.", 
            inline=False
        )
        embed.add_field(
            name="🎯 `/quest_freekick`", 
            value=f"**Reward:** {eco.get('freekick_reward_vouchers', 1)}x Voucher 🎫 + {eco.get('freekick_reward_coins', 4_000_000):,} Coins 💰\n**Cooldown:** {fmt_mins(eco.get('freekick_cooldown_mins', 90))}\nFree Kick Master — Top corner curl or knuckleball.", 
            inline=False
        )
        embed.add_field(
            name="🧠 `/quest_trivia`", 
            value=f"**Reward:** {eco.get('trivia_reward_vouchers', 1)}x Voucher 🎫 + {eco.get('trivia_reward_coins', 5_000_000):,} Coins 💰\n**Cooldown:** {fmt_mins(eco.get('trivia_cooldown_mins', 60))}\nFootball IQ Quiz — 4-choice trivia within 25 seconds.", 
            inline=False
        )
        embed.add_field(
            name="🧤 `/quest_gk`", 
            value=f"**Reward:** {eco.get('gk_reward_vouchers', 1)}x Voucher 🎫 + {eco.get('gk_reward_coins', 4_000_000):,} Coins 💰\n**Cooldown:** {fmt_mins(eco.get('gk_cooldown_mins', 90))}\nGoalkeeper Hero — Make a 1v1 match-saving dive.", 
            inline=False
        )
        embed.add_field(
            name="🚀 `/quest_volley`", 
            value=f"**Reward:** {eco.get('volley_reward_vouchers', 1)}x Voucher 🎫 + {eco.get('volley_reward_coins', 4_000_000):,} Coins 💰\n**Cooldown:** {fmt_mins(eco.get('volley_cooldown_mins', 90))}\nCross & Volley — Bicycle kicks, volleys & bullet headers.", 
            inline=False
        )
        
        embed.set_footer(text="Play quests regularly to maximize your rewards!")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="starterpack", description="Claim your one-time starter pack!")
    async def starterpack(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user = await database.get_user(interaction.user.id)
        if user.get("starter_claimed", 0) == 1:
            return await interaction.followup.send("❌ You have already claimed your starter pack!")
            
        import renderz_api
        eco_cfg = await database.get_economy_config()
        st_coins = eco_cfg.get('starter_coins', 50_000_000)
        st_vouchers = eco_cfg.get('starter_vouchers', 10)

        await database.set_starter_claimed(interaction.user.id)
        await database.add_coins(interaction.user.id, st_coins)
        await database.add_vouchers(interaction.user.id, st_vouchers)
        
        page = random.randint(1, 5)
        offset = (page - 1) * 15
        players = renderz_api.query_players_by_program("", size=15, from_offset=offset, min_rating=100, max_rating=110)
        
        if not players or len(players) < 11:
            players = renderz_api.query_players_by_program("", size=11, from_offset=0, min_rating=90, max_rating=115)
            
        given_players = []
        for p in players[:11]:
            await database.add_player_to_inventory(interaction.user.id, p)
            name = p.get('cardName') or p.get('lastName', 'Unknown')
            given_players.append(f"**{name}** ({p.get('rating', '?')})")
            
        from cogs.market import format_price_short
        desc = f"💰 **+{st_coins:,} Coins ({format_price_short(st_coins)})**\n🎫 **+{st_vouchers}x Draft Vouchers**\n\n**Your Starter Players:**\n" + "\n".join(given_players)
        embed = discord.Embed(title="🎉 Starter Pack Claimed!", description=desc, color=discord.Color.green())
        embed.set_footer(text="Use /squad autofill to equip your new players!")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="work", description="Work a football management shift to earn coins!")
    async def work_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        eco_cfg = await database.get_economy_config()
        cooldown_mins = eco_cfg.get('work_cooldown_mins', 30)
        cooldown_secs = cooldown_mins * 60

        p = await database.get_db()
        last_work = await p.fetchval('SELECT last_work FROM users WHERE user_id = $1', user_id) or 0
        now_ts = int(time.time())

        if last_work and (now_ts - last_work < cooldown_secs):
            rem = cooldown_secs - (now_ts - last_work)
            mins, secs = divmod(rem, 60)
            return await interaction.followup.send(f"⏳ Your shift is on break! You can work again in **{int(mins)}m {int(secs)}s**.")

        min_w = eco_cfg.get('work_coins_min', 2_000_000)
        max_w = eco_cfg.get('work_coins_max', 10_000_000)
        earned = random.randint(min_w, max_w)

        await p.execute('UPDATE users SET coins = COALESCE(coins, 0) + $1, last_work = $2 WHERE user_id = $3', earned, now_ts, user_id)

        jobs = [
            ("Scouting Young Talents", "🔍"),
            ("Analyzing Match Film", "📹"),
            ("Organizing Training Drills", "⚽"),
            ("Negotiating Sponsorship Deals", "💼"),
            ("Managing Team Press Conference", "🎙️"),
            ("Upgrading Training Facilities", "🏟️")
        ]
        job_name, job_icon = random.choice(jobs)

        embed = discord.Embed(
            title=f"{job_icon} Shift Complete: {job_name}",
            description=f"You completed your football duties and earned **🪙 {earned:,} Coins**!",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"DestiFC Economy • Shift cooldown: {cooldown_mins} minutes")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="balance", description="Check your or another user's balance")
    @app_commands.describe(user="User whose balance you want to check (leave empty for yours)")
    async def balance(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        target = user or interaction.user
        
        # Privacy Check
        if target.id != interaction.user.id and not await is_team_admin_or_owner(self.bot, interaction.user):
            if await database.is_profile_private(target.id):
                return await interaction.followup.send(f"🔒 **{target.display_name}** has set their profile to **Private**.", ephemeral=True)
                
        user_data = await database.get_user(target.id)
        
        embed = discord.Embed(
            title=f"🏦 {target.display_name}'s Balance",
            color=discord.Color.blue()
        )
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        embed.add_field(name="Coins 🪙", value=f"**{user_data.get('coins', 0):,}**", inline=True)
        embed.add_field(name="Draft Vouchers 🎫", value=f"**{user_data.get('vouchers', 0):,}**", inline=True)
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="bal", description="Check your or another user's balance (shortcut)")
    @app_commands.describe(user="User whose balance you want to check (leave empty for yours)")
    async def bal(self, interaction: discord.Interaction, user: discord.Member = None):
        await self.balance.callback(self, interaction, user)

    @app_commands.command(name="privacy", description="Toggle whether other users can view your balance and inventory")
    async def privacy(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_state = await database.toggle_privacy(interaction.user.id)
        if new_state == 1:
            await interaction.followup.send("🔒 Your profile & inventory are now **Private**! Other players cannot view your balance or club.", ephemeral=True)
        else:
            await interaction.followup.send("🔓 Your profile & inventory are now **Public**! Other players can view your stats.", ephemeral=True)

    @app_commands.command(name="give", description="[Team Admin Only] Give currency to yourself or a user")
    @app_commands.choices(item=[
        app_commands.Choice(name="Coins", value="coins"),
        app_commands.Choice(name="Draft Vouchers", value="vouchers")
    ])
    async def give(self, interaction: discord.Interaction, item: str, amount: int, member: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        if not await is_team_admin_or_owner(self.bot, interaction.user):
            await interaction.followup.send("❌ **Access Denied:** This command is strictly restricted to members of the Discord Developer Team.", ephemeral=True)
            return
            
        target = member or interaction.user
        
        if item == "coins":
            await database.add_coins(target.id, amount)
        elif item == "vouchers":
            await database.add_vouchers(target.id, amount)
            
        await interaction.followup.send(f"👑 Team Admin Command: Gave **{amount:,} {item}** to {target.mention}!", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            hours, remainder = divmod(int(error.retry_after), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
            msg = f"⏳ **Cooldown!** You must wait **{time_str}** before doing this quest again."
        else:
            msg = f"❌ An error occurred: {error}"
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    @app_commands.command(name="daily", description="Claim your massive daily reward (Coins, Vouchers & chance at a Walkout)!")
    async def daily_reward(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        
        # Check cooldown & streak calculation
        p = await database.get_db()
        row = await p.fetchrow('SELECT last_daily, daily_streak FROM users WHERE user_id = $1', user_id)
        last_daily = row['last_daily'] if row and row['last_daily'] else 0
        current_streak = row['daily_streak'] if row and row['daily_streak'] else 0
                
        current_time = int(time.time())
        cooldown = 86400  # 24 hours
        if last_daily:
            time_diff = current_time - last_daily
            if time_diff < cooldown:
                remaining = cooldown - time_diff
                hours, rem = divmod(remaining, 3600)
                mins, secs = divmod(rem, 60)
                return await interaction.followup.send(f"⏳ You already claimed your daily reward! Come back in **{int(hours)}h {int(mins)}m**.")
            elif time_diff <= (cooldown * 2):
                # Within 48 hours -> streak increments!
                new_streak = (current_streak % 7) + 1
            else:
                # Missed more than 48 hours -> reset streak
                new_streak = 1
        else:
            new_streak = 1

        # 7-Day Tiered Streak Table
        STREAK_REWARDS = {
            1: {"coins": 5_000_000, "vouchers": 2, "gems": 10, "walkout": False},
            2: {"coins": 10_000_000, "vouchers": 3, "gems": 25, "walkout": False},
            3: {"coins": 15_000_000, "vouchers": 5, "gems": 50, "walkout": False},
            4: {"coins": 20_000_000, "vouchers": 7, "gems": 75, "walkout": False},
            5: {"coins": 30_000_000, "vouchers": 10, "gems": 100, "walkout": False},
            6: {"coins": 40_000_000, "vouchers": 15, "gems": 150, "walkout": False},
            7: {"coins": 60_000_000, "vouchers": 25, "gems": 300, "walkout": True},
        }

        tier = STREAK_REWARDS.get(new_streak, STREAK_REWARDS[1])
        coins_won = tier["coins"]
        vouchers_won = tier["vouchers"]
        gems_won = tier["gems"]
        guaranteed_walkout = tier["walkout"]

        await p.execute('''
            INSERT INTO users (user_id, coins, vouchers, gems, last_daily, daily_streak)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id) DO UPDATE SET
                coins = COALESCE(users.coins, 0) + $2,
                vouchers = COALESCE(users.vouchers, 0) + $3,
                gems = COALESCE(users.gems, 0) + $4,
                last_daily = $5,
                daily_streak = $6
        ''', user_id, coins_won, vouchers_won, gems_won, current_time, new_streak)
        
        # Invalidate cached user record
        database._USER_CACHE.pop(user_id, None)

        # Build visual progress bar
        bar = " ".join(["🟩" if i <= new_streak else "⬜" for i in range(1, 8)])
        streak_header = f"🔥 **Daily Streak: Day {new_streak} / 7**\n{bar}"
        if new_streak == 7:
            streak_header += "\n🏆 **MAX STREAK REACHED! MEGA REWARD ACTIVATED!**"

        desc = (
            f"{streak_header}\n\n"
            f"🪙 **Coins:** `+{coins_won:,}`\n"
            f"🎟️ **Draft Vouchers:** `+{vouchers_won}`\n"
            f"💎 **Gems:** `+{gems_won}`"
        )
        embed = discord.Embed(title="🎁 Daily Reward Claimed!", description=desc, color=discord.Color.gold())
        
        # Walkout card (guaranteed on Day 7, or 15% chance on other days)
        lucky_player = None
        if guaranteed_walkout or random.random() < 0.15:
            min_r = 120 if guaranteed_walkout else 118
            lucky_pool = await database.get_official_cards_by_rating(min_r, 122, 50)
            if lucky_pool:
                lucky_player = random.choice(lucky_pool)

        if lucky_player:
            await database.add_player_to_inventory(user_id, lucky_player)
            name = lucky_player.get('cardName', lucky_player.get('lastName', 'Unknown'))
            ovr = lucky_player.get('rating', '??')
            badge = "🌟 **DAY 7 WALKOUT SPECIAL!**" if guaranteed_walkout else "🎉 **JACKPOT WALKOUT!**"
            embed.description += f"\n\n{badge}\nYou also pulled a **{ovr} {name}** into your club!"
            img_url = lucky_player.get('images', {}).get('playerCardImage') or lucky_player.get('images', {}).get('playerImage')
            if img_url:
                embed.set_thumbnail(url=img_url)
        
        try:
            from cogs.season import add_season_xp
            await add_season_xp(user_id, 200 + (new_streak * 50))
        except Exception:
            pass
                
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
