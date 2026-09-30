import os
import json
import asyncio
import asyncpg
from werkzeug.utils import secure_filename
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session

app = Flask(__name__)
app.secret_key = 'destifc-admin-secret-key-change-this'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

SUPABASE_URL = "postgresql://postgres.xreebpmibnbttuhevall:MonislovesBiryani37@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

# --- AUTHENTICATION ---
ADMIN_PASSWORD = "admin"  # Change this to whatever you want your team to use

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def run_async(coro):
    """Run an async function synchronously."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

async def _pg_exec(query, *args):
    conn = await asyncpg.connect(SUPABASE_URL)
    try:
        return await conn.execute(query, *args)
    finally:
        await conn.close()

async def _pg_fetch(query, *args):
    conn = await asyncpg.connect(SUPABASE_URL)
    try:
        return await conn.fetch(query, *args)
    finally:
        await conn.close()

async def _pg_fetchval(query, *args):
    conn = await asyncpg.connect(SUPABASE_URL)
    try:
        return await conn.fetchval(query, *args)
    finally:
        await conn.close()

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('Successfully logged in!', 'success')
            return redirect(request.args.get('next') or url_for('index'))
        else:
            flash('Incorrect password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/custom_cards', methods=['GET', 'POST'])
@login_required
def custom_cards():
    if request.method == 'POST':
        name = request.form.get('name')
        ovr = request.form.get('ovr')
        position = request.form.get('position')
        qty = int(request.form.get('quantity', 1))
        in_drafts = request.form.get('in_drafts') == 'on'
        
        file = request.files.get('card_image')
        if not file or file.filename == '':
            flash('No image selected for the custom card.', 'error')
            return redirect(request.url)
            
        if file and file.filename.endswith('.webp'):
            filename = secure_filename(f"{name.lower().replace(' ', '_')}_{ovr}.webp")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            player_data = {
                "player_name": name,
                "cardName": name,
                "rating": int(ovr),
                "position": position,
                "custom_image_path": filepath,
                "id": f"custom_{name}_{ovr}"
            }
            
            if in_drafts:
                run_async(_pg_exec('INSERT INTO custom_draft_cards (player_data) VALUES ($1)', json.dumps(player_data)))
                
            flash(f'Custom card {name} ({ovr}) added successfully to Supabase!', 'success')
            return redirect(url_for('custom_cards'))
        else:
            flash('Only .webp images are supported.', 'error')
            
    return render_template('custom_card.html')

@app.route('/database')
@login_required
def database_view():
    search = request.args.get('search', '')
    
    custom_rows = run_async(_pg_fetch('SELECT * FROM custom_draft_cards ORDER BY id DESC LIMIT 50'))
    custom_cards = [dict(r) for r in custom_rows]
    
    total_cards = run_async(_pg_fetchval('SELECT COUNT(*) FROM inventory')) or 0
    total_users = run_async(_pg_fetchval('SELECT COUNT(*) FROM users')) or 0
    
    return render_template('database.html', custom_cards=custom_cards, total_cards=total_cards, total_users=total_users, search=search)

@app.route('/formation', methods=['GET', 'POST'])
@login_required
def formation_editor():
    if request.method == 'POST':
        formation_name = request.form.get('formation_name')
        positions_json = request.form.get('positions_json')
        
        run_async(_pg_exec(
            'INSERT INTO formation_layouts (formation_name, positions_json) VALUES ($1, $2) ON CONFLICT (formation_name) DO UPDATE SET positions_json = $2',
            formation_name, positions_json
        ))
        flash('Formation updated successfully in Supabase!', 'success')
        return redirect(url_for('formation_editor'))
        
    rows = run_async(_pg_fetch('SELECT * FROM formation_layouts'))
    formations = [dict(r) for r in rows]
    return render_template('formation.html', formations=formations)

@app.route('/api/formation/<name>')
def get_formation(name):
    row = run_async(_pg_fetch('SELECT positions_json FROM formation_layouts WHERE formation_name = $1', name))
    if row:
        return jsonify(json.loads(row[0]['positions_json']))
    return jsonify({})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
