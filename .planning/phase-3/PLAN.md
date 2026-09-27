# Phase 3: True Draft Engine Plan

## Objective
Upgrade the `/draft` command from a generic random pull to a realistic pack opening experience using Program filters and weighted probabilities.

## Step-by-Step Implementation

### Step 1: Upgrade `renderz_api.py`
1. Add a new function `query_players_by_program(program_code: str, min_rating: int, max_rating: int)`.
2. This function will build an Elasticsearch query matching the `source` field and filtering by the `rating` range.

### Step 2: Implement Weighted RNG in `cogs/draft.py`
1. Define a loot table with probabilities for different OVR ranges.
   - Example Tiers:
     - **Walkout (120+ OVR):** 2%
     - **Elite (115-119 OVR):** 18%
     - **Gold (110-114 OVR):** 80%
2. When a user runs `/draft`, roll a random number from 1-100 to determine which tier they hit.
3. Call `query_players_by_program` (e.g., using a live program like Anniversary `PROGRAM_ANN27` or a combined pool) with the min/max rating of the chosen tier.
4. If the query returns multiple players in that tier, pick one at random.
5. Generate the card image and send it to the user.

### Step 3: Verify
1. Run `/draft` multiple times in Discord to ensure the vast majority of pulls are Gold tier, with rare Elite and Walkout pulls.
2. Ensure the generated cards correctly display their Program backgrounds.
