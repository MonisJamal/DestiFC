import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import time
import json

import database
import ai_engine
from maps import TACTICS

# Centralized tracking to ensure only 1 active H2H match, draft battle, or challenge at a time per user
ACTIVE_MATCH_USERS = database.ACTIVE_MATCH_USERS

def format_match_player_name(p_name: str) -> str:
    if not p_name:
        return ""
    if "blank" in str(p_name).strip().lower():
        return "~𝔹𝕃𝔸ℕ𝕂"
    return str(p_name)

def generate_dynamic_goal_commentary(
    time_label: str,
    scorer: str,
    scorer_disp: str,
    pos: str,
    ptype: str,
    assister: str | None,
    assister_disp: str,
    team_name: str,
    opponent_name: str,
    score_for_team: int,
    score_for_opp: int,
    is_stoppage: bool,
    player_goals_today: int
) -> str:
    assist_phrases = [
        f" assisted by **{assister_disp}**",
        f" after a glorious through-ball from **{assister_disp}**",
        f" served on a silver platter by **{assister_disp}**",
        f" orchestrated by a pinpoint pass from **{assister_disp}**",
        f" courtesy of a sublime delivery from **{assister_disp}**",
        f" courtesy of a delicious cross by **{assister_disp}**",
    ]
    assist_comm = random.choice(assist_phrases) if assister_disp else ""
    s_lower = str(scorer).lower()

    # 1. Custom Lore Cards
    if 'blank' in s_lower:
        return f"🌌 **{time_label} GOAL! THE ENIGMA AWAKENS!** **~𝔹𝕃𝔸ℕ𝕂** (`{pos}`){assist_comm} ghosts past the entire defense with impossible agility and finishes into the bottom corner for **{team_name}**! 🔮✨"
    if 'akari' in s_lower or 'watanabe' in s_lower:
        return f"✨ **{time_label} GOAL! MAGICAL MAESTRO!** Akari **Watanabe** (`{pos}`){assist_comm} dances through the backline and chips the keeper with sublime flair for **{team_name}**! 🌸⚡"

    # 2. Hat-Trick milestone
    if player_goals_today >= 3:
        return random.choice([
            f"🎩🔥 **{time_label} GOAL! HAT-TRICK HERO! TAKE A BOW!** {scorer_disp} (`{pos}`){assist_comm} seals a breathtaking treble for **{team_name}**! The match ball is coming home with him! ⚽⚽⚽",
            f"🌟🎩 **{time_label} GOAL! SENSATIONAL HAT-TRICK!** A majestic three-goal masterclass from {scorer_disp} (`{pos}`){assist_comm}! Searing brilliance putting **{team_name}** in dreamland! ⚽⚽⚽",
            f"👑⚽ **{time_label} GOAL! THIRD OF THE MATCH!** What a day for {scorer_disp} (`{pos}`){assist_comm}! Completely unstoppable as he bags his hat-trick for **{team_name}**! 🔥🎩",
        ])

    # 3. Brace milestone
    if player_goals_today == 2:
        return random.choice([
            f"🔥 **{time_label} GOAL! THAT'S TWO FOR HIM TODAY!** {scorer_disp} (`{pos}`){assist_comm} doubles his tally with relentless hunger for **{team_name}**! On fire! ⚡",
            f"⚽💥 **{time_label} GOAL! A SENSATIONAL BRACE!** {scorer_disp} (`{pos}`){assist_comm} strikes again with deadly killer instinct for **{team_name}**! 🎯🔥",
            f"✌️⚽ **{time_label} GOAL! BRACE SECURED!** Two for {scorer_disp} (`{pos}`){assist_comm}! Slicing through the defense once more for **{team_name}**! ⚡",
        ])

    # 4. Iconic Superstar Signatures
    if 'ronaldo' in s_lower or 'cr7' in s_lower:
        return random.choice([
            f"🔥 **{time_label} GOAL! SIIIIIUUUUU!** {scorer_disp} (`{pos}`){assist_comm} leaps into orbit, hangs in mid-air, and powers an unstoppable header into the roof of the net! The King strikes for **{team_name}**! 👑🇵🇹",
            f"⚽⚡ **{time_label} GOAL! THE INEVITABLE PHENOMENON!** {scorer_disp} (`{pos}`){assist_comm} executes blistering stepovers and lashes a dipping knuckleball past the despairing keeper for **{team_name}**! 🇵🇹💥",
            f"💥🐐 **{time_label} GOAL! BIG-GAME PREDATOR!** Cometh the hour, cometh the man! {scorer_disp} (`{pos}`){assist_comm} finishes with laser precision into the bottom corner for **{team_name}**! 🇵🇹🎯",
        ])
    if 'messi' in s_lower:
        return random.choice([
            f"✨ **{time_label} GOAL! PURE FOOTBALL DIVINITY!** {scorer_disp} (`{pos}`){assist_comm} leaves three defenders frozen in time and caresses a sublime curler into the top corner for **{team_name}**! 🪄🇦🇷",
            f"🌸👑 **{time_label} GOAL! ASTRONOMICAL GENIUS!** {scorer_disp} (`{pos}`){assist_comm} clips an audacious chip over the onrushing goalkeeper! Poetry in motion for **{team_name}**! 🐐⚽",
            f"🪄⚡ **{time_label} GOAL! ANKARA MESSI!** Slalom dribble from {scorer_disp} (`{pos}`){assist_comm}, threading the ball through the eye of a needle into the side-netting for **{team_name}**! 🇦🇷🔥",
        ])
    if 'haaland' in s_lower:
        return random.choice([
            f"🤖 **{time_label} GOAL! THE CYBORG UNLEASHED!** {scorer_disp} (`{pos}`){assist_comm} bulldozes through the center-backs and obliterates the net with a thunderous 110 km/h rocket for **{team_name}**! 🇳🇴⚡",
            f"💥🦁 **{time_label} GOAL! UNSTOPPABLE FORCE!** {scorer_disp} (`{pos}`){assist_comm} meets the ball airborne and smashes a ferocious volley off the crossbar and in for **{team_name}**! 🎯🔥",
        ])
    if 'mbappe' in s_lower or 'mbappé' in s_lower:
        return random.choice([
            f"⚡💨 **{time_label} GOAL! ELECTRIC BLUR!** {scorer_disp} (`{pos}`){assist_comm} turns on the supersonic afterburners, leaving everyone trailing, and slots with ice in his veins for **{team_name}**! 🇫🇷⚽",
            f"🎯🔥 **{time_label} GOAL! LETHAL FINESSE!** {scorer_disp} (`{pos}`){assist_comm} opens up his body and curls a wicked strike around the diving keeper into the side-netting for **{team_name}**! 🐢⚡",
        ])
    if 'neymar' in s_lower:
        return f"🪄🇧🇷 **{time_label} GOAL! JOGA BONITO!** {scorer_disp} (`{pos}`){assist_comm} dances through the penalty box with audacious samba flair and rolls it in with supreme swagger for **{team_name}**! ✨🤙"
    if 'zidane' in s_lower:
        return f"🎩🇫🇷 **{time_label} GOAL! ABSOLUTE MAJESTY!** {scorer_disp} (`{pos}`){assist_comm} pirouettes past his marker and hits an exquisite dropping volley into the top stanchion for **{team_name}**! 🪄👑"
    if 'ronaldinho' in s_lower or 'dinho' in s_lower:
        return f"😁🇧🇷 **{time_label} GOAL! MAGIC IN HIS BOOTS!** {scorer_disp} (`{pos}`){assist_comm} chips the keeper with a huge smile on his face! Pure unadulterated joy for **{team_name}**! 🤙💫"
    if 'lewandowski' in s_lower:
        return random.choice([
            f"⚽🇵🇱 **{time_label} GOAL! CLINICAL MACHINE!** Robert **Lewandowski** (`{pos}`){assist_comm} clinically hammers a thunderbolt into the bottom corner for **{team_name}**! 🎯🇵🇱",
            f"💥🎯 **{time_label} GOAL! NUMBER NINE PERFECTION!** **Lewandowski** (`{pos}`){assist_comm} traps the cross on his chest and rifles a half-volley home for **{team_name}**! ⚽🔥",
        ])

    # 5. Late Stoppage-Time Drama
    if is_stoppage:
        return random.choice([
            f"🚨💥 **{time_label} GOAL! UNBELIEVABLE DRAMA! ABSOLUTE LIMBS!** {scorer_disp} (`{pos}`){assist_comm} strikes at the death for **{team_name}**! The stadium is in utter pandemonium! 🏟️🔥",
            f"⏳⚡ **{time_label} GOAL! STOPPAGE-TIME HEARTBREAKER!** Right when the clock ticks into eternity, {scorer_disp} (`{pos}`){assist_comm} nets a breathless stunner for **{team_name}**! 💔⚽",
            f"🔥🚨 **{time_label} GOAL! CLUTCH HEROICS!** Incredible scenes! {scorer_disp} (`{pos}`){assist_comm} stabs home a dramatic late goal in extra time for **{team_name}**! ⚡🤯",
        ])

    # 6. Equalizer Goal (e.g. 1-1, 2-2)
    if score_for_team == score_for_opp and score_for_team >= 1:
        return random.choice([
            f"⚡🤝 **{time_label} GOAL! AN INSTANT REPLY! WE ARE LEVEL!** {scorer_disp} (`{pos}`){assist_comm} drags **{team_name}** back into the contest with a ruthless finish! All square! 🔥",
            f"💥⚖️ **{time_label} GOAL! PARITY RESTORED!** {scorer_disp} (`{pos}`){assist_comm} connects on the half-turn and makes it all square for **{team_name}**! Game on! ⚽",
            f"🔥🔄 **{time_label} GOAL! BACK FROM THE BRINK!** Sensational resilience! {scorer_disp} (`{pos}`){assist_comm} slots home the equalizer for **{team_name}**! 🎯",
        ])

    # 7. Go-Ahead / Lead Taking Goal (e.g. 2-1 after trailing or being tied)
    if score_for_team == score_for_opp + 1 and score_for_opp >= 1:
        return random.choice([
            f"🚀🔥 **{time_label} GOAL! THEY HAVE TURNED IT AROUND!** {scorer_disp} (`{pos}`){assist_comm} fires **{team_name}** into the lead! What incredible character! ⚡",
            f"💥📈 **{time_label} GOAL! IN THE DRIVER'S SEAT!** {scorer_disp} (`{pos}`){assist_comm} pounces and puts **{team_name}** ahead! Tremendous momentum! 🎯",
        ])

    # 8. Positional Finish Pools
    if ptype == "def":
        return random.choice([
            f"⚽📐 **{time_label} GOAL! BULLET HEADER!** Defender {scorer_disp} (`{pos}`){assist_comm} towers above the penalty box and powers a thumping header home for **{team_name}**! 🏰🔥",
            f"⚽⚔️ **{time_label} GOAL! PURE DESIRE!** Goalmouth scramble! Defender {scorer_disp} (`{pos}`){assist_comm} throws everything on the line to force the ball over the line for **{team_name}**! 🛡️",
            f"⚽💥 **{time_label} GOAL! UNLIKELY HERO!** Center-back {scorer_disp} (`{pos}`){assist_comm} controls with the chest and volleys cleanly into the roof of the net for **{team_name}**! 🤯",
            f"⚽⚡ **{time_label} GOAL! NEAR-POST STUNNER!** {scorer_disp} (`{pos}`){assist_comm} darts across the front post to glance the corner delivery into the far netting for **{team_name}**! 🎯",
            f"⚽☄️ **{time_label} GOAL! AN UNBELIEVABLE THUNDERBOLT!** Defender {scorer_disp} (`{pos}`){assist_comm} steps into midfield and cracks an absolute piledriver past the stunned keeper for **{team_name}**! 💣",
        ])
    elif ptype == "mid":
        return random.choice([
            f"⚽☄️ **{time_label} GOAL! 30-YARD SCREAMER!** {scorer_disp} (`{pos}`){assist_comm} unleashes an unstoppable rocket into the top stanchion for **{team_name}**! 🚀",
            f"⚽🏃 **{time_label} GOAL! LATE ARRIVAL!** {scorer_disp} (`{pos}`){assist_comm} arrives on the edge of the area unmarked and sidefoots with surgical precision for **{team_name}**! 🎯",
            f"⚽🌀 **{time_label} GOAL! AUDACIOUS TRIVELA!** {scorer_disp} (`{pos}`){assist_comm} strikes with the outside of the boot and curls a magical effort into the side-netting for **{team_name}**! 🪄",
            f"⚽📐 **{time_label} GOAL! BENT LIKE A BANANA!** {scorer_disp} (`{pos}`){assist_comm} whips an unstoppable dead-ball strike over the defensive wall for **{team_name}**! 🧱",
            f"⚽💥 **{time_label} GOAL! WHAT A HIT, SON!** The corner was headed away, but {scorer_disp} (`{pos}`){assist_comm} met it with a ferocious dropping half-volley for **{team_name}**! 🔥",
            f"⚽🤝 **{time_label} GOAL! TIKI-TAKA BLISS!** A razor-sharp one-two unlocks the 18-yard box, and {scorer_disp} (`{pos}`){assist_comm} tucks it into the corner for **{team_name}**! 🪄",
        ])
    else:  # Attackers
        return random.choice([
            f"⚽🧊 **{time_label} GOAL! PURE CLASS!** {scorer_disp} (`{pos}`){assist_comm} cuts past the keeper with silky footwork and finishes with ice in his veins for **{team_name}**! 🧊⚽",
            f"⚽🎨 **{time_label} GOAL! DELICATE CHIP!** {scorer_disp} (`{pos}`){assist_comm} dinks it sublimely over the committed goalkeeper for **{team_name}**! Pure artistry! ✨",
            f"⚽💥 **{time_label} GOAL! THUNDERBOLT VOLLEY!** {scorer_disp} (`{pos}`){assist_comm} smashes a venomous first-time strike off the crossbar and in for **{team_name}**! 🚀",
            f"⚽⚡ **{time_label} GOAL! SOLO SPECTACULAR!** {scorer_disp} (`{pos}`){assist_comm} takes on three defenders single-handedly and slides it into the bottom corner for **{team_name}**! 💨",
            f"⚽🎯 **{time_label} GOAL! TOP CORNER PERFECTION!** {scorer_disp} (`{pos}`){assist_comm} bends a peach of a curler right where postage stamps live for **{team_name}**! 📮✨",
            f"⚽🦊 **{time_label} GOAL! POACHER'S INSTINCT!** {scorer_disp} (`{pos}`){assist_comm} gambles on the second ball and stabs home from 6 yards out for **{team_name}**! 🐾",
            f"⚽🪄 **{time_label} GOAL! CHEEKY FINISH!** {scorer_disp} (`{pos}`){assist_comm} slips the ball right through the keeper's legs with supreme composure for **{team_name}**! 🪡",
            f"⚽⚡ **{time_label} GOAL! RAPID BREAKAWAY!** A lightning 3-pass counter-attack ends with {scorer_disp} (`{pos}`){assist_comm} rounding the keeper for **{team_name}**! ⚡",
        ])

