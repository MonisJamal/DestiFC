# DestiFC Bot - Project Plan

## Overview
DestiFC is a Discord bot designed to bring the EA Sports FC Mobile experience directly to Discord. It aims to provide features similar to the MadridistaaFC bot, allowing users to draft teams, complete quests, earn rewards, and compete with others.

## Core Features
1. **Player Database**: A robust system to store and retrieve FC Mobile player cards (stats, ratings, images).
2. **Draft System**: Users can open drafts (e.g., current in-game events) to pull player cards.
3. **Quests & Vouchers**: A quest system where users can perform "research" or daily activities to earn draft vouchers.
4. **Squad Building**: Users can assemble their drafted players into a starting XI.
5. **PvP Matches**: A simulated match engine that compares user teams and determines a winner based on player stats and RNG.

## Tech Stack (Recommended)
* **Language**: Python (discord.py) or JavaScript (discord.js)
* **Database**: SQLite (for getting started quickly) or PostgreSQL (for long-term scale)
* **Data Source**: Since we cannot directly access MadridistaaFC's private database, we will need to build our own player database, potentially by scraping sites like FIFARenderZ or using a static JSON dataset of FC Mobile players.

## Implementation Phases
* **Phase 1: Setup & Bot Foundation**
  * Create the Discord Bot on the Developer Portal.
  * Setup project structure and basic commands (e.g., `/ping`, `/help`).
* **Phase 2: Database & Economy**
  * Setup the database for Users, Inventory, and Player Cards.
  * Implement the Draft Voucher and Quest economy (`/research`, `/daily`).
* **Phase 3: The Draft System**
  * Add player data to the DB.
  * Implement the `/draft` command with weighted RNG (pack opening simulator).
* **Phase 4: Squad Building & PvP**
  * Implement `/team view` and `/team set` commands.
  * Build the PvP simulation engine (`/play @user`).

## Next Steps
1. Choose the programming language (Python or Node.js).
2. Gather initial FC Mobile player data.
3. Obtain a Discord Bot Token.
