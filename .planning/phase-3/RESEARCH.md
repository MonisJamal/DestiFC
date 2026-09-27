# Phase 3: True Draft Engine Research

## 1. Pack Probabilities & Draft Pools
There is **no public data** on exact drop weights or live pack odds from EA Sports or FIFARenderZ. The pack simulator on RenderZ's mobile app handles all RNG server-side and does not expose the probabilities to the web. Their "Roster Rumble" draft mode is also mobile-exclusive with no web API.

## 2. Emulating Live Pools (Programs)
RenderZ groups all cards by "Program" using the `source` field (e.g., `PROGRAM_ANN27` for Anniversary, `PROGRAM_TOTY26` for TOTY). We can emulate live packs by querying the RenderZ Elasticsearch API for specific `source` tags.

## 3. Emulating Drop Weights (Weighted RNG)
Since we cannot fetch exact odds, we must build a standard gacha tier list. We will define probabilities (e.g., 120+ OVR = 1%, 115-119 OVR = 9%, <115 OVR = 90%) and randomly roll a tier. Once a tier is selected, we query the RenderZ API for a player in that specific OVR range from the active Program.