def generate_dynamic_in_play_commentary(
    time_label: str,
    att_team_name: str,
    a_p: str,
    m_p: str,
    d_p: str,
    g_p: str,
    om_p: str
) -> tuple[str, str | None]:
    categories = [
        # 1. Goalkeeping heroics
        [
            (f"🧤 **{time_label}** FINGERTIP SAVE! **{g_p}** produces an acrobatic reflex stop to tip **{a_p}**'s venomous volley around the post!", "save"),
            (f"🧤 **{time_label}** WHAT A SAVE! **{g_p}** spreads himself wide and denies a point-blank blast from **{a_p}** with an outstretched boot!", "save"),
            (f"🧤 **{time_label}** UNBELIEVABLE DOUBLE-SAVE! **{g_p}** parries **{a_p}**'s header and immediately scrambles off the turf to smother the rebound!", "save"),
            (f"🧤 **{time_label}** SWEEPER KEEPER! **{g_p}** charges 30 yards out of goal to slide tackle the ball away right before **{a_p}** could shoot!", "save"),
            (f"🧤 **{time_label}** FLYING STOP! **{g_p}** goes full stretch to turn **{m_p}**'s dipping 30-yard rocket away from the top corner!", "save"),
            (f"🧤 **{time_label}** SAFE HANDS! **{g_p}** commands his area, leaping into a crowd of bodies to pluck the dangerous cross out of the air!", None),
            (f"🧤 **{time_label}** HOW DID HE SAVE THAT?! **{a_p}** was certain he scored, but **{g_p}** claws it off the goal-line in the nick of time!", "save"),
            (f"🧤 **{time_label}** CAT-LIKE DIVE! **{g_p}** gets a strong hand down to turn **{a_p}**'s deflected daisy-cutter behind for a corner!", "save"),
        ],
        # 2. Woodwork & Near Misses
        [
            (f"🚀 **{time_label}** WOODWORK! **{a_p}** rattles the crossbar with a ferocious 25-yard strike that leaves the goal frame vibrating!", None),
            (f"🚀 **{time_label}** OFF THE POST! **{a_p}** cuts inside and unleashes a thunderous curler that pings off the upright and bounces out!", None),
            (f"🚀 **{time_label}** AGONIZINGLY WIDE! **{a_p}**'s diving header skims the crossbar and ripples the roof of the net!", None),
            (f"🚀 **{time_label}** INCHES AWAY! **{m_p}** connects with a dipping knuckleball that whistles mere centimeters over the bar!", None),
            (f"🚀 **{time_label}** GOLDEN OPPORTUNITY MISSED! **{a_p}** breaks clean through on goal but drags his low finish agonizingly wide of the far post!", None),
            (f"🚀 **{time_label}** WICKED DEFLECTION! **{a_p}**'s shot takes a looping deflection off **{d_p}** and drops just onto the roof of the net!", None),
        ],
        # 3. Dribbling, Skills & Through Balls
        [
            (f"⚡ **{time_label}** AUDACIOUS PASS! **{m_p}** threads an exquisite no-look through-ball, slicing open {att_team_name}'s defense!", None),
            (f"🪄 **{time_label}** SILKY SKILLS! **{a_p}** beats two defenders with a mesmerizing roulette before squaring dangerously into the box!", None),
            (f"🪄 **{time_label}** TEKKEN ON TURF! **{a_p}** executes a lightning-fast elastico, sending the fullback completely the wrong way!", None),
            (f"🎯 **{time_label}** PINPOINT PING! **{m_p}** switches play with a breathtaking 50-yard diagonal pass landing on a sixpence for **{a_p}**!", None),
            (f"🪄 **{time_label}** NUTMEG! **{a_p}** audaciously slips the ball through **{d_p}**'s legs and surges into the penalty box!", None),
            (f"⚡ **{time_label}** TIKI-TAKA BLISS! A fluid 5-pass one-touch move between **{m_p}** and **{a_p}** carves open the final third!", None),
            (f"🌀 **{time_label}** RABONA CROSS! **{a_p}** whips a delightful rabona into the mixer, creating sheer panic in the six-yard box!", None),
            (f"⚡ **{time_label}** ANKLE-BREAKER! **{a_p}** drops the shoulder with such ferocity that **{d_p}** is left scrambling on the turf!", None),
        ],
        # 4. Defensive Heroics & Tackles
        [
            (f"🛡️ **{time_label}** GOAL-LINE CLEARANCE! **{d_p}** slides across the turf to hook **{a_p}**'s chip off the line at the very last second!", None),
            (f"⚔️ **{time_label}** CRUNCHING TACKLE! **{om_p}** stops a dangerous breakaway with an inch-perfect, ball-winning challenge!", None),
            (f"🛡️ **{time_label}** HEROIC BLOCK! **{d_p}** throws their entire body in front of **{a_p}**'s thunderous blast inside the 18-yard box!", None),
            (f"🏰 **{time_label}** MONSTER IN THE AIR! **{d_p}** rises above three attackers to power away a lethal corner delivery!", None),
            (f"🧠 **{time_label}** MASTERCLASS INTERCEPTION! **{om_p}** reads the attacker's mind, stepping forward to pinch possession cleanly!", None),
            (f"⚔️ **{time_label}** RECOVERY PACE! **{a_p}** thought he was clean through, but **{d_p}** gallops back to make a textbook recovery tackle!", None),
            (f"🛡️ **{time_label}** ROCK SOLID! **{d_p}** out-muscles **{a_p}** shoulder-to-shoulder and ushers the ball safely out for a goal kick!", None),
            (f"📐 **{time_label}** OFFSIDE TRAP! **{d_p}** steps up in unison, leaving **{a_p}** stranded as the linesman's flag shoots up!", None),
        ],
        # 5. Discipline & Match Drama
        [
            (f"🟨 **{time_label}** YELLOW CARD! Tactical foul by **{d_p}** to cynically haul down **{a_p}** and stop a lightning counter-attack!", "yellow"),
            (f"🟨 **{time_label}** YELLOW CARD! Late sliding tackle by **{om_p}** on the edge of the area! The referee reaches straight into his pocket!", "yellow"),
            (f"⚠️ **{time_label}** PENALTY SHOUTS! **{a_p}** goes down in the box under contact from **{d_p}**, but the referee vigorously waves play on!", None),
            (f"🔥 **{time_label}** TEMPERATURE RISES! **{m_p}** and **{om_p}** square up chest-to-chest after a ferocious 50-50 challenge!", None),
            (f"🚑 **{time_label}** HEAVY COLLISION! **{a_p}** and keeper **{g_p}** collide contesting a high cross, but both get back up ready to fight on!", None),
        ],
        # 6. Stadium Atmosphere & Momentum
        [
            (f"📢 **{time_label}** THE STADIUM ROARS! The supporters are on their feet chanting as {att_team_name} surges forward with relentless momentum!", None),
            (f"🔥 **{time_label}** HIGH VOLTAGE! {att_team_name} suffocating their opponent with an intense, suffocating high-press in the final third!", None),
            (f"⚡ **{time_label}** BREATHLESS TEMPO! Both teams throwing caution to the wind in a thrilling, end-to-end transition battle!", None),
            (f"⏳ **{time_label}** TENSION AT PEAK! Every pass, every tackle carries immense weight as managers scream instructions from the technical area!", None),
        ]
    ]
    chosen_cat = random.choices(categories, weights=[25, 20, 20, 20, 10, 5], k=1)[0]
    return random.choice(chosen_cat)

class MatchRequestView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, cog, squad_a, squad_b, fans_a, fans_b, ovr_a, ovr_b, timeout_secs: int = 60):
        super().__init__(timeout=timeout_secs)
        self.challenger = challenger
        self.opponent = opponent
        self.cog = cog
        self.squad_a = squad_a
        self.squad_b = squad_b
        self.fans_a = fans_a
        self.fans_b = fans_b
        self.ovr_a = ovr_a
        self.ovr_b = ovr_b
        self.timeout_secs = timeout_secs
        self.message = None
        self.accepted = False

    async def on_timeout(self):
        if self.accepted:
            return
        ACTIVE_MATCH_USERS.discard(self.challenger.id)
        ACTIVE_MATCH_USERS.discard(self.opponent.id)
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content=f"⏱️ **Match Challenge Expired!** {self.opponent.display_name} did not respond within {self.timeout_secs} seconds.", view=self)
            except Exception:
                pass

    @discord.ui.button(label="Accept Match", style=discord.ButtonStyle.green, emoji="✅")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can accept!", ephemeral=True)
            return
            
        if self.accepted:
            await interaction.response.send_message("❌ This match challenge has already been accepted!", ephemeral=True)
            return

        self.accepted = True
        self.stop()
        for child in self.children:
            child.disabled = True

        # Extend lock for both players for the lobby phase (320 seconds)
        ACTIVE_MATCH_USERS.add(self.challenger.id, duration=320)
        ACTIVE_MATCH_USERS.add(self.opponent.id, duration=320)

        # Transition to Lobby
        lobby = MatchLobbyView(self.challenger, self.opponent, self.cog, self.squad_a, self.squad_b, self.fans_a, self.fans_b, self.ovr_a, self.ovr_b, self.message)
        await lobby.update_message(interaction)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged player can decline!", ephemeral=True)
            return
            
        self.stop()
        ACTIVE_MATCH_USERS.discard(self.challenger.id)
        ACTIVE_MATCH_USERS.discard(self.opponent.id)
        
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"❌ **{self.opponent.display_name}** declined the match.", view=self)

class MatchLobbyView(discord.ui.View):
    def __init__(self, challenger, opponent, cog, squad_a, squad_b, fans_a, fans_b, ovr_a, ovr_b, message):
        super().__init__(timeout=300)
        self.challenger = challenger
        self.opponent = opponent
        self.cog = cog
        self.squad_a = squad_a
        self.squad_b = squad_b
        self.fans_a = fans_a
        self.fans_b = fans_b
        self.ovr_a = ovr_a
        self.ovr_b = ovr_b
        self.message = message
        
        self.format = 1
        self.tiebreaker = "Penalties"
        self.stakes = {
            self.challenger.id: {"coins": 0, "card": None, "card_id": None},
            self.opponent.id: {"coins": 0, "card": None, "card_id": None}
        }
        self.ready = {self.challenger.id: False, self.opponent.id: False}
        self.series_started = False
        
    async def on_timeout(self):
        if not self.series_started:
            ACTIVE_MATCH_USERS.discard(self.challenger.id)
            ACTIVE_MATCH_USERS.discard(self.opponent.id)
            for child in self.children:
                child.disabled = True
            try:
                if self.message:
                    await self.message.edit(content="⏱️ **Lobby Expired!** Players took too long to ready up.", view=self)
            except Exception:
                pass
        
    async def update_message(self, interaction=None):
        embed = discord.Embed(title="⚔️ Match Lobby", color=discord.Color.blue())
        embed.description = f"**{self.challenger.display_name}** vs **{self.opponent.display_name}**"
        embed.add_field(name="Format", value=f"Best of {self.format}")
        embed.add_field(name="Tiebreaker", value=self.tiebreaker)
        c_stakes = self.stakes[self.challenger.id]
        o_stakes = self.stakes[self.opponent.id]
        c_str = f"Coins: {c_stakes['coins']:,}" + (f"\nCard: {c_stakes['card']}" if c_stakes['card'] else "")
        o_str = f"Coins: {o_stakes['coins']:,}" + (f"\nCard: {o_stakes['card']}" if o_stakes['card'] else "")
        embed.add_field(name=f"{self.challenger.display_name}'s Stakes", value=c_str, inline=False)
        embed.add_field(name=f"{self.opponent.display_name}'s Stakes", value=o_str, inline=False)
        status_c = "✅ Ready" if self.ready[self.challenger.id] else "⏳ Not Ready"
        status_o = "✅ Ready" if self.ready[self.opponent.id] else "⏳ Not Ready"
        embed.add_field(name="Status", value=f"{self.challenger.display_name}: {status_c}\n{self.opponent.display_name}: {status_o}", inline=False)
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.message:
            await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Format: Bo1", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_format(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.challenger.id, self.opponent.id]: return
        self.ready[self.challenger.id] = False
        self.ready[self.opponent.id] = False
        if self.format == 1: self.format = 3
        elif self.format == 3: self.format = 5
        else: self.format = 1
        button.label = f"Format: Bo{self.format}"
        await self.update_message(interaction)

    @discord.ui.button(label="Tiebreaker: Penalties", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_tiebreaker(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.challenger.id, self.opponent.id]: return
        self.ready[self.challenger.id] = False
        self.ready[self.opponent.id] = False
        if self.tiebreaker == "Penalties":
            self.tiebreaker = "Golden Goal"
        else:
            self.tiebreaker = "Penalties"
        button.label = f"Tiebreaker: {self.tiebreaker}"
        await self.update_message(interaction)

    @discord.ui.button(label="Wager Coins", style=discord.ButtonStyle.primary, row=1)
    async def wager_coins(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.challenger.id, self.opponent.id]: return
        await interaction.response.send_modal(WagerCoinsModal(self))

    @discord.ui.button(label="Wager Card (ID)", style=discord.ButtonStyle.primary, row=1)
    async def wager_card(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.challenger.id, self.opponent.id]: return
        await interaction.response.send_modal(WagerCardModal(self))

    @discord.ui.button(label="Ready", style=discord.ButtonStyle.success, row=2)
    async def ready_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.challenger.id, self.opponent.id]: return
        if self.series_started:
            return await interaction.response.send_message("❌ Match series has already started!", ephemeral=True)

        self.ready[interaction.user.id] = True
        if self.ready[self.challenger.id] and self.ready[self.opponent.id]:
            self.series_started = True
            self.stop()
            for child in self.children: child.disabled = True
            await self.update_message(interaction)
            
            # Lock both players for active match simulation (600s = 10 mins)
            ACTIVE_MATCH_USERS.add(self.challenger.id, duration=600)
            ACTIVE_MATCH_USERS.add(self.opponent.id, duration=600)

            # Start Series
            asyncio.create_task(self.cog.run_series(
                interaction, self.challenger, self.opponent, 
                self.ovr_a, self.ovr_b, self.squad_a, self.squad_b, 
                self.message, self
            ))
        else:
            await self.update_message(interaction)

    @discord.ui.button(label="Cancel / Leave", style=discord.ButtonStyle.danger, row=2)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.challenger.id, self.opponent.id]:
            return await interaction.response.send_message("❌ You are not part of this match!", ephemeral=True)
        if self.series_started:
            return await interaction.response.send_message("❌ Match series has already started!", ephemeral=True)
        self.stop()
        ACTIVE_MATCH_USERS.discard(self.challenger.id)
        ACTIVE_MATCH_USERS.discard(self.opponent.id)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"❌ **{interaction.user.display_name}** cancelled the match lobby.", embed=None, view=self)

