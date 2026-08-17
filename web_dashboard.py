from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import aiosqlite
import asyncio
from datetime import datetime, timezone
import json
import secrets
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

DB_PATH = "db/dashboard_system.db"

def get_db():
    """Get database connection"""
    return aiosqlite.connect(DB_PATH)

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        token = request.cookies.get('auth_token')
        if not token:
            return redirect(url_for('login'))
        
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT user_id, expires_at FROM auth_tokens WHERE token = ? AND is_valid = 1",
                (token,)
            )
            result = await cursor.fetchone()
            
            if not result:
                return redirect(url_for('login'))
            
            user_id, expires_at = result
            
            # Check if expired
            if datetime.now(timezone.utc) > datetime.fromisoformat(expires_at):
                return redirect(url_for('login'))
        
        return await f(user_id, *args, **kwargs)
    
    return decorated_function

@app.route('/')
async def index():
    """Home page"""
    return render_template('index.html')

@app.route('/api/commands')
async def api_commands():
    """API endpoint for command catalog"""
    try:
        from pathlib import Path
        catalog_path = Path("data/command_catalog.json")
        
        if catalog_path.exists():
            import json
            with open(catalog_path, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            return jsonify(catalog)
        else:
            # Fallback if catalog doesn't exist yet
            return jsonify({
                "generated_at": "",
                "command_count": 0,
                "commands": [],
                "loader": [],
                "error": "Command catalog not generated yet. Bot needs to run first."
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/login')
async def login():
    """Login page"""
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
async def authenticate():
    """Authenticate user with token"""
    token = request.form.get('token')
    
    if not token:
        return render_template('login.html', error='Token is required')
    
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT user_id, expires_at FROM auth_tokens WHERE token = ? AND is_valid = 1",
            (token,)
        )
        result = await cursor.fetchone()
        
        if not result:
            return render_template('login.html', error='Invalid token')
        
        user_id, expires_at = result
        
        # Check if expired
        if datetime.now(timezone.utc) > datetime.fromisoformat(expires_at):
            return render_template('login.html', error='Token expired')
        
        # Get user info
        cursor = await db.execute(
            "SELECT username, discriminator, avatar_url FROM user_profiles WHERE user_id = ?",
            (user_id,)
        )
        user_data = await cursor.fetchone()
        
        if not user_data:
            return render_template('login.html', error='User profile not found')
    
    response = redirect(url_for('dashboard'))
    response.set_cookie('auth_token', token, max_age=86400)  # 24 hours
    return response

@app.route('/dashboard')
@require_auth
async def dashboard(user_id):
    """Main dashboard"""
    async with get_db() as db:
        # Get user profile
        cursor = await db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,)
        )
        profile = await cursor.fetchone()
        
        # Get user stats
        cursor = await db.execute(
            "SELECT * FROM user_stats WHERE user_id = ?",
            (user_id,)
        )
        stats = await cursor.fetchone()
        
        # Get achievements
        cursor = await db.execute(
            "SELECT achievement_name, achievement_description, achievement_icon FROM user_achievements WHERE user_id = ? ORDER BY unlocked_at DESC LIMIT 5",
            (user_id,)
        )
        achievements = await cursor.fetchall()
        
        # Get social connections
        cursor = await db.execute(
            "SELECT * FROM social_connections WHERE user_id = ?",
            (user_id,)
        )
        social = await cursor.fetchone()
        
        # Get global rank
        cursor = await db.execute(
            "SELECT user_id, xp FROM user_profiles ORDER BY xp DESC"
        )
        all_users = await cursor.fetchall()
        
        user_rank = None
        for i, (uid, xp) in enumerate(all_users):
            if uid == user_id:
                user_rank = i + 1
                break
    
    return render_template('dashboard.html', 
                          profile=profile, 
                          stats=stats, 
                          achievements=achievements,
                          social=social,
                          user_rank=user_rank,
                          total_users=len(all_users))

@app.route('/profile/<user_id>')
async def public_profile(user_id):
    """Public profile page"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (int(user_id),)
        )
        profile = await cursor.fetchone()
        
        if not profile:
            return render_template('error.html', message='Profile not found')
        
        cursor = await db.execute(
            "SELECT * FROM user_stats WHERE user_id = ?",
            (int(user_id),)
        )
        stats = await cursor.fetchone()
        
        cursor = await db.execute(
            "SELECT achievement_name, achievement_description, achievement_icon FROM user_achievements WHERE user_id = ? ORDER BY unlocked_at DESC LIMIT 5",
            (int(user_id),)
        )
        achievements = await cursor.fetchall()
        
        cursor = await db.execute(
            "SELECT * FROM social_connections WHERE user_id = ?",
            (int(user_id),)
        )
        social = await cursor.fetchone()
    
    return render_template('public_profile.html',
                          profile=profile,
                          stats=stats,
                          achievements=achievements,
                          social=social)

@app.route('/leaderboard')
async def leaderboard():
    """Leaderboard page"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT user_id, xp, level FROM user_profiles ORDER BY xp DESC LIMIT 50"
        )
        top_users = await cursor.fetchall()
    
    return render_template('leaderboard.html', top_users=top_users)

@app.route('/api/profile/<user_id>')
async def api_profile(user_id):
    """API endpoint for profile data"""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (int(user_id),)
        )
        profile = await cursor.fetchone()
        
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        cursor = await db.execute(
            "SELECT * FROM user_stats WHERE user_id = ?",
            (int(user_id),)
        )
        stats = await cursor.fetchone()
    
    return jsonify({
        'profile': {
            'user_id': profile[0],
            'username': profile[1],
            'discriminator': profile[2],
            'avatar_url': profile[3],
            'bio': profile[4],
            'banner_url': profile[5],
            'xp': profile[6],
            'level': profile[7],
            'coins': profile[8],
            'theme_color': profile[10],
            'profile_style': profile[11]
        },
        'stats': {
            'messages_sent': stats[1],
            'voice_minutes': stats[2],
            'commands_used': stats[3],
            'tickets_created': stats[4],
            'applications_submitted': stats[5],
            'suggestions_made': stats[6],
            'reputation': stats[10]
        }
    })

@app.route('/logout')
async def logout():
    """Logout"""
    response = redirect(url_for('index'))
    response.delete_cookie('auth_token')
    return response

@app.route('/documentation')
async def documentation():
    """Documentation page"""
    return render_template('documentation.html')

@app.route('/about')
async def about():
    """About page"""
    return render_template('about.html')

@app.route('/contact')
async def contact():
    """Contact page"""
    return render_template('contact.html')

@app.route('/privacy')
async def privacy():
    """Privacy policy page"""
    return render_template('privacy.html')

@app.route('/terms')
async def terms():
    """Terms of service page"""
    return render_template('terms.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
