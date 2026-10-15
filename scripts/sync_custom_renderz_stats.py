import asyncio
import asyncpg
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def sync_custom_stats():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # 1. Update signature_box_config for Sergio Busquets
    sig_rows = await conn.fetch('SELECT id, signature_card_data FROM signature_box_config;')
    for sr in sig_rows:
        sc = sr['signature_card_data']
        if isinstance(sc, str): sc = json.loads(sc)
        c_name = sc.get('cardName') or sc.get('player_name') or ''
        if 'busquets' in c_name.lower():
            ovr = sc.get('rating') or 124
            # Busquets RenderZ deltas: PAC -1, SHO -20, PAS +15, DRI +9, DEF +6, PHY -5
            busquets_avg = {
                'avg1': ovr - 1,   # 123
                'avg2': ovr - 20,  # 104
                'avg3': ovr + 15,  # 139
                'avg4': ovr + 9,   # 133
                'avg5': ovr + 6,   # 130
                'avg6': ovr - 5,   # 119
            }
            sc['avgStats'] = busquets_avg
            await conn.execute(
                'UPDATE signature_box_config SET signature_card_data = $1 WHERE id = $2',
                json.dumps(sc), sr['id']
            )
            print(f'✅ Updated signature_box_config for {c_name}: {busquets_avg}')

    # 2. Update custom_cards_catalog
    custom_rows = await conn.fetch('SELECT id, card_name, ovr, player_data FROM custom_cards_catalog;')
    for cr in custom_rows:
        pd = cr['player_data']
        if isinstance(pd, str): pd = json.loads(pd)
        name = cr['card_name'].lower()
        ovr = cr['ovr'] or pd.get('rating') or 120
        pos = (pd.get('position') or 'ST').upper()
        
        if 'lewandowski' in name:
            # Lewandowski RenderZ deltas: PAC +24, SHO +26, PAS -7, DRI +20, DEF -58, PHY +11
            stats_avg = {'avg1': ovr + 24, 'avg2': ovr + 26, 'avg3': ovr - 7, 'avg4': ovr + 20, 'avg5': ovr - 58, 'avg6': ovr + 11}
        elif pos == 'LB':
            stats_avg = {'avg1': ovr + 21, 'avg2': ovr - 17, 'avg3': ovr + 7, 'avg4': ovr + 13, 'avg5': ovr + 17, 'avg6': ovr + 10}
        elif pos == 'RB':
            stats_avg = {'avg1': ovr + 18, 'avg2': ovr - 25, 'avg3': ovr - 1, 'avg4': ovr + 8, 'avg5': ovr + 19, 'avg6': ovr + 12}
        elif pos == 'CAM':
            stats_avg = {'avg1': ovr + 19, 'avg2': ovr + 17, 'avg3': ovr + 15, 'avg4': ovr + 24, 'avg5': ovr - 33, 'avg6': ovr - 14}
        else: # ST
            stats_avg = {'avg1': ovr + 23, 'avg2': ovr + 24, 'avg3': ovr - 3, 'avg4': ovr + 17, 'avg5': ovr - 47, 'avg6': ovr + 5}
            
        pd['avgStats'] = stats_avg
        await conn.execute(
            'UPDATE custom_cards_catalog SET player_data = $1 WHERE id = $2',
            json.dumps(pd), cr['id']
        )
        print(f'✅ Updated custom_cards_catalog for {cr["card_name"]}: {stats_avg}')

    # 3. Update inventory for custom/signature cards without avgStats
    inv_rows = await conn.fetch('SELECT id, player_name, ovr, position, player_data FROM inventory WHERE player_data IS NOT NULL;')
    updated_inv = 0
    for ir in inv_rows:
        pd = ir['player_data']
        if isinstance(pd, str):
            try: pd = json.loads(pd)
            except: continue
        if not pd.get('avgStats'):
            p_name = (ir['player_name'] or '').lower()
            ovr = ir['ovr'] or 120
            pos = (ir['position'] or pd.get('position') or 'ST').upper()
            
            if 'busquets' in p_name:
                avg = {'avg1': ovr - 1, 'avg2': ovr - 20, 'avg3': ovr + 15, 'avg4': ovr + 9, 'avg5': ovr + 6, 'avg6': ovr - 5}
            elif 'lewandowski' in p_name:
                avg = {'avg1': ovr + 24, 'avg2': ovr + 26, 'avg3': ovr - 7, 'avg4': ovr + 20, 'avg5': ovr - 58, 'avg6': ovr + 11}
            elif 'yashin' in p_name or pos == 'GK':
                avg = {'avg1': ovr + 32, 'avg2': ovr + 31, 'avg3': ovr + 24, 'avg4': ovr + 32, 'avg5': ovr + 12, 'avg6': ovr + 13}
                pd['avgGkStats'] = avg
            elif pos == 'LB':
                avg = {'avg1': ovr + 21, 'avg2': ovr - 17, 'avg3': ovr + 7, 'avg4': ovr + 13, 'avg5': ovr + 17, 'avg6': ovr + 10}
            elif pos == 'RB':
                avg = {'avg1': ovr + 18, 'avg2': ovr - 25, 'avg3': ovr - 1, 'avg4': ovr + 8, 'avg5': ovr + 19, 'avg6': ovr + 12}
            elif pos == 'CAM':
                avg = {'avg1': ovr + 19, 'avg2': ovr + 17, 'avg3': ovr + 15, 'avg4': ovr + 24, 'avg5': ovr - 33, 'avg6': ovr - 14}
            elif pos in ['LW', 'LF']:
                avg = {'avg1': ovr + 30, 'avg2': ovr + 17, 'avg3': ovr + 11, 'avg4': ovr + 27, 'avg5': ovr - 47, 'avg6': ovr - 8}
            elif pos in ['RW', 'RF']:
                avg = {'avg1': ovr + 28, 'avg2': ovr + 16, 'avg3': ovr + 11, 'avg4': ovr + 26, 'avg5': ovr - 48, 'avg6': ovr - 11}
            else:
                avg = {'avg1': ovr + 23, 'avg2': ovr + 24, 'avg3': ovr - 3, 'avg4': ovr + 17, 'avg5': ovr - 47, 'avg6': ovr + 5}
                
            pd['avgStats'] = avg
            await conn.execute(
                'UPDATE inventory SET player_data = $1 WHERE id = $2',
                json.dumps(pd), ir['id']
            )
            updated_inv += 1
            
    print(f'✅ Backfilled {updated_inv} inventory cards with authentic RenderZ stats!')
    
    # Signal cache flush
    await conn.execute("INSERT INTO portal_jobs (job_type, payload, status) VALUES ('SIGNAL_FLUSH_CACHES', '{}', 'pending')")
    print('✅ Triggered SIGNAL_FLUSH_CACHES')
    await conn.close()

if __name__ == '__main__':
    asyncio.run(sync_custom_stats())