class WagerCoinsModal(discord.ui.Modal, title="Wager Coins"):
    amount = discord.ui.TextInput(label="Coins to Wager (max 100B)", placeholder="e.g. 50000000", max_length=15)
    def __init__(self, lobby):
        super().__init__()
        self.lobby = lobby
    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.amount.value.replace(',', '').strip())
        except:
            return await interaction.response.send_message("Invalid amount.", ephemeral=True)
        if val < 0 or val > 100_000_000_000:
            return await interaction.response.send_message("Must be between 0 and 100B.", ephemeral=True)
        
        # Check user balance
        import database
        user_db = await database.get_user(interaction.user.id)
        if user_db.get('coins', 0) < val:
            return await interaction.response.send_message("You don't have enough coins.", ephemeral=True)
            
        self.lobby.stakes[interaction.user.id]['coins'] = val
        self.lobby.ready[self.lobby.challenger.id] = False
        self.lobby.ready[self.lobby.opponent.id] = False
        await self.lobby.update_message(interaction)

class WagerCardModal(discord.ui.Modal, title="Wager Card"):
    card_id = discord.ui.TextInput(label="Inventory ID of the card", placeholder="e.g. 12345", max_length=10)
    def __init__(self, lobby):
        super().__init__()
        self.lobby = lobby
    async def on_submit(self, interaction: discord.Interaction):
        try:
            cid = int(self.card_id.value.strip())
        except:
            return await interaction.response.send_message("Invalid ID.", ephemeral=True)
            
        import database
        inv = await database.get_inventory(interaction.user.id)
        card = next((c for c in inv if c['id'] == cid), None)
        if not card:
            return await interaction.response.send_message("Card not found in your inventory.", ephemeral=True)
            
        # Check if card is in squad
        squad = await database.get_squad(interaction.user.id)
        in_squad = any(p and p.get('inv_id') == cid for p in squad.get('players', {}).values())
        if in_squad:
            return await interaction.response.send_message("Cannot wager a card that is currently in your squad.", ephemeral=True)
            
        c_name = card.get('card_name', 'Unknown Card')
        self.lobby.stakes[interaction.user.id]['card'] = c_name
        self.lobby.stakes[interaction.user.id]['card_id'] = cid
        self.lobby.ready[self.lobby.challenger.id] = False
        self.lobby.ready[self.lobby.opponent.id] = False
        await self.lobby.update_message(interaction)


class MatchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._official_players_cache = None
        self._last_cache_time = 0

    async def get_official_players_cache(self):
        """Preload and cache authentic RenderZ official players from official_cards."""
        now = time.time()
        if self._official_players_cache and (now - self._last_cache_time < 3600):
            return self._official_players_cache
        try:
            rows = await database.fetch_all("SELECT player_name, card_name, rating, position, player_data FROM official_cards")
            cache = {}
            for r in (rows or []):
                p_name = (r.get('card_name') or r.get('player_name') or '').strip().lower()
                if not p_name: continue
                pd = r.get('player_data')
                if isinstance(pd, str):
                    try: pd = json.loads(pd)
                    except Exception: pd = {}
                avg = pd.get('avgStats') or {}
                avg_gk = pd.get('avgGkStats') or {}
                st = pd.get('stats') or {}
                rating = int(r.get('rating') or 100)
                if p_name not in cache or rating > cache[p_name].get('ovr', 0):
                    cache[p_name] = {
                        'ovr': rating,
                        'pos': r.get('position'),
                        'avgStats': avg,
                        'avgGkStats': avg_gk,
                        'stats': st
                    }
            self._official_players_cache = cache
            self._last_cache_time = now
            return cache
        except Exception:
            return self._official_players_cache or {}

    def calculate_ovr(self, squad):
        total = 0
        count = 0
        players = squad.get("players", {})
        for pos, player in players.items():
            if player:
                total += player['ovr']
                count += 1
        return round(total / 11) if count == 11 else 0

    def get_division(self, fans: int, gp_cfg: dict = None):
        if gp_cfg and "division_tiers" in gp_cfg and gp_cfg["division_tiers"]:
            tiers = sorted(gp_cfg["division_tiers"], key=lambda x: int(x.get('min_fans', 0)))
            matched = tiers[0]
            for t in tiers:
                if fans >= int(t.get('min_fans', 0)):
                    matched = t
                else:
                    break
            badge = matched.get('badge', '')
            name = matched.get('name', 'Amateur')
            return f"{name} {badge}".strip()

        if fans < 10000: return "Amateur III 🥉"
        elif fans < 20000: return "Amateur II 🥉"
        elif fans < 30000: return "Amateur I 🥉"
        elif fans < 50000: return "Pro III 🥈"
        elif fans < 70000: return "Pro II 🥈"
        elif fans < 100000: return "Pro I 🥈"
        elif fans < 200000: return "World Class III 🥇"
        elif fans < 300000: return "World Class II 🥇"
        elif fans < 400000: return "World Class I 🥇"
        elif fans < 600000: return "Legendary III 💎"
        elif fans < 800000: return "Legendary II 💎"
        elif fans < 1000000: return "Legendary I 💎"
        elif fans < 1200000: return "FC Champion III 🏆"
        elif fans < 1500000: return "FC Champion II 🏆"
        else: return "FC Champion I 👑"

    def get_division_tier(self, fans: int, gp_cfg: dict = None):
        if gp_cfg and "division_tiers" in gp_cfg and gp_cfg["division_tiers"]:
            tiers = sorted(gp_cfg["division_tiers"], key=lambda x: int(x.get('min_fans', 0)))
            matched = tiers[0]
            for t in tiers:
                if fans >= int(t.get('min_fans', 0)):
                    matched = t
                else:
                    break
            return matched
        return None

    def get_division_index(self, fans: int, gp_cfg: dict = None):
        if gp_cfg and "division_tiers" in gp_cfg and gp_cfg["division_tiers"]:
            tiers = sorted(gp_cfg["division_tiers"], key=lambda x: int(x.get('min_fans', 0)))
            idx = 0
            for i, t in enumerate(tiers):
                if fans >= int(t.get('min_fans', 0)):
                    idx = i
                else:
                    break
            return idx

        if fans < 10000: return 0
        elif fans < 20000: return 1
        elif fans < 30000: return 2
        elif fans < 50000: return 3
        elif fans < 70000: return 4
        elif fans < 100000: return 5
        elif fans < 200000: return 6
        elif fans < 300000: return 7
        elif fans < 400000: return 8
        elif fans < 600000: return 9
        elif fans < 800000: return 10
        elif fans < 1000000: return 11
        elif fans < 1200000: return 12
        elif fans < 1500000: return 13
        else: return 14

    def get_div_reward(self, index: int):
        if index <= 2: return 3
        elif index <= 5: return 5
        elif index <= 8: return 7
        elif index <= 11: return 10
        elif index == 12: return 15
        elif index == 13: return 20
        else: return 30


    async def run_series(self, interaction, player_a, player_b, ovr_a, ovr_b, squad_a, squad_b, message, lobby):
        try:
            format_num = lobby.format
            target_wins = (format_num // 2) + 1
            wins_a = 0
            wins_b = 0
            
            for match_idx in range(1, format_num + 1):
                if wins_a >= target_wins or wins_b >= target_wins:
                    break
                    
                msg = await interaction.channel.send(f"🏆 **SERIES MATCH {match_idx}/{format_num}** | {player_a.display_name} [{wins_a} - {wins_b}] {player_b.display_name}")
                
                class DummyInteraction:
                    def __init__(self, channel, user, msg):
                        self.channel = channel
                        self.user = user
                        self.response = None
                        self.msg = msg
                    async def edit_original_response(self, *args, **kwargs):
                        if self.msg:
                            return await self.msg.edit(**kwargs)
                        raise Exception("Dummy interaction")
                    @property
                    def followup(self):
                        class Followup:
                            def __init__(self, msg):
                                self.msg = msg
                            async def send(self, *args, **kwargs):
                                pass
                        return Followup(self.msg)
                
                dummy_interaction = DummyInteraction(interaction.channel, player_a, msg)
                score_a, score_b = await self.simulate_live_match(
                    dummy_interaction, player_a, player_b, ovr_a, ovr_b, squad_a, squad_b, message=msg, is_series_submatch=True
                )
                
                # Tiebreaker logic if Golden Goal
                if score_a == score_b and lobby.tiebreaker == "Golden Goal":
                    await interaction.channel.send(f"⚖️ Match tied at {score_a}-{score_b}! Going to **Golden Goal**... (Simulated instantly)")
                    import random
                    win_prob_a = ovr_a / (ovr_a + ovr_b)
                    if random.random() < win_prob_a:
                        score_a += 1
                    else:
                        score_b += 1
                    await interaction.channel.send(f"⚽ **GOLDEN GOAL!** {'⭐ ' + player_a.display_name if score_a > score_b else '⭐ ' + player_b.display_name} scored the winner! ({score_a}-{score_b})")
                    
                if score_a > score_b: wins_a += 1
                elif score_b > score_a: wins_b += 1
                
                if match_idx < format_num and (wins_a < target_wins and wins_b < target_wins):
                    await asyncio.sleep(5)
                    
            winner = player_a if wins_a > wins_b else player_b if wins_b > wins_a else None
            
            # Resolve stakes
            if winner:
                loser = player_b if winner == player_a else player_a
                
                win_stakes = lobby.stakes[winner.id]
                lose_stakes = lobby.stakes[loser.id]
                
                import database
                conn = await database.get_db()
                
                embed = discord.Embed(title="🏆 SERIES CONCLUDED", color=discord.Color.gold())
                embed.description = f"**{winner.display_name}** wins the series `{max(wins_a, wins_b)} - {min(wins_a, wins_b)}`!"
                
                # Transfer Coins
                if lose_stakes['coins'] > 0:
                    await conn.execute("UPDATE users SET coins = coins - $1 WHERE user_id = $2", lose_stakes['coins'], loser.id)
                    await conn.execute("UPDATE users SET coins = coins + $1 WHERE user_id = $2", lose_stakes['coins'], winner.id)
                    embed.add_field(name="💰 Coins Won", value=f"{lose_stakes['coins']:,} coins from {loser.display_name}")
                    
                # Transfer Cards
                if lose_stakes['card_id']:
                    await conn.execute("UPDATE inventory SET user_id = $1 WHERE id = $2 AND user_id = $3", winner.id, lose_stakes['card_id'], loser.id)
                    embed.add_field(name="🃏 Card Won", value=f"{lose_stakes['card']} from {loser.display_name}")
                    
                await interaction.channel.send(embed=embed)
            else:
                await interaction.channel.send("🤝 The series ended in a tie. No stakes were transferred.")
        except Exception as e:
            print(f"[Match Series Error] {e}")
            import traceback
            traceback.print_exc()
        finally:
            ACTIVE_MATCH_USERS.discard(player_a.id)
            ACTIVE_MATCH_USERS.discard(player_b.id)


    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            if custom_id.startswith("tourney_join_"):
                t_id = int(custom_id.split("_")[2])
                try:
                    t_row = await database.fetch_one("SELECT registration_open, max_participants FROM tournaments WHERE id = $1", t_id)
                    if t_row and t_row.get("registration_open") is False:
                        await interaction.response.send_message("❌ Registration for this tournament is currently closed!", ephemeral=True)
                        return

                    already_registered = await database.fetch_val(
                        "SELECT 1 FROM tournament_participants WHERE tournament_id = $1 AND user_id = $2",
                        t_id, interaction.user.id
                    )
                    if already_registered:
                        await interaction.response.send_message("⚠️ You are already registered for this tournament!", ephemeral=True)
                        return

                    count = 0
                    if t_row and t_row.get("max_participants"):
                        count = await database.fetch_val("SELECT COUNT(*) FROM tournament_participants WHERE tournament_id = $1", t_id) or 0
                        if count >= t_row["max_participants"]:
                            await interaction.response.send_message("⚠️ This tournament is already full!", ephemeral=True)
                            return
                    
                    # Enforce valid 11-player squad
                    squad = await database.get_squad(interaction.user.id)
                    s_players = squad.get("players", {}) if squad else {}
                    valid_squad_players = [p for p in s_players.values() if p and isinstance(p, dict)]
                    if len(valid_squad_players) < 11:
                        await interaction.response.send_message(
                            f"❌ You need a complete 11-player squad to enter this tournament!\nYour squad currently has only **{len(valid_squad_players)}/11 players**. Use `/squad` to finish setting up your team before joining.",
                            ephemeral=True
                        )
                        return

                    username = interaction.user.name
                    display_name = interaction.user.display_name or interaction.user.global_name or interaction.user.name
                    await database.execute(
                        """
                        INSERT INTO tournament_participants (tournament_id, user_id, username, display_name) 
                        VALUES ($1, $2, $3, $4)
                        """,
                        t_id, interaction.user.id, username, display_name
                    )

                    new_count = count + 1
                    max_spots = t_row.get("max_participants") if t_row else 16
                    if max_spots and new_count >= max_spots:
                        await database.execute("UPDATE tournaments SET registration_open = FALSE, status = 'REGISTRATION_CLOSED' WHERE id = $1", t_id)
                        await interaction.response.send_message(f"✅ You have registered! ({new_count}/{max_spots})\n🎉 **Tournament is now 100% full!** Registration is officially closed.", ephemeral=True)
                        try:
                            if interaction.channel:
                                await interaction.channel.send(f"🔒 **All {max_spots} spots for the tournament are filled!** Registration is now closed.")
                        except Exception:
                            pass
                    else:
                        await interaction.response.send_message(f"✅ You have successfully registered for the tournament! ({new_count}/{max_spots} spots filled)", ephemeral=True)
                except Exception as e:
                    if 'unique constraint' in str(e).lower() or 'duplicate key' in str(e).lower():
                        await interaction.response.send_message("⚠️ You are already registered for this tournament.", ephemeral=True)
                    else:
                        await interaction.response.send_message("❌ Error registering for tournament.", ephemeral=True)

    async def announce_tournament(self, payload):
        try:
            import json
            data = json.loads(payload) if isinstance(payload, str) else payload
            channel_id = int(data.get('channel_id'))
            channel = self.bot.get_channel(channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception as fe:
                    print(f"[Announce Tournament] Could not fetch channel {channel_id}: {fe}")
                    return f"Could not fetch channel {channel_id}: {fe}"
            if not channel:
                print(f"[Announce Tournament] Channel {channel_id} not found!")
                return f"Channel {channel_id} not found"
            
            t_id = data.get('tournament_id')
            name = data.get('name')
            custom_msg = data.get('announcement_msg')
            desc = custom_msg.strip() if (custom_msg and custom_msg.strip()) else "A new tournament has been announced! Click the button below to register."
            
            embed = discord.Embed(title=f"🏆 NEW TOURNAMENT: {name}", description=desc, color=discord.Color.gold())
            if data.get('type'):
                t_format = data.get('format', 'Single Legged')
                embed.add_field(name="⚔️ Format", value=f"{data.get('type')} ({t_format})", inline=True)
            if data.get('max_participants'):
                embed.add_field(name="👥 Max Spots", value=f"{data.get('max_participants')} Players", inline=True)
            
            view = discord.ui.View(timeout=None)
            btn = discord.ui.Button(label="Participate", style=discord.ButtonStyle.green, emoji="🎟️", custom_id=f"tourney_join_{t_id}")
            view.add_item(btn)
            
            role_mention = ""
            if channel.guild:
                role = discord.utils.get(channel.guild.roles, name="DestiFC Players") or channel.guild.get_role(1557010712013045860)
                if role:
                    role_mention = role.mention

            msg = await channel.send(content=f"📢 {role_mention}" if role_mention else None, embed=embed, view=view)
            res_str = f"Successfully posted announcement (Msg ID: {msg.id}) in channel {channel_id}!"
            print(f"[Announce Tournament] {res_str}")
            return res_str
        except Exception as e:
            err_str = f"Announce Tournament Error: {e}"
            print(f"[{err_str}]")
            import traceback
            traceback.print_exc()
            return err_str

    async def trigger_tournament_match(self, payload):
        try:
            import json
            data = json.loads(payload) if isinstance(payload, str) else payload
            channel_id = int(data.get('channel_id'))
            player_a_id = int(data.get('player_a_id'))
            player_b_id = int(data.get('player_b_id'))
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception as fe:
                    print(f"[Trigger Match] Could not fetch channel {channel_id}: {fe}")
                    return
            if not channel:
                return
            
            player_a = channel.guild.get_member(player_a_id)
            if not player_a:
                try:
                    player_a = await channel.guild.fetch_member(player_a_id)
                except Exception:
                    pass
            player_b = channel.guild.get_member(player_b_id)
            if not player_b:
                try:
                    player_b = await channel.guild.fetch_member(player_b_id)
                except Exception:
                    pass
            if not player_a or not player_b:
                await channel.send(f"Error: One or both players ({player_a_id}, {player_b_id}) are not in the server.")
                return
                
            squad_a = await database.get_squad(player_a.id)
            squad_b = await database.get_squad(player_b.id)
            
            ovr_a = self.calculate_ovr(squad_a)
            ovr_b = self.calculate_ovr(squad_b)
            
            ACTIVE_MATCH_USERS.add(player_a.id, duration=300)
            ACTIVE_MATCH_USERS.add(player_b.id, duration=300)
            
            msg = await channel.send(f"📢 **TOURNAMENT MATCH STARTING!**\n{player_a.mention} vs {player_b.mention}")
        
            class DummyInteraction:
                def __init__(self, channel, user):
                    self.channel = channel
                    self.user = user
                    self.response = None
                async def edit_original_response(self, *args, **kwargs):
                    raise Exception("Dummy interaction")
                    
            dummy = DummyInteraction(channel, player_a)
            await self.simulate_live_match(dummy, player_a, player_b, ovr_a, ovr_b, squad_a, squad_b, message=msg)
        except Exception as e:
            print(f"[Trigger Tournament Match Error] {e}")
            import traceback
            traceback.print_exc()

    @app_commands.command(name="play", description="Challenge another user to a H2H Division Rivals Match!")
    async def play(self, interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot:
            return await interaction.response.send_message("❌ You cannot challenge a Discord bot to a match!", ephemeral=True)
            
        if opponent.id == interaction.user.id:
            return await interaction.response.send_message("❌ You can't play against yourself!", ephemeral=True)

        # 1. ATOMIC LOCK ACQUISITION: Lock BOTH players synchronously before ANY async operations!
        if not ACTIVE_MATCH_USERS.acquire_both(interaction.user.id, opponent.id, duration=90):
            if interaction.user.id in ACTIVE_MATCH_USERS:
                return await interaction.response.send_message("❌ You already have an active match, lobby, or pending challenge! Please finish it before starting another.", ephemeral=True)
            else:
                return await interaction.response.send_message(f"❌ **{opponent.display_name}** is already in an active match, lobby, or pending challenge! Please wait for them to finish.", ephemeral=True)

        try:
            await interaction.response.defer()

            gp_cfg = await database.get_gameplay_config()
            cooldown_mins = int(gp_cfg.get('match_cooldown_mins', 0))
            if cooldown_mins > 0:
                import time
                now = int(time.time())
                cooldown_secs = cooldown_mins * 60
                p = await database.get_db()
                last_match_a = await p.fetchval('SELECT last_match_time FROM users WHERE user_id = $1', interaction.user.id) or 0
                if now - last_match_a < cooldown_secs:
                    rem = cooldown_secs - (now - last_match_a)
                    ACTIVE_MATCH_USERS.discard(interaction.user.id)
                    ACTIVE_MATCH_USERS.discard(opponent.id)
                    return await interaction.followup.send(f"⏳ Match cooldown active! You can challenge again in **{int(rem // 60)}m {int(rem % 60)}s**.")
            
            squad_a = await database.get_squad(interaction.user.id)
            squad_b = await database.get_squad(opponent.id)
            
            ovr_a = self.calculate_ovr(squad_a)
            ovr_b = self.calculate_ovr(squad_b)
            
            if ovr_a == 0:
                ACTIVE_MATCH_USERS.discard(interaction.user.id)
                ACTIVE_MATCH_USERS.discard(opponent.id)
                return await interaction.followup.send(f"❌ Your starting XI is incomplete! Use `/squad set` or `/squad autobuild` to fill all 11 positions.")
            if ovr_b == 0:
                ACTIVE_MATCH_USERS.discard(interaction.user.id)
                ACTIVE_MATCH_USERS.discard(opponent.id)
                return await interaction.followup.send(f"❌ {opponent.display_name}'s starting XI is incomplete! They must fill all 11 positions.")
                
            user_a = await database.get_user(interaction.user.id)
            user_b = await database.get_user(opponent.id)
            fans_a, fans_b = user_a.get('fans', 0), user_b.get('fans', 0)
            
            timeout_secs = int(gp_cfg.get('match_challenge_timeout_secs', 60))
            # Refresh lock for challenge window
            ACTIVE_MATCH_USERS.add(interaction.user.id, duration=timeout_secs + 15)
            ACTIVE_MATCH_USERS.add(opponent.id, duration=timeout_secs + 15)

            view = MatchRequestView(interaction.user, opponent, self, squad_a, squad_b, fans_a, fans_b, ovr_a, ovr_b, timeout_secs=timeout_secs)
            
            msg = await interaction.followup.send(
                f"⚔️ **DIVISION RIVALS CHALLENGE!** ⚔️\n\n**{interaction.user.display_name} ({ovr_a})** [{self.get_division(fans_a, gp_cfg)}]\n🆚\n**{opponent.display_name} ({ovr_b})** [{self.get_division(fans_b, gp_cfg)}]\n\nHey {opponent.mention}, you have been challenged! Do you accept? *(Expires in {timeout_secs}s)*",
                view=view
            )
            view.message = msg
        except Exception as e:
            ACTIVE_MATCH_USERS.discard(interaction.user.id)
            ACTIVE_MATCH_USERS.discard(opponent.id)
            raise e

    async def simulate_live_match(self, interaction, player_a, player_b, ovr_a, ovr_b, squad_a, squad_b, message=None, is_series_submatch: bool = False):
        try:
            # Refresh match lock for active simulation (240s)
            ACTIVE_MATCH_USERS.add(player_a.id, duration=240)
            ACTIVE_MATCH_USERS.add(player_b.id, duration=240)

            # 1. Extract players, positions, and sectoral power ratings
            inv_a = await database.get_inventory(player_a.id) or []
            inv_b = await database.get_inventory(player_b.id) or []
            inv_map = {}
            for c in (inv_a + inv_b):
                inv_map[str(c.get('id', ''))] = c

            # Preload live custom cards catalog for real-time fallback and perk sync
            catalog_map = {}
            try:
                catalog_rows = await database.fetch_all("SELECT card_name, ovr, player_data FROM custom_cards_catalog")
                for cr in (catalog_rows or []):
                    c_name = (cr.get('card_name') or '').strip().lower()
                    if c_name:
                        c_pdata = cr.get('player_data')
                        if isinstance(c_pdata, str):
                            try: c_pdata = json.loads(c_pdata)
                            except Exception: c_pdata = {}
                        catalog_map[c_name] = {
                            "ovr": cr.get('ovr'),
                            "player_data": c_pdata or {}
                        }
            except Exception as cat_err:
                catalog_map = {}

            gp_cfg = await database.get_gameplay_config()
            default_custom_boost = float(gp_cfg.get('custom_card_match_boost', 1.15))
            official_players_map = await self.get_official_players_cache()

            def extract_player_stats(pd_dict, p_name, p_pos, eff_ovr):
                """Extract authentic RenderZ stats (avgStats and detailed stats) for H2H match engine."""
                p_pos = (p_pos or 'ST').upper()
                is_gk = (p_pos == 'GK')
                p_name_clean = (p_name or '').strip().lower()
                
                # Check player_data first (for GK prefer avgGkStats)
                avg = {}
                if isinstance(pd_dict, dict):
                    avg = (pd_dict.get('avgGkStats') if is_gk else pd_dict.get('avgStats')) or pd_dict.get('avgStats') or {}
                st = pd_dict.get('stats') or {} if isinstance(pd_dict, dict) else {}

                # If avgStats is missing or has no avg1, resolve from authentic RenderZ official players cache!
                if not avg.get('avg1') and p_name_clean:
                    matched = official_players_map.get(p_name_clean)
                    if not matched:
                        for k, v in official_players_map.items():
                            if k in p_name_clean or p_name_clean in k:
                                matched = v
                                break

                    if matched:
                        base_ovr = int(matched.get('ovr') or 100)
                        ovr_delta = eff_ovr - base_ovr
                        rz_avg = (matched.get('avgGkStats') if is_gk else matched.get('avgStats')) or matched.get('avgStats') or {}
                        rz_st = matched.get('stats') or {}

                        if is_gk:
                            a1 = int(rz_avg.get('avg1') or rz_st.get('gkd') or (base_ovr + 29)) + ovr_delta
                            a2 = int(rz_avg.get('avg2') or rz_st.get('gkp') or (base_ovr + 28)) + ovr_delta
                            a3 = int(rz_avg.get('avg3') or rz_st.get('han') or (base_ovr + 28)) + ovr_delta
                            a4 = int(rz_avg.get('avg4') or rz_st.get('ref') or (base_ovr + 30)) + ovr_delta
                            a5 = int(rz_avg.get('avg5') or rz_st.get('gkk') or max(50, base_ovr + 24)) + ovr_delta
                            a6 = int(rz_avg.get('avg6') or rz_st.get('str') or rz_st.get('phy') or (base_ovr + 3)) + ovr_delta
                        else:
                            a1 = int(rz_avg.get('avg1') or rz_st.get('spd') or rz_st.get('pac') or (base_ovr + 20)) + ovr_delta
                            a2 = int(rz_avg.get('avg2') or rz_st.get('sho') or rz_st.get('fin') or (base_ovr + 20)) + ovr_delta
                            a3 = int(rz_avg.get('avg3') or rz_st.get('spa') or rz_st.get('pas') or (base_ovr + 10)) + ovr_delta
                            a4 = int(rz_avg.get('avg4') or rz_st.get('dri') or rz_st.get('agi') or (base_ovr + 20)) + ovr_delta
                            a5 = int(rz_avg.get('avg5') or rz_st.get('mrk') or rz_st.get('def') or (base_ovr - 20)) + ovr_delta
                            a6 = int(rz_avg.get('avg6') or rz_st.get('str') or rz_st.get('phy') or base_ovr) + ovr_delta
                    else:
                        a1, a2, a3, a4, a5, a6 = None, None, None, None, None, None
                else:
                    a1 = avg.get('avg1')
                    a2 = avg.get('avg2')
                    a3 = avg.get('avg3')
                    a4 = avg.get('avg4')
                    a5 = avg.get('avg5')
                    a6 = avg.get('avg6')
                
                if is_gk:
                    div = int(a1 or st.get('gkd') or (eff_ovr + 29))
                    pos_stat = int(a2 or st.get('gkp') or (eff_ovr + 28))
                    han = int(a3 or st.get('han') or (eff_ovr + 28))
                    ref = int(a4 or st.get('ref') or (eff_ovr + 30))
                    kic = int(a5 or st.get('gkk') or max(50, eff_ovr + 24))
                    phy = int(a6 or st.get('str') or st.get('phy') or (eff_ovr + 3))
                    
                    # Goalkeeper sector power: heavy emphasis on Reflexes & Diving
                    stat_rating = (ref * 0.40) + (div * 0.30) + (pos_stat * 0.20) + (han * 0.10)
                    return {
                        "is_gk": True,
                        "div": div, "pos_stat": pos_stat, "han": han, "ref": ref, "kic": kic, "phy": phy,
                        "gkd": int(st.get('gkd') or div),
                        "gkp": int(st.get('gkp') or pos_stat),
                        "ref_detail": int(st.get('ref') or ref),
                        "pac": kic, "sho": 30, "pas": kic, "dri": 40, "def_stat": 30,
                        "fin": 10, "spd": kic, "spa": kic, "mrk": 10, "stt": 10,
                        "stat_rating": stat_rating
                    }
                else:
                    # Exact empirical RenderZ average attribute deltas from over 1,800 official cards:
                    if p_pos in ['ST', 'CF']:
                        d1, d2, d3, d4, d5, d6 = 23, 24, -3, 17, -47, 5
                    elif p_pos in ['LW', 'LF']:
                        d1, d2, d3, d4, d5, d6 = 30, 17, 11, 27, -47, -8
                    elif p_pos in ['RW', 'RF']:
                        d1, d2, d3, d4, d5, d6 = 28, 16, 11, 26, -48, -11
                    elif p_pos == 'CAM':
                        d1, d2, d3, d4, d5, d6 = 19, 17, 15, 24, -33, -14
                    elif p_pos == 'CM':
                        d1, d2, d3, d4, d5, d6 = 11, 5, 19, 17, 1, 0
                    elif p_pos in ['LM', 'RM']:
                        d1, d2, d3, d4, d5, d6 = 25, 10, 14, 22, -25, -6
                    elif p_pos == 'CDM':
                        d1, d2, d3, d4, d5, d6 = 6, -13, 6, 11, 19, 16
                    elif p_pos == 'CB':
                        d1, d2, d3, d4, d5, d6 = 8, -29, -9, 1, 28, 23
                    elif p_pos in ['LB', 'LWB']:
                        d1, d2, d3, d4, d5, d6 = 21, -17, 7, 13, 17, 10
                    elif p_pos in ['RB', 'RWB']:
                        d1, d2, d3, d4, d5, d6 = 18, -25, -1, 8, 19, 12
                    else:
                        d1, d2, d3, d4, d5, d6 = 15, 10, 10, 15, 0, 5

                    pac = int(a1 or st.get('spd') or st.get('pac') or max(40, eff_ovr + d1))
                    sho = int(a2 or st.get('sho') or st.get('fin') or max(40, eff_ovr + d2))
                    pas = int(a3 or st.get('spa') or st.get('pas') or max(40, eff_ovr + d3))
                    dri = int(a4 or st.get('dri') or st.get('agi') or max(40, eff_ovr + d4))
                    def_stat = int(a5 or st.get('mrk') or st.get('stt') or st.get('def') or max(30, eff_ovr + d5))
                    phy = int(a6 or st.get('str') or st.get('phy') or max(40, eff_ovr + d6))

                    if p_pos in ['ST', 'CF', 'LF', 'RF']:
                        stat_rating = (sho * 0.45) + (pac * 0.30) + (dri * 0.15) + (phy * 0.10)
                    elif p_pos in ['LW', 'RW']:
                        stat_rating = (pac * 0.40) + (dri * 0.25) + (sho * 0.25) + (pas * 0.10)
                    elif p_pos == 'CAM':
                        stat_rating = (pas * 0.35) + (dri * 0.30) + (sho * 0.20) + (pac * 0.15)
                    elif p_pos == 'CDM':
                        stat_rating = (def_stat * 0.35) + (phy * 0.30) + (pas * 0.20) + (pac * 0.15)
                    elif p_pos in ['CM', 'LM', 'RM']:
                        stat_rating = (pas * 0.30) + (dri * 0.25) + (pac * 0.20) + (def_stat * 0.15) + (phy * 0.10)
                    elif p_pos == 'CB':
                        stat_rating = (def_stat * 0.45) + (phy * 0.35) + (pac * 0.10) + (pas * 0.10)
                    elif p_pos in ['LB', 'RB', 'LWB', 'RWB']:
                        stat_rating = (def_stat * 0.35) + (pac * 0.30) + (phy * 0.15) + (pas * 0.10) + (dri * 0.10)
                    else:
                        stat_rating = eff_ovr

                    return {
                        "is_gk": False,
                        "pac": pac, "sho": sho, "pas": pas, "dri": dri, "def_stat": def_stat, "phy": phy,
                        "fin": int(st.get('fin') or sho),
                        "spd": int(st.get('spd') or pac),
                        "spa": int(st.get('spa') or pas),
                        "mrk": int(st.get('mrk') or def_stat),
                        "stt": int(st.get('stt') or def_stat),
                        "stat_rating": stat_rating
                    }

            def get_team_sectors(squad, team_avg_ovr):
                atk, mid, defn, gk = [], [], [], []
                starters = []
                for pos_raw, p in squad.get('players', {}).items():
                    if not p: continue
                    name = p.get('name') or p.get('player_name', 'Player')
                    pos = ''.join([c for c in pos_raw if not c.isdigit()]).strip().upper()
                    name_lower = (name or '').lower()
                    
                    p_ovr = p.get('ovr', 100)
                    inv_id_str = str(p.get('inv_id', ''))
                    
                    # Apply custom card / signature card buffs directly to the player's OVR for the match engine
                    is_custom = False
                    boost_val = default_custom_boost
                    pd = {}
                    if inv_id_str in inv_map:
                        full_p = inv_map[inv_id_str]
                        # Parse inner player_data JSON if string
                        pd_raw = full_p.get('player_data')
                        if isinstance(pd_raw, str):
                            try:
                                pd = json.loads(pd_raw)
                            except Exception:
                                pd = {}
                        elif isinstance(pd_raw, dict):
                            pd = pd_raw

                        boost_val = float(pd.get('performance_boost') or full_p.get('performance_boost') or default_custom_boost)

                        pid_str = str(full_p.get('player_id', '') or pd.get('id', '')).lower()
                        src_str = (str(full_p.get('source', '') or pd.get('source', ''))).upper()
                        
                        is_custom = bool(
                            full_p.get('is_custom') or full_p.get('is_signature_box') or
                            pd.get('is_custom') or pd.get('is_signature_box') or
                            'CUSTOM' in src_str or 'SIGNATURE' in src_str or
                            pid_str.startswith('sig_') or pid_str.startswith('custom_') or
                            inv_id_str.startswith('custom_') or inv_id_str.startswith('sig_')
                        )

                    # Real-time sync fallback to live custom catalog if not marked or if catalog has newer data
                    cat_match = catalog_map.get(name_lower)
                    if cat_match:
                        is_custom = True
                        cat_pd = cat_match.get('player_data', {})
                        if cat_pd:
                            # Inherit buffed_ovr and perks from live catalog if missing or updated
                            if not pd.get('buffed_ovr') and cat_pd.get('buffed_ovr'):
                                pd['buffed_ovr'] = cat_pd.get('buffed_ovr')
                            if not pd.get('avgStats') and cat_pd.get('avgStats'):
                                pd['avgStats'] = cat_pd.get('avgStats')
                            if cat_pd.get('perks'):
                                pd['perks'] = cat_pd.get('perks')

                    base_ovr = int(p.get('ovr', 100))
                    effective_ovr = base_ovr

                    # Match performance OVR directly from panel (buffed_ovr / performance_ovr)
                    card_perks = {}
                    if is_custom:
                        card_buffed_ovr = (
                            (pd.get('buffed_ovr') or pd.get('performance_ovr')) if isinstance(pd, dict) else None
                        ) or (full_p.get('buffed_ovr') if 'full_p' in locals() and isinstance(full_p, dict) else None)
                        
                        if card_buffed_ovr:
                            try:
                                effective_ovr = int(card_buffed_ovr)
                            except Exception:
                                effective_ovr = base_ovr
                        else:
                            effective_ovr = base_ovr

                        # Parse custom perks
                        raw_perks = pd.get('perks') if isinstance(pd, dict) else (full_p.get('perks') if 'full_p' in locals() and isinstance(full_p, dict) else None)
                        if isinstance(raw_perks, str):
                            try:
                                card_perks = json.loads(raw_perks)
                            except Exception:
                                card_perks = {}
                        elif isinstance(raw_perks, dict):
                            card_perks = raw_perks

                    # Extract authentic RenderZ stats & role ratings
                    p_stats = extract_player_stats(pd, name, pos, effective_ovr)

                    # Store clean base_ovr for stats, records, and displays;
                    # use authentic RenderZ stat_rating and stats for match physics
                    entry = {
                        "name": name,
                        "pos": pos,
                        "raw_pos": pos_raw,
                        "ovr": base_ovr,
                        "effective_ovr": effective_ovr,
                        "stat_rating": p_stats["stat_rating"],
                        "stats": p_stats,
                        "pac": p_stats["pac"],
                        "sho": p_stats["sho"],
                        "pas": p_stats["pas"],
                        "dri": p_stats["dri"],
                        "def_stat": p_stats["def_stat"],
                        "phy": p_stats["phy"],
                        "fin": p_stats.get("fin", p_stats["sho"]),
                        "spd": p_stats.get("spd", p_stats["pac"]),
                        "spa": p_stats.get("spa", p_stats["pas"]),
                        "is_custom": is_custom,
                        "boost_val": boost_val,
                        "perks": card_perks
                    }
                    starters.append(entry)
                    if pos in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF']:
                        atk.append(entry)
                    elif pos in ['CAM', 'CM', 'CDM', 'LM', 'RM']:
                        mid.append(entry)
                    elif pos in ['CB', 'LB', 'RB', 'LWB', 'RWB']:
                        defn.append(entry)
                    elif pos == 'GK':
                        gk.append(entry)
                    else:
                        mid.append(entry)
                
                # Sector powers calculated directly from individual players using their RenderZ stat ratings
                atk_p = sum(p.get('stat_rating', p['effective_ovr']) for p in atk) / len(atk) if atk else team_avg_ovr
                mid_p = sum(p.get('stat_rating', p['effective_ovr']) for p in mid) / len(mid) if mid else team_avg_ovr
                def_p = sum(p.get('stat_rating', p['effective_ovr']) for p in defn) / len(defn) if defn else team_avg_ovr
                
                # Goalkeeper power directly from keeper's RenderZ reflexes & diving
                gk_p = gk[0].get('stat_rating', gk[0]['effective_ovr']) if gk else team_avg_ovr

                # Dynamic Custom Perks applied in real time from panel configuration
                for p_entry in starters:
                    p_perks = p_entry.get('perks', {})
                    if not p_perks or not p_perks.get('enabled'):
                        continue

                    p_pos = p_entry.get('pos', '')
                    # 1. Custom Sector Surge (+1 to +10)
                    surge = float(p_perks.get('sector_surge') or 0)
                    if surge > 0:
                        if p_pos in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF']:
                            atk_p += surge
                        elif p_pos in ['CAM', 'CM', 'CDM', 'LM', 'RM']:
                            mid_p += surge
                        elif p_pos in ['CB', 'LB', 'RB', 'LWB', 'RWB']:
                            def_p += surge
                        elif p_pos == 'GK':
                            gk_p += surge

                    # 2. Speed Demon (+3 Attack Power)
                    if p_perks.get('speed_demon'):
                        atk_p += 3.0

                    # 3. Maestro Playmaker (+3 Midfield Power)
                    if p_perks.get('playmaker'):
                        mid_p += 3.0

                    # 4. Iron Fortress (+3 Defense Power)
                    if p_perks.get('iron_fortress'):
                        def_p += 3.0

                    # 5. The Wall (+5 Goalkeeping Power)
                    if p_perks.get('the_wall') and p_pos == 'GK':
                        gk_p += 5.0

                    # 6. Aura Dominance (+2 to all sectors)
                    if p_perks.get('aura_dominance'):
                        atk_p += 2.0
                        mid_p += 2.0
                        def_p += 2.0

                tactic = squad.get('tactic', 'Tiki-Taka')
                formation = squad.get('formation', '4-3-3 Flat')
                theme = squad.get('theme', 'default')
                t_data = TACTICS.get(tactic, TACTICS["Tiki-Taka"])
                is_synergy = any(f.lower() in formation.lower() for f in t_data.get('best_formations', []))
                
                # Apply tactical chemistry boost if formation matches tactic
                if is_synergy:
                    if tactic == "Tiki-Taka":
                        mid_p += 5.0
                    elif tactic == "Gegenpressing":
                        atk_p += 4.5
                        mid_p += 3.0
                    elif tactic == "Wing Play":
                        atk_p += 4.5
                    elif tactic == "Counter-Attack":
                        def_p += 4.5
                        atk_p += 2.0
                    elif tactic == "Kick and Rush":
                        atk_p += 4.0
                    elif tactic == "Park the Bus":
                        def_p += 3.5
                        gk_p += 2.0
                        atk_p -= 3.0
                        mid_p -= 2.0
                    elif tactic == "Vertical Tiki-Taka":
                        mid_p += 4.0
                        atk_p += 3.5
                    elif tactic == "Total Football":
                        atk_p += 3.0
                        mid_p += 3.5
                        def_p += 3.0
                    elif tactic == "Catenaccio":
                        def_p += 6.5
                        gk_p += 4.5
                    elif tactic == "Heavy Metal Football":
                        atk_p += 5.5
                        mid_p += 2.5
                    elif tactic == "Direct Play":
                        atk_p += 4.0
                        mid_p += 2.5
                        def_p += 2.0

                # Apply Stadium Turf Perks (Home Venue Advantage)
                stadium_name = "⚡ Neon Stadium"
                if theme == "snow":
                    def_p += 2.0
                    stadium_name = "❄️ Frostbite Arena"
                elif theme == "lava":
                    atk_p += 3.5
                    stadium_name = "🌋 Volcanic Caldera"
                elif theme == "cyberpunk":
                    mid_p += 3.0
                    stadium_name = "🤖 Neo-Tokyo Cyber City"
                elif theme == "desert":
                    def_p += 4.0
                    gk_p += 2.0
                    stadium_name = "🌙 Arabian Oasis Coliseum"
                elif theme == "galaxy":
                    atk_p += 3.0
                    mid_p += 3.0
                    def_p += 3.0
                    gk_p += 1.5
                    stadium_name = "🌌 Celestial Orbit Stadium"
                elif theme == "gold":
                    atk_p += 6.0
                    mid_p += 6.0
                    def_p += 6.0
                    gk_p += 2.5
                    stadium_name = "👑 Champions Royal Colosseum"
                elif theme == "bernabeu":
                    atk_p += 7.0
                    mid_p += 5.0
                    stadium_name = "⚪ Santiago Bernabéu"
                elif theme == "campnou":
                    mid_p += 8.0
                    atk_p += 5.0
                    stadium_name = "🔵🔴 Spotify Camp Nou"
                elif theme == "oldtrafford":
                    atk_p += 7.0
                    def_p += 5.0
                    stadium_name = "🔴 Old Trafford"
                elif theme == "anfield":
                    atk_p += 7.5
                    def_p += 5.5
                    stadium_name = "🔥 Anfield"
                elif theme == "sansiro":
                    def_p += 8.0
                    mid_p += 4.0
                    gk_p += 2.5
                    stadium_name = "⚔️ San Siro"
                elif theme == "allianz":
                    atk_p += 7.5
                    mid_p += 5.0
                    stadium_name = "🔴 Allianz Arena"
                elif theme == "maracana":
                    atk_p += 8.0
                    mid_p += 5.0
                    stadium_name = "🇧🇷 Maracanã Stadium"
                elif theme == "wembley":
                    atk_p += 6.0
                    mid_p += 6.0
                    def_p += 6.0
                    stadium_name = "🦁 Wembley Stadium"

                return {
                    "atk": atk, "mid": mid, "defn": defn, "gk": gk, "starters": starters,
                    "atk_p": atk_p, "mid_p": mid_p, "def_p": def_p, "gk_p": gk_p,
                    "tactic": tactic, "formation": formation, "is_synergy": is_synergy,
                    "theme": theme, "stadium_name": stadium_name
                }

            s_a = get_team_sectors(squad_a, ovr_a)
            s_b = get_team_sectors(squad_b, ovr_b)

            starters_a = s_a["starters"]
            starters_b = s_b["starters"]
            atk_a = [p['name'] for p in s_a["atk"]] or [p['name'] for p in starters_a]
            mid_a = [p['name'] for p in s_a["mid"]] or [p['name'] for p in starters_a]
            def_a = [p['name'] for p in s_a["defn"]] or [p['name'] for p in starters_a]
            gk_a = [p['name'] for p in s_a["gk"]] or ["Goalkeeper"]

            atk_b = [p['name'] for p in s_b["atk"]] or [p['name'] for p in starters_b]
            mid_b = [p['name'] for p in s_b["mid"]] or [p['name'] for p in starters_b]
            def_b = [p['name'] for p in s_b["defn"]] or [p['name'] for p in starters_b]
            gk_b = [p['name'] for p in s_b["gk"]] or ["Goalkeeper"]

            # Midfield Battle & Stadium Possession Perks
            mid_diff = s_a["mid_p"] - s_b["mid_p"]
            possession_a = int(50 + (mid_diff * 1.8) + random.randint(-2, 2))
            if s_a.get('theme') == 'campnou':
                possession_a += 6
            if s_b.get('theme') == 'campnou':
                possession_a -= 6
            possession_a = max(30, min(70, possession_a))
            possession_b = 100 - possession_a

            def format_match_player_name(p_name: str) -> str:
                if not p_name:
                    return ""
                if "blank" in str(p_name).strip().lower():
                    return "~𝔹𝕃𝔸ℕ𝕂"
                return str(p_name)

            def calc_full_team_ratings(starters, is_winning_team, is_draw_match, goals_conceded, goals_scored, team_goals, team_assists, team_saves):
                ratings = []
                for s in starters:
                    p_name = s['name']
                    pos = s['pos']
                    goals = team_goals.get(p_name, 0)
                    assists = team_assists.get(p_name, 0)
                    
                    base = 6.8 + random.uniform(-0.2, 0.3)
                    stat_r = float(s.get('stat_rating', s.get('effective_ovr', s['ovr'])))
                    base += (stat_r - 100.0) * 0.015

                    if is_winning_team: base += 0.7
                    elif is_draw_match: base += 0.2
                    else: base -= 0.5
                    
                    base += goals * 1.3 + assists * 0.7
                    if pos == 'GK':
                        base += team_saves * 0.2
                        if goals_conceded == 0: base += 0.8
                    elif pos in ['CB', 'LB', 'RB', 'LWB', 'RWB']:
                        if goals_conceded == 0: base += 0.6
                        base += random.uniform(-0.1, 0.3)
                    elif pos in ['CAM', 'CM', 'CDM', 'LM', 'RM']:
                        base += random.uniform(-0.1, 0.4)
                    if s.get('is_custom'):
                        base += 0.8
                            
                    rating = round(min(10.0, max(5.5, base)), 1)
                    ratings.append({"name": p_name, "pos": pos, "rating": rating, "goals": goals, "assists": assists, "ovr": s['ovr'], "is_custom": s.get('is_custom', False)})
                return ratings

            # Threat and goal probability calculations based on squad sectors & tactical synergy
            threat_a = (s_a["atk_p"] * 0.60 + s_a["mid_p"] * 0.40) - (s_b["def_p"] * 0.60 + s_b["gk_p"] * 0.40)
            threat_b = (s_b["atk_p"] * 0.60 + s_b["mid_p"] * 0.40) - (s_a["def_p"] * 0.60 + s_a["gk_p"] * 0.40)

            # Goalkeeper resistance factor based on opponent keeper's RenderZ reflexes & diving
            gk_resist_b = max(-0.08, min(0.08, (s_b["gk_p"] - s_a["atk_p"]) * 0.004))
            gk_resist_a = max(-0.08, min(0.08, (s_a["gk_p"] - s_b["atk_p"]) * 0.004))

            # Balanced exciting chances (5 to 8 chances per team)
            chances_a = max(4, int(5 + (threat_a * 0.15) + random.randint(0, 2)))
            chances_b = max(4, int(5 + (threat_b * 0.15) + random.randint(0, 2)))

            goals_a = 0
            for _ in range(chances_a):
                p_score = 0.38 + (threat_a * 0.015) - gk_resist_b + random.uniform(-0.03, 0.03)
                if random.random() < max(0.16, min(0.60, p_score)):
                    goals_a += 1

            goals_b = 0
            for _ in range(chances_b):
                p_score = 0.38 + (threat_b * 0.015) - gk_resist_a + random.uniform(-0.03, 0.03)
                if random.random() < max(0.16, min(0.60, p_score)):
                    goals_b += 1

            # Realistic exciting scoreline cap: 5 goals max (allowing thrillers like 4-3, 5-4, 5-3, 3-2)
            goals_a = min(5, goals_a)
            goals_b = min(5, goals_b)

            # Late Drama Roll: 35% chance for an 88'-90' thriller goal if match is tied or 1-goal gap
            late_drama = random.random() < 0.35
            if late_drama:
                if goals_a == goals_b and random.random() < 0.60:
                    # Someone grabs a dramatic 89' winner!
                    if random.random() < (0.5 + (threat_a - threat_b) * 0.02):
                        goals_a += 1
                    else:
                        goals_b += 1
                elif abs(goals_a - goals_b) == 1 and random.random() < 0.45:
                    # Trailing team grabs a last-gasp 90' equalizer!
                    if goals_a < goals_b:
                        goals_a += 1
                    else:
                        goals_b += 1

            # Distribute goals across 90 minutes with positional roles (attackers, midfielders, defenders)
            assists_pool_a = [p['name'] for p in starters_a if p['pos'] in ['CAM', 'CM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF']]
            assists_pool_b = [p['name'] for p in starters_b if p['pos'] in ['CAM', 'CM', 'LM', 'RM', 'LW', 'RW', 'ST', 'CF']]
            
            # Boost playmakers in the assists pool
            for p in starters_a:
                if p.get('perks', {}).get('enabled') and p.get('perks', {}).get('playmaker'):
                    assists_pool_a.extend([p['name'], p['name']])
            for p in starters_b:
                if p.get('perks', {}).get('enabled') and p.get('perks', {}).get('playmaker'):
                    assists_pool_b.extend([p['name'], p['name']])

            team_a_assists = {}
            team_b_assists = {}

            # Outfield players only (GOALKEEPERS NEVER SCORE GOALS)
            outfield_a = [p for p in starters_a if p.get('pos') != 'GK']
            outfield_b = [p for p in starters_b if p.get('pos') != 'GK']

            # Dynamic Custom Perks for goal conversion (only when perks are enabled on the card)
            clinical_finishers_a = [
                p for p in outfield_a 
                if p.get('perks', {}).get('enabled') and p.get('perks', {}).get('clinical_finisher')
            ]
            clutch_players_a = [
                p for p in outfield_a 
                if p.get('perks', {}).get('enabled') and p.get('perks', {}).get('clutch_performer')
            ]

            all_goals = []
            for idx in range(goals_a):
                is_late = (late_drama and idx == goals_a - 1)
                if is_late and clutch_players_a and random.random() < 0.50:
                    scorer_obj = random.choice(clutch_players_a)
                    ptype = "atk" if scorer_obj.get("pos") in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF'] else "mid"
                elif clinical_finishers_a and random.random() < 0.35:
                    scorer_obj = random.choice(clinical_finishers_a)
                    ptype = "atk" if scorer_obj.get("pos") in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF'] else "mid"
                else:
                    r = random.random()
                    if r < 0.65 and s_a["atk"]:
                        cands, ptype = s_a["atk"], "atk"
                    elif r < 0.90 and s_a["mid"]:
                        cands, ptype = s_a["mid"], "mid"
                    elif s_a["defn"]:
                        cands, ptype = s_a["defn"], "def"
                    else:
                        cands, ptype = (s_a["atk"] or outfield_a), "atk"
                    cands = [p for p in cands if p.get('pos') != 'GK'] or outfield_a
                    # Weight directly by RenderZ shooting & finishing attributes
                    weights = [max(1.0, (float(p.get('fin', p.get('sho', p.get('ovr', 100)))) / 50.0) ** 3.0) for p in cands]
                    scorer_obj = random.choices(cands, weights=weights, k=1)[0]
                
                # Strict absolute guard: GKs never score
                if scorer_obj.get("pos") == "GK":
                    scorer_obj = random.choice(outfield_a)

                # If late drama, push the last goal to 88-90'
                min_g = random.randint(87, 90) if (late_drama and idx == goals_a - 1) else random.randint(7, 86)
                
                # Assign assister (75% probability if candidates exist, weighted by RenderZ passing stats)
                assister = None
                if random.random() < 0.75:
                    a_cands = [p for p in assists_pool_a if p != scorer_obj["name"]]
                    if a_cands:
                        cand_objs = [p for p in starters_a if p['name'] in a_cands and p.get('pos') != 'GK'] or starters_a
                        a_weights = [max(1.0, (float(p.get('spa', p.get('pas', p.get('ovr', 100)))) / 50.0) ** 2.5) for p in cand_objs]
                        for w_i, ap in enumerate(cand_objs):
                            if ap.get('perks', {}).get('enabled') and ap.get('perks', {}).get('playmaker'):
                                a_weights[w_i] *= 2.5
                        chosen_assister = random.choices(cand_objs, weights=a_weights, k=1)[0]
                        assister = chosen_assister['name']
                        team_a_assists[assister] = team_a_assists.get(assister, 0) + 1

                all_goals.append((player_a, min_g, scorer_obj["name"], scorer_obj.get("pos", "ST"), ptype, assister))

            clinical_finishers_b = [
                p for p in outfield_b 
                if p.get('perks', {}).get('enabled') and p.get('perks', {}).get('clinical_finisher')
            ]
            clutch_players_b = [
                p for p in outfield_b 
                if p.get('perks', {}).get('enabled') and p.get('perks', {}).get('clutch_performer')
            ]

            for idx in range(goals_b):
                is_late = (late_drama and idx == goals_b - 1)
                if is_late and clutch_players_b and random.random() < 0.50:
                    scorer_obj = random.choice(clutch_players_b)
                    ptype = "atk" if scorer_obj.get("pos") in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF'] else "mid"
                elif clinical_finishers_b and random.random() < 0.35:
                    scorer_obj = random.choice(clinical_finishers_b)
                    ptype = "atk" if scorer_obj.get("pos") in ['ST', 'LW', 'RW', 'CF', 'LF', 'RF'] else "mid"
                else:
                    r = random.random()
                    if r < 0.65 and s_b["atk"]:
                        cands, ptype = s_b["atk"], "atk"
                    elif r < 0.90 and s_b["mid"]:
                        cands, ptype = s_b["mid"], "mid"
                    elif s_b["defn"]:
                        cands, ptype = s_b["defn"], "def"
                    else:
                        cands, ptype = (s_b["atk"] or outfield_b), "atk"
                    cands = [p for p in cands if p.get('pos') != 'GK'] or outfield_b
                    # Weight directly by RenderZ shooting & finishing attributes
                    weights = [max(1.0, (float(p.get('fin', p.get('sho', p.get('ovr', 100)))) / 50.0) ** 3.0) for p in cands]
                    scorer_obj = random.choices(cands, weights=weights, k=1)[0]
                
                # Strict absolute guard: GKs never score
                if scorer_obj.get("pos") == "GK":
                    scorer_obj = random.choice(outfield_b)

                min_g = random.randint(87, 90) if (late_drama and idx == goals_b - 1) else random.randint(7, 86)
                
                # Assign assister (75% probability if candidates exist, weighted by RenderZ passing stats)
                assister = None
                if random.random() < 0.75:
                    b_cands = [p for p in assists_pool_b if p != scorer_obj["name"]]
                    if b_cands:
                        cand_objs = [p for p in starters_b if p['name'] in b_cands and p.get('pos') != 'GK'] or starters_b
                        b_weights = [max(1.0, (float(p.get('spa', p.get('pas', p.get('ovr', 100)))) / 50.0) ** 2.5) for p in cand_objs]
                        for w_i, bp in enumerate(cand_objs):
                            if bp.get('perks', {}).get('enabled') and bp.get('perks', {}).get('playmaker'):
                                b_weights[w_i] *= 2.5
                        chosen_assister = random.choices(cand_objs, weights=b_weights, k=1)[0]
                        assister = chosen_assister['name']
                        team_b_assists[assister] = team_b_assists.get(assister, 0) + 1

                all_goals.append((player_b, min_g, scorer_obj["name"], scorer_obj.get("pos", "ST"), ptype, assister))

            all_goals.sort(key=lambda x: x[1])

            scoresheet_events = []
            team_a_player_goals = {}
            team_b_player_goals = {}
            current_score_a = 0
            current_score_b = 0

            # Realistic statistics totals
            shots_on_target_a = goals_a + random.randint(3, 7)
            shots_total_a = shots_on_target_a + random.randint(4, 8)
            shots_on_target_b = goals_b + random.randint(3, 7)
            shots_total_b = shots_on_target_b + random.randint(4, 8)

            saves_a = max(0, shots_on_target_b - goals_b)
            saves_b = max(0, shots_on_target_a - goals_a)

            # Match timeline: 90 real seconds (1 second = 1 match minute) + extra stoppage time
            stoppage_ht = random.randint(1, 3)  # +1' to +3' first half stoppage
            stoppage_ft = random.randint(2, 5)  # +2' to +5' second half stoppage

            # Distribute goals into match minutes (1 to 90 + stoppage)
            # Re-adjust goal times if needed so they fall across 1-90 and stoppage
            for i, g in enumerate(all_goals):
                if late_drama and i == len(all_goals) - 1:
                    # Score in 89-90 or extra time
                    stoppage_goal_min = 90 + random.randint(1, stoppage_ft) if random.random() < 0.4 else random.randint(88, 90)
                    all_goals[i] = (g[0], stoppage_goal_min, g[2], g[3], g[4], g[5] if len(g) > 5 else None)

            def render_clock_bar(min_val: int, is_extra: bool = False, extra_min: int = 0) -> str:
                progress_capped = min(90, min_val)
                blocks = min(10, max(1, int((progress_capped / 90.0) * 10)))
                bar = "▰" * blocks + "▱" * (10 - blocks)
                if min_val == 45 and is_extra:
                    return f"`[{bar}]` ⏱️ **45+{extra_min}' ET**"
                elif min_val == 45 and not is_extra:
                    return f"`[{bar}]` ⏱️ **45' HALF TIME ☕**"
                elif min_val >= 90 and is_extra:
                    return f"`[{bar}]` ⏱️ **90+{extra_min}' STOPPAGE TIME 🔥**"
                elif min_val >= 90:
                    return f"`[{bar}]` ⏱️ **90' FULL TIME 🏁**"
                else:
                    return f"`[{bar}]` ⏱️ **{min_val}' MIN**"

            async def safe_update_ui(content=None, embed=None, view=None):
                try:
                    await interaction.edit_original_response(content=content, embed=embed, view=view)
                    return True
                except Exception:
                    if message:
                        try:
                            await message.edit(content=content, embed=embed, view=view)
                            return True
                        except Exception:
                            pass
                    return False

            stadium_display = s_a.get("stadium_name", "⚡ Neon Stadium")
            latest_events_feed = []

            # Timeline execution loop: 1 to 90 seconds (1 second = 1 match minute)
            # Plus extra stoppage time
            curr_sim_min = 1
            last_edit_time = 0

            # Construct full progression sequence of minutes:
            # 1 to 45, 45+1..45+stoppage, HT pause, 46 to 90, 90+1..90+stoppage
            minute_sequence = []
            for m in range(1, 46):
                minute_sequence.append((m, False, 0, "1st Half"))
            for em in range(1, stoppage_ht + 1):
                minute_sequence.append((45, True, em, "1st Half Extra Time"))
            minute_sequence.append((45, False, 0, "Half Time Break"))
            for m in range(46, 91):
                minute_sequence.append((m, False, 0, "2nd Half"))
            for em in range(1, stoppage_ft + 1):
                minute_sequence.append((90, True, em, "2nd Half Extra Time"))

            # Discord rate-limit safety: edit roughly every 2.5 - 3 seconds or immediately on goals / HT
            for seq_idx, (m_val, is_et, et_val, phase_label) in enumerate(minute_sequence):
                time_now = asyncio.get_event_loop().time()
                time_label = f"45+{et_val}'" if (m_val == 45 and is_et) else (f"90+{et_val}'" if (m_val == 90 and is_et) else f"{m_val}'")

                # Check if a goal happens at this exact minute
                # For regular minutes match m_val. For stoppage time match 90+et_val or 45+et_val
                effective_min = (90 + et_val) if (m_val == 90 and is_et) else ((45 + et_val) if (m_val == 45 and is_et) else m_val)
                matched_goals = [g for g in all_goals if g[1] == effective_min]

                goal_happened = False
                for g in matched_goals:
                    goal_happened = True
                    team_target, min_scored, scorer, pos, ptype = g[0], g[1], g[2], g[3], g[4]
                    assister = g[5] if len(g) > 5 else None
                    if team_target == player_a:
                        current_score_a += 1
                        team_name = player_a.display_name
                        opponent_name = player_b.display_name
                        team_a_player_goals[scorer] = team_a_player_goals.get(scorer, 0) + 1
                        player_goals_today = team_a_player_goals[scorer]
                        score_for_team = current_score_a
                        score_for_opp = current_score_b
                    else:
                        current_score_b += 1
                        team_name = player_b.display_name
                        opponent_name = player_a.display_name
                        team_b_player_goals[scorer] = team_b_player_goals.get(scorer, 0) + 1
                        player_goals_today = team_b_player_goals[scorer]
                        score_for_team = current_score_b
                        score_for_opp = current_score_a

                    scorer_disp = format_match_player_name(scorer)
                    assister_disp = format_match_player_name(assister) if assister else ""
                    is_stoppage_goal = (is_et or min_scored >= 88)

                    goal_commentary = generate_dynamic_goal_commentary(
                        time_label=time_label,
                        scorer=scorer,
                        scorer_disp=scorer_disp,
                        pos=pos,
                        ptype=ptype,
                        assister=assister,
                        assister_disp=assister_disp,
                        team_name=team_name,
                        opponent_name=opponent_name,
                        score_for_team=score_for_team,
                        score_for_opp=score_for_opp,
                        is_stoppage=is_stoppage_goal,
                        player_goals_today=player_goals_today
                    )

                    latest_events_feed.insert(0, goal_commentary)
                    assist_str = f" *(🅰️ {assister_disp})*" if assister else ""
                    scoresheet_events.append(f"⚽ **{time_label}** - **{scorer_disp}**{assist_str} ({team_name})")

                # Random key event commentary every ~6 minutes if no goal, or start of stoppage time
                if not matched_goals and (m_val % 6 == 0 or (is_et and et_val == 1)) and phase_label != "Half Time Break":
                    is_a_attack = random.random() < (possession_a / 100.0)
                    att_team_name = player_a.display_name if is_a_attack else player_b.display_name
                    atk_pool = atk_a if is_a_attack else atk_b
                    mid_pool = mid_a if is_a_attack else mid_b
                    def_pool = def_b if is_a_attack else def_a
                    gk_pool = gk_b if is_a_attack else gk_a
                    opp_mid_pool = mid_b if is_a_attack else mid_a

                    a_p = format_match_player_name(random.choice(atk_pool))
                    m_p = format_match_player_name(random.choice(mid_pool))
                    d_p = format_match_player_name(random.choice(def_pool))
                    g_p = format_match_player_name(random.choice(gk_pool))
                    om_p = format_match_player_name(random.choice(opp_mid_pool))

                    chosen_comm, event_tag = generate_dynamic_in_play_commentary(
                        time_label=time_label,
                        att_team_name=att_team_name,
                        a_p=a_p,
                        m_p=m_p,
                        d_p=d_p,
                        g_p=g_p,
                        om_p=om_p
                    )
                    latest_events_feed.insert(0, f"🎙️ *{chosen_comm}*")
                    if event_tag == "yellow":
                        carded_p = d_p if f"**{d_p}**" in chosen_comm else om_p
                        scoresheet_events.append(f"🟨 **{time_label}** - **{carded_p}** (Yellow Card)")
                    elif event_tag == "save":
                        scoresheet_events.append(f"🧤 **{time_label}** - **{g_p}** (Great Save)")

                # Keep latest events compact (top 3)
                events_display = "\n".join(latest_events_feed[:3]) if latest_events_feed else "🏁 *Intense battle for possession in midfield...*"

                # Determine if we should update Discord UI on this second
                # Always update if goal happened, or at half-time, or if >= 2.0 seconds elapsed
                time_since_edit = time_now - last_edit_time
                is_ht_break = (phase_label == "Half Time Break")
                is_last_step = (seq_idx == len(minute_sequence) - 1)

                should_update_ui = goal_happened or is_ht_break or (time_since_edit >= 2.0) or is_last_step

                if should_update_ui:
                    scoreboard = f"**{player_a.display_name}** `[ {current_score_a} - {current_score_b} ]` **{player_b.display_name}**"
                    clock_str = render_clock_bar(m_val, is_extra=is_et, extra_min=et_val)

                    live_shots_a = max(current_score_a, int(shots_total_a * (min(90, m_val) / 90.0)))
                    live_shots_b = max(current_score_b, int(shots_total_b * (min(90, m_val) / 90.0)))
                    stats_mini = f"📊 Possession: `{possession_a}%` ⬝ `{possession_b}%` | Shots: `{live_shots_a}` ⬝ `{live_shots_b}`"

                    recent_goals_str = ""
                    goals_only = [e for e in scoresheet_events if "⚽" in e]
                    if goals_only:
                        recent_goals_str = "📋 **Goals:** " + " • ".join(goals_only[-3:]) + "\n\n"

                    if is_ht_break:
                        status_footer = f"☕ **HALF TIME BREAK** • 1st Half Stoppage was +{stoppage_ht}'"
                    elif is_et:
                        status_footer = f"🔥 **+{stoppage_ft if m_val == 90 else stoppage_ht} MIN EXTRA STOPPAGE TIME ADDED!**"
                    elif m_val >= 85:
                        status_footer = "⚡ *Final minutes of regulation time! Huge tension on the pitch...*"
                    else:
                        status_footer = "⚡ *Ball in play... Match in progress!*"

                    msg_content = (
                        f"🏟️ **LIVE DIVISION RIVALS MATCH** • *{stadium_display}*\n\n"
                        f"{scoreboard}\n"
                        f"{clock_str}  •  {stats_mini}\n\n"
                        f"{recent_goals_str}"
                        f"{events_display}\n\n"
                        f"*{status_footer}*"
                    )

                    await safe_update_ui(content=msg_content, view=None)
                    last_edit_time = asyncio.get_event_loop().time()

                # Sleep 0.58 seconds per minute (1.5s for HT) for ~60 seconds total match length
                if is_ht_break:
                    await asyncio.sleep(1.5)
                else:
                    await asyncio.sleep(0.58)

            # Match winner resolution
            if current_score_a > current_score_b:
                winner = player_a
                is_a_win, is_b_win, is_draw = True, False, False
            elif current_score_b > current_score_a:
                winner = player_b
                is_a_win, is_b_win, is_draw = False, True, False
            else:
                winner = None
                is_a_win, is_b_win, is_draw = False, False, True

            possession_a = int(50 + ((s_a["mid_p"] - s_b["mid_p"]) * 1.6) + random.randint(-2, 2))
            possession_a = max(35, min(65, possession_a))
            possession_b = 100 - possession_a
            pass_acc_a = random.randint(84, 94)
            pass_acc_b = random.randint(82, 93)
            corners_a = random.randint(2, 6)
            corners_b = random.randint(2, 6)
            fouls_a = random.randint(4, 11)
            fouls_b = random.randint(4, 11)
            yellows_a = random.randint(0, min(3, fouls_a // 3))
            yellows_b = random.randint(0, min(3, fouls_b // 3))
            xg_a = round(current_score_a * 0.65 + (shots_on_target_a * 0.18) + random.uniform(0.1, 0.25), 2)
            xg_b = round(current_score_b * 0.65 + (shots_on_target_b * 0.18) + random.uniform(0.1, 0.25), 2)
            # Re-calculate accurate final ratings with actual player scores
            ratings_a = calc_full_team_ratings(starters_a, is_a_win, is_draw, current_score_b, current_score_a, team_a_player_goals, team_a_assists, saves_a)
            ratings_b = calc_full_team_ratings(starters_b, is_b_win, is_draw, current_score_a, current_score_b, team_b_player_goals, team_b_assists, saves_b)
            all_rated_final = [(r, player_a.display_name) for r in ratings_a] + [(r, player_b.display_name) for r in ratings_b]
            if all_rated_final:
                motm_entry, motm_team = max(all_rated_final, key=lambda x: (x[0].get("goals", 0) * 2 + x[0].get("assists", 0) * 1.5 + x[0].get("rating", 6.0)))
            else:
                motm_entry = {"name": "Match MVP", "rating": 8.0, "goals": 0, "assists": 0}
                motm_team = player_a.display_name

            motm_disp = format_match_player_name(motm_entry['name'])
            motm_str = f"⭐ **{motm_disp}** `({motm_entry['rating']} Rating)` — *{motm_team}*"
            # Background AI analysis task (never delays the match)
            events_summary = [f"{g[1]}' {format_match_player_name(g[2])} ({g[0].display_name})" for g in all_goals]
            ai_analysis_task = asyncio.create_task(
                ai_engine.generate_post_match_analysis(
                    player_a.display_name,
                    player_b.display_name,
                    current_score_a,
                    current_score_b,
                    motm_entry['name'],
                    motm_entry['rating'],
                    events_summary
                )
            )

            gp_cfg = await database.get_gameplay_config()
            u_data_a = await database.get_user(player_a.id)
            u_data_b = await database.get_user(player_b.id)
            fans_a = int(u_data_a.get('fans', 0))
            fans_b = int(u_data_b.get('fans', 0))
            tier_a = self.get_division_tier(fans_a, gp_cfg)
            tier_b = self.get_division_tier(fans_b, gp_cfg)

            win_coins_base = int(gp_cfg.get('match_win_coins', 100_000_000))
            draw_coins = int(gp_cfg.get('match_draw_coins', 40_000_000))
            loss_coins = int(gp_cfg.get('match_loss_coins', 20_000_000))
            win_fans = int(gp_cfg.get('match_win_fans', 12_000))
            draw_fans = int(gp_cfg.get('match_draw_fans', 3_000))
            loss_fans = int(gp_cfg.get('match_loss_fans', -6_000))
            win_xp = int(gp_cfg.get('match_win_xp', 150))

            tier_coins_a = int(tier_a.get('win_reward_coins', 0)) if tier_a else 0
            tier_coins_b = int(tier_b.get('win_reward_coins', 0)) if tier_b else 0
            calc_win_a = tier_coins_a if tier_coins_a > 0 else win_coins_base
            calc_win_b = tier_coins_b if tier_coins_b > 0 else win_coins_base
            coins_won_num_a = int(calc_win_a * 1.25) if s_a.get('theme') == 'gold' else calc_win_a
            coins_won_num_b = int(calc_win_b * 1.25) if s_b.get('theme') == 'gold' else calc_win_b

            vouchers_won_a = max(3, int(tier_a.get('win_reward_vouchers', 3))) if tier_a else 3
            vouchers_won_b = max(3, int(tier_b.get('win_reward_vouchers', 3))) if tier_b else 3

            color = discord.Color.light_grey()
            if winner is None:
                result_text = f"🤝 **IT'S A DRAW!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                fan_change_str = f"Both players gained **+{draw_fans:,} Fans**\n💰 **+{draw_coins:,} Coins** & 🎫 **+1x Draft Voucher** each"
                bonus_a_str = ""
                bonus_b_str = ""
            elif winner == player_a:
                result_text = f"🏆 **{player_a.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                color = discord.Color.green()
                fan_change_str = f"**{player_a.display_name}** gained **+{win_fans:,} Fans**\n**{player_b.display_name}** lost **{loss_fans:,} Fans** *(+20M Consolation Coins)*"
                bonus_theme = " *(👑 +25% Stadium Bonus!)*" if s_a.get('theme') == 'gold' else ""
                bonus_a_str = f"💰 **+{coins_won_num_a:,} Coins**{bonus_theme}\n🎫 **+{vouchers_won_a}x Draft Vouchers**"
                bonus_b_str = ""
            else:
                result_text = f"🏆 **{player_b.display_name} WINS!**\nFinal Score: `{current_score_a} - {current_score_b}`"
                color = discord.Color.red()
                fan_change_str = f"**{player_b.display_name}** gained **+{win_fans:,} Fans**\n**{player_a.display_name}** lost **{loss_fans:,} Fans** *(+20M Consolation Coins)*"
                bonus_theme = " *(👑 +25% Stadium Bonus!)*" if s_b.get('theme') == 'gold' else ""
                bonus_a_str = ""
                bonus_b_str = f"💰 **+{coins_won_num_b:,} Coins**{bonus_theme}\n🎫 **+{vouchers_won_b}x Draft Vouchers**"

            embed = discord.Embed(title="FULL TIME ⏱️", description=result_text, color=color)
            
            # 1. Match Score Sheet & Key Events
            sheet_text = "\n".join(scoresheet_events) if scoresheet_events else "*No goals or major incidents.*"
            if len(sheet_text) > 1024:
                sheet_text = sheet_text[:1020] + "..."
            embed.add_field(name="📋 Match Events", value=sheet_text, inline=False)
            
            # 2. Detailed Real-Life Team Match Statistics (Mobile-friendly layout)
            tactic_a_badge = f"{TACTICS.get(s_a['tactic'], {}).get('emoji', '🪄')} {s_a['tactic']}" + (" (🌟)" if s_a['is_synergy'] else "")
            tactic_b_badge = f"{TACTICS.get(s_b['tactic'], {}).get('emoji', '🪄')} {s_b['tactic']}" + (" (🌟)" if s_b['is_synergy'] else "")
            
            name_a_trunc = player_a.display_name[:14]
            name_b_trunc = player_b.display_name[:14]
            stats_content = (
                f"**{name_a_trunc}** 🆚 **{name_b_trunc}**\n"
                f"📊 **Possession:** `{possession_a}%` ⬝ `{possession_b}%`\n"
                f"🎯 **xG:** `{xg_a}` ⬝ `{xg_b}`\n"
                f"🥅 **Shots (Target):** `{shots_total_a} ({shots_on_target_a})` ⬝ `{shots_total_b} ({shots_on_target_b})`\n"
                f"🧤 **GK Saves:** `{saves_a}` ⬝ `{saves_b}`\n"
                f"📐 **Corners:** `{corners_a}` ⬝ `{corners_b}`\n"
                f"🟨 **Fouls (Cards):** `{fouls_a} ({yellows_a}🟨)` ⬝ `{fouls_b} ({yellows_b}🟨)`\n"
                f"🎯 **Pass Accuracy:** `{pass_acc_a}%` ⬝ `{pass_acc_b}%`\n"
                f"🧠 **Tactics:** `{tactic_a_badge}` ⬝ `{tactic_b_badge}`"
            )
            embed.add_field(name="📊 Match Statistics", value=stats_content, inline=False)

            # 3. Man of the Match
            embed.add_field(name="🎖️ Man of the Match", value=motm_str, inline=False)

            # 4. Full Squad Player Ratings (All 11 Starters for both teams with goals & assists)
            def format_full_ratings(r_list, assists_dict, is_team_a=True):
                lines = []
                current_team_name = player_a.display_name if is_team_a else player_b.display_name
                for r in r_list:
                    icon = "🧤" if r.get("pos") == "GK" else ("🛡️" if r.get("pos") in ['CB', 'LB', 'RB', 'LWB', 'RWB'] else ("⚡" if r.get("pos") in ['CAM', 'CM', 'CDM', 'LM', 'RM'] else "🔥"))
                    star = " ⭐" if (r.get("name") == motm_entry.get("name") and motm_team == current_team_name) else ""
                    goals_cnt = r.get('goals', 0)
                    assists_cnt = assists_dict.get(r.get('name', ''), 0)
                    
                    stats_badge = ""
                    if r.get('is_custom'):
                        stats_badge += " ⚡"
                    if goals_cnt > 0:
                        stats_badge += f" {'⚽' * goals_cnt}"
                    if assists_cnt > 0:
                        stats_badge += f" {'🅰️' * assists_cnt}"
                        
                    p_disp = format_match_player_name(r.get('name', 'Player'))
                    if len(p_disp) > 13 and not p_disp.startswith("~"):
                        p_disp = p_disp[:13]
                    lines.append(f"{icon} `[{r.get('pos', 'SUB'):<3}]` **{p_disp}** `{r.get('rating', 6.0)}`{star}{stats_badge}")
                txt = "\n".join(lines) if lines else "*No rating data*"
                return txt[:1024]

            embed.add_field(name=f"👥 {player_a.display_name} XI", value=format_full_ratings(ratings_a, team_a_assists, is_team_a=True), inline=True)
            embed.add_field(name=f"👥 {player_b.display_name} XI", value=format_full_ratings(ratings_b, team_b_assists, is_team_a=False), inline=True)

            # 5. Fans & Rewards
            embed.add_field(
                name="📈 Fans & Rewards",
                value=fan_change_str + ("\n" + bonus_a_str if bonus_a_str else "") + ("\n" + bonus_b_str if bonus_b_str else ""),
                inline=False
            )
            embed.set_footer(text="DestiFC Match Engine • Stats recorded to /club_stats & /player_stats")
            
            # PRESENT FULL TIME EMBED SAFELY
            ft_sent = await safe_update_ui(content=None, embed=embed, view=None)
            if not ft_sent:
                try:
                    await interaction.channel.send(content=f"🏁 **FULL TIME** — {player_a.mention} vs {player_b.mention}", embed=embed)
                    ft_sent = True
                except Exception as e_send:
                    print(f"[Match] Fallback channel send failed: {e_send}")

            gp_cfg = await database.get_gameplay_config()
            step_delay = float(gp_cfg.get('match_sim_step_delay_secs', 0))
            if step_delay > 0:
                await asyncio.sleep(min(step_delay, 10.0))

            # Background task: Database saves & rewards
            async def _bg_save_and_ai():
                try:
                    import time
                    now = int(time.time())
                    p = await database.get_db()
                    await p.execute('UPDATE users SET last_match_time = $1 WHERE user_id = $2 OR user_id = $3', now, player_a.id, player_b.id)

                    if winner is None:
                        await database.add_fans(player_a.id, draw_fans)
                        await database.add_fans(player_b.id, draw_fans)
                        await database.add_coins(player_a.id, draw_coins)
                        await database.add_coins(player_b.id, draw_coins)
                        await database.add_vouchers(player_a.id, 1)
                        await database.add_vouchers(player_b.id, 1)
                    elif winner == player_a:
                        await database.add_fans(player_a.id, win_fans)
                        await database.add_fans(player_b.id, loss_fans)
                        await database.add_coins(player_a.id, coins_won_num_a)
                        await database.add_coins(player_b.id, loss_coins)
                        await database.add_vouchers(player_a.id, vouchers_won_a)
                        try:
                            from cogs.achievements import increment_stat, check_and_award
                            await increment_stat(player_a.id, "matches_won")
                            await check_and_award(player_a.id)
                            from cogs.season import add_season_xp
                            await add_season_xp(player_a.id, win_xp)
                        except Exception: pass
                    else:
                        await database.add_fans(player_b.id, win_fans)
                        await database.add_fans(player_a.id, loss_fans)
                        await database.add_coins(player_b.id, coins_won_num_b)
                        await database.add_coins(player_a.id, loss_coins)
                        await database.add_vouchers(player_b.id, vouchers_won_b)
                        try:
                            from cogs.achievements import increment_stat, check_and_award
                            await increment_stat(player_b.id, "matches_won")
                            await check_and_award(player_b.id)
                            from cogs.season import add_season_xp
                            await add_season_xp(player_b.id, win_xp)
                        except Exception: pass

                    # Team A Stats (using pre-computed team_a_assists)
                    stats_list_a = []
                    for r in ratings_a:
                        p_name = r['name']
                        pos = r['pos']
                        is_df_gk = any(k in pos for k in ['GK', 'CB', 'LB', 'RB', 'LWB', 'RWB'])
                        cs = 1 if (is_df_gk and current_score_b == 0) else 0
                        y_card = 1 if (yellows_a > 0 and random.random() < 0.25) else 0
                        stats_list_a.append({
                            "player_name": p_name,
                            "position": pos,
                            "ovr": r.get('ovr', 100),
                            "goals": r.get('goals', 0),
                            "assists": team_a_assists.get(p_name, 0),
                            "clean_sheets": cs,
                            "yellow_cards": y_card,
                            "red_cards": 0,
                            "rating": r.get('rating', 6.0),
                            "is_motm": 1 if (p_name == motm_entry['name'] and motm_team == player_a.display_name) else 0
                        })
                    await database.record_player_match_stats(player_a.id, stats_list_a)

                    # Team B Stats (using pre-computed team_b_assists)
                    stats_list_b = []
                    for r in ratings_b:
                        p_name = r['name']
                        pos = r['pos']
                        is_df_gk = any(k in pos for k in ['GK', 'CB', 'LB', 'RB', 'LWB', 'RWB'])
                        cs = 1 if (is_df_gk and current_score_a == 0) else 0
                        y_card = 1 if (yellows_b > 0 and random.random() < 0.25) else 0
                        stats_list_b.append({
                            "player_name": p_name,
                            "position": pos,
                            "ovr": r.get('ovr', 100),
                            "goals": r.get('goals', 0),
                            "assists": team_b_assists.get(p_name, 0),
                            "clean_sheets": cs,
                            "yellow_cards": y_card,
                            "red_cards": 0,
                            "rating": r.get('rating', 6.0),
                            "is_motm": 1 if (p_name == motm_entry['name'] and motm_team == player_b.display_name) else 0
                        })
                    await database.record_player_match_stats(player_b.id, stats_list_b)

                    # Optional AI Pundit breakdown edit
                    try:
                        ai_text = await asyncio.wait_for(ai_analysis_task, timeout=4.0)
                        if ai_text:
                            embed.add_field(name="🎙️ AI Tactical Analysis", value=f"*{ai_text}*", inline=False)
                            await interaction.edit_original_response(embed=embed)
                    except Exception:
                        pass
                except Exception as ex:
                    print(f"[Match] Background save error: {ex}")

            asyncio.create_task(_bg_save_and_ai())
            return current_score_a, current_score_b

        except Exception as e:
            import traceback
            print(f"Error in simulate_live_match: {e}")
            traceback.print_exc()
            try:
                if message:
                    await message.edit(content=f"⚠️ **Match simulation error:** `{e}`. Match cancelled and slots cleared.", view=None)
                elif interaction:
                    await interaction.followup.send(f"⚠️ **Match simulation error:** `{e}`. Match cancelled and slots cleared.")
            except Exception:
                pass
        finally:
            if not is_series_submatch:
                ACTIVE_MATCH_USERS.discard(player_a.id)
                ACTIVE_MATCH_USERS.discard(player_b.id)

    @app_commands.command(name="leaderboard", description="View Global Leaderboards (Fans, Coins, or Vouchers)")
    @app_commands.choices(category=[
        app_commands.Choice(name="🏆 Division Rivals (Fans)", value="fans"),
        app_commands.Choice(name="💰 Cash / Coins", value="coins"),
        app_commands.Choice(name="🎫 Draft Vouchers", value="vouchers")
    ])
    async def leaderboard(self, interaction: discord.Interaction, category: str = "fans"):
        await interaction.response.defer()
        user_id = interaction.user.id
        
        if category == "coins":
            lb = await database.get_coins_leaderboard(10)
            lines = []
            top_ids = set()
            for i, row in enumerate(lb):
                uid = row['user_id']
                top_ids.add(uid)
                coins = row['coins']
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                lines.append(f"{medal} <@{uid}> — **{coins:,}** Coins 💰")
            desc = "\n".join(lines) if lines else "No ranked players yet!"
            embed = discord.Embed(title="💰 Cash / Coins Global Leaderboard", description=desc, color=discord.Color.gold())
            
            if user_id not in top_ids:
                u_data = await database.get_user(user_id)
                embed.add_field(name="📍 Your Balance", value=f"🪙 **{u_data.get('coins', 0):,}** Coins", inline=False)
            
        elif category == "vouchers":
            lb = await database.get_vouchers_leaderboard(10)
            lines = []
            top_ids = set()
            for i, row in enumerate(lb):
                uid = row['user_id']
                top_ids.add(uid)
                vouchers = row['vouchers']
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                lines.append(f"{medal} <@{uid}> — **{vouchers:,}** Vouchers 🎫")
            desc = "\n".join(lines) if lines else "No ranked players yet!"
            embed = discord.Embed(title="🎫 Draft Vouchers Global Leaderboard", description=desc, color=discord.Color.blue())
            
            if user_id not in top_ids:
                u_data = await database.get_user(user_id)
                embed.add_field(name="📍 Your Inventory", value=f"🎫 **{u_data.get('vouchers', 0):,}** Draft Vouchers", inline=False)
            
        else:
            gp_cfg = await database.get_gameplay_config()
            lb = await database.get_leaderboard(10)
            lines = []
            top_ids = set()
            for i, row in enumerate(lb):
                uid = row['user_id']
                top_ids.add(uid)
                div = self.get_division(row['fans'], gp_cfg)
                medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
                lines.append(f"{medal} <@{uid}> — **{row['fans']:,}** Fans `[{div}]`")
            desc = "\n".join(lines) if lines else "No ranked players yet!"
            embed = discord.Embed(title="🌍 Division Rivals Leaderboard", description=desc, color=discord.Color.purple())

            if user_id not in top_ids:
                user_rank_info = await database.get_user_rank(user_id)
                user_fans = user_rank_info.get('fans', 0)
                user_div = self.get_division(user_fans, gp_cfg)
                embed.add_field(
                    name="📍 Your Global Rank",
                    value=f"**Rank #{user_rank_info.get('rank', 'N/A')}** of {user_rank_info.get('total_users', 1)} • **{user_fans:,}** Fans `[{user_div}]`",
                    inline=False
                )

        await interaction.followup.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

async def setup(bot):
    await bot.add_cog(MatchCog(bot))
