# app.py – Unified Chameleon + Bluff (Complete Fixed Version with 3-Player Option)
from flask import Flask, render_template_string, jsonify, request, session
import random
import string
import uuid
import time
import html
import threading
import os
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'unified_secret_key_change_in_production')

# ---------- SECURITY HOOKS ----------
@app.before_request
def csrf_mitigation():
    if request.method == "POST":
        referer = request.headers.get('Referer')
        if referer:
            ref_url = urlparse(referer)
            host_url = urlparse(request.host_url)
            if ref_url.netloc != host_url.netloc:
                return jsonify({'error': 'CSRF token missing or incorrect origin'}), 403

# ---------- GLOBAL CHAT ----------
GLOBAL_CHAT_MESSAGES = []
MAX_CHAT_MESSAGES = 100
CHAT_LOCK = threading.Lock()

def add_global_message(username, text):
    timestamp = time.strftime("%H:%M")
    with CHAT_LOCK:
        GLOBAL_CHAT_MESSAGES.append({
            'username': html.escape(username)[:20],
            'text': html.escape(text)[:200],
            'time': timestamp
        })
        if len(GLOBAL_CHAT_MESSAGES) > MAX_CHAT_MESSAGES:
            GLOBAL_CHAT_MESSAGES.pop(0)

# ---------- GAME DATA ----------
TOPIC_CARDS = {
    "Food & Drink": [["Pizza","Sushi","Taco","Burger"],["Pasta","Curry","Ramen","Burrito"],["Coffee","Espresso","Matcha","Boba"],["Donut","Ice Cream","Pancake","Waffle"]],
    "Movies & Cinema": [["Titanic","Inception","Avatar","Jaws"],["Matrix","Star Wars","Avengers","Jurassic Park"],["Godfather","Gladiator","Oppenheimer","Interstellar"],["Shrek","Toy Story","Frozen","Finding Nemo"]],
    "Animals & Wildlife": [["Lion","Elephant","Giraffe","Cheetah"],["Penguin","Flamingo","Dolphin","Octopus"],["Kangaroo","Koala","Panda","Grizzly Bear"],["Eagle","Owl","Shark","Chameleon"]],
    "Countries & Nations": [["Japan","Brazil","France","Canada"],["Egypt","Australia","Italy","India"],["Mexico","Germany","Greece","Spain"],["South Korea","Norway","Kenya","Thailand"]],
    "Superheroes & Villains": [["Spider-Man","Batman","Superman","Iron Man"],["Wonder Woman","Thor","Captain America","Hulk"],["Black Panther","Flash","Aquaman","Doctor Strange"],["Joker","Thanos","Loki","Venom"]],
    "Video Games": [["Minecraft","Fortnite","Pokemon","Tetris"],["Super Mario","Zelda","Pac-Man","GTA"],["Roblox","Call of Duty","Overwatch","Valorant"],["The Witcher","Skyrim","Elden Ring","Sonic"]],
    "Sports & Fitness": [["Soccer","Basketball","Tennis","Baseball"],["Volleyball","Golf","Swimming","Boxing"],["Skiing","Surfing","Rugby","Cricket"],["Cycling","Running","Gymnastics","Ice Hockey"]],
    "Space & Astronomy": [["Mars","Jupiter","Saturn","Moon"],["Black Hole","Supernova","Asteroid","Comet"],["Telescope","Rocket","Astronaut","Milky Way"],["Nebula","Satellite","Solar Eclipse","Galaxy"]],
    "Music Genres": [["Rock","Pop","Jazz","Classical"],["Hip Hop","Country","Reggae","Blues"],["Electronic","Folk","R&B","Metal"],["Disco","Punk","Soul","K-Pop"]],
    "Mythical Creatures": [["Dragon","Unicorn","Griffin","Phoenix"],["Mermaid","Centaur","Minotaur","Pegasus"],["Werewolf","Vampire","Goblin","Troll"],["Fairy","Elf","Kraken","Yeti"]],
    "School Subjects": [["Math","History","Science","Art"],["Music","Geography","Literature","P.E."],["Physics","Chemistry","Biology","Drama"],["Computer Science","Economics","Languages","Philosophy"]],
    "Famous Landmarks": [["Eiffel Tower","Great Wall","Pyramids","Colosseum"],["Taj Mahal","Statue of Liberty","Big Ben","Machu Picchu"],["Mount Rushmore","Stonehenge","Sydney Opera","Acropolis"],["Burj Khalifa","Golden Gate","Christ the Redeemer","Mount Fuji"]],
    "Board Games": [["Chess","Monopoly","Scrabble","Risk"],["Catan","Carcassonne","Ticket to Ride","Pandemic"],["Clue","Battleship","Stratego","Sorry"],["Checkers","Backgammon","Dominoes","Mahjong"]],
    "Fictional Characters": [["Sherlock Holmes","James Bond","Harry Potter","Atticus Finch"],["Elizabeth Bennet","Holden Caulfield","Jay Gatsby","Hamlet"],["Frodo Baggins","Katniss Everdeen","Gandalf","Dumbledore"],["Bruce Wayne","Clark Kent","Peter Parker","Tony Stark"]],
    "Musical Instruments": [["Guitar","Piano","Violin","Drums"],["Flute","Trumpet","Saxophone","Cello"],["Harp","Trombone","Clarinet","Bass"],["Organ","Mandolin","Banjo","Accordion"]],
    "Types of Dance": [["Ballet","Tap","Jazz","Hip Hop"],["Salsa","Tango","Waltz","Foxtrot"],["Breakdance","Contemporary","Flamenco","Belly Dance"],["Swing","Rumba","Cha Cha","Bolero"]]
}

def get_random_coordinates():
    cols = ['A', 'B', 'C', 'D']
    rows = [1, 2, 3, 4]
    return random.choice(cols), random.choice(rows)

# ---------- BLUFF DECK ----------
SUITS = ['♠','♥','♦','♣']
RANKS = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']

def create_deck():
    return [f"{rank}{suit}" for suit in SUITS for rank in RANKS]

def shuffle_deck(d):
    random.shuffle(d)
    return d

def deal_cards(deck, n):
    hands = [[] for _ in range(n)]
    for i, card in enumerate(deck):
        hands[i % n].append(card)
    return hands

def rank_of(card):
    return card[:-1]

# ---------- THREAD SAFETY ----------
ROOMS_LOCK = threading.RLock()
GAME_STATE_LOCK = threading.RLock()

# ---------- LOCAL (Pass & Play) ----------
game_state = {
    'phase': 'START_SCREEN',
    'players_count': 3,
    'current_player_idx': 0,
    'roles': [],
    'player_codes': {},
    'valid_codes': set(),
    'col': '',
    'row': 0,
    'topic_name': '',
    'grid': [],
    'chameleon_idx': -1,
    'use_codes': True
}

# ---------- ONLINE ROOMS ----------
ROOMS = {}
ROOM_EXPIRE_INACTIVE = 300
ROOM_EXPIRE_IN_PROGRESS = 600
ROOM_KEEP_ALIVE = 86400

def clean_expired_rooms():
    now = time.time()
    expired = []
    with ROOMS_LOCK:
        for room_id, room in ROOMS.items():
            if room.get('keep_until', 0) > now:
                continue
            threshold = ROOM_EXPIRE_INACTIVE if room['phase'] == 'LOBBY' else ROOM_EXPIRE_IN_PROGRESS
            if now - room.get('last_activity', now) > threshold:
                expired.append(room_id)
            elif len(room['players']) == 0:
                expired.append(room_id)
        for rid in expired:
            del ROOMS[rid]

def generate_room_id():
    clean_expired_rooms()
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        with ROOMS_LOCK:
            if code not in ROOMS:
                return code

def log_room_action(room, msg):
    timestamp = time.strftime("%H:%M:%S")
    safe_msg = html.escape(msg)
    with ROOMS_LOCK:
        room['game_log'].append(f"[{timestamp}] {safe_msg}")
        if len(room['game_log']) > 50:
            room['game_log'].pop(0)

def remove_player_and_manuals(room, target_id):
    to_remove = [pid for pid, p in room['players'].items() if pid == target_id or p.get('device_id') == target_id]
    for pid in to_remove:
        if pid in room['players']:
            del room['players'][pid]

# ---------- GAME SETUPS ----------
def setup_new_online_round(room, category=None):
    player_ids = list(room['players'].keys())
    if len(player_ids) < 3:
        return
    room['roles'] = {}
    chameleon_id = random.choice(player_ids)
    room['chameleon_id'] = chameleon_id
    for pid in player_ids:
        room['roles'][pid] = 'CHAMELEON' if pid == chameleon_id else 'CLUED_IN'

    if not category or category not in TOPIC_CARDS:
        category = random.choice(list(TOPIC_CARDS.keys()))
    grid = TOPIC_CARDS[category]
    room['topic_name'] = category
    room['grid'] = grid

    # FIX: select col/row first, then derive secret_word from that coordinate
    room['col'], room['row'] = get_random_coordinates()
    col_idx = ord(room['col']) - ord('A')
    row_idx = room['row'] - 1
    room['secret_word'] = grid[row_idx][col_idx]

    shared_clued_code = str(random.randint(0, 9))
    while True:
        chameleon_code = str(random.randint(0, 9))
        if chameleon_code != shared_clued_code:
            break
    room['player_codes'] = {}
    for pid in player_ids:
        room['player_codes'][pid] = chameleon_code if room['roles'][pid] == 'CHAMELEON' else shared_clued_code
    room['revealed_players'] = set()
    room['phase'] = 'ROLE_REVEAL'

def start_bluff_round(room):
    players = [p for p in room['players'] if not room['players'][p].get('is_manual')]
    random.shuffle(players)
    room['turn_order'] = players
    room['current_turn_index'] = random.randint(0, len(players)-1)
    deck = shuffle_deck(create_deck())
    hands = deal_cards(deck, len(players))
    for i, pid in enumerate(players):
        room['players'][pid]['cards'] = hands[i]

    room['discard_pile'] = []
    room['played_cards'] = []
    room['last_played_cards'] = []
    room['claimed_rank'] = ''
    room['played_by'] = None
    room['consecutive_passes'] = 0
    room['winner'] = None
    room['voting'] = None
    room['phase'] = 'BLUFF_PLAYING'
    room['last_activity'] = time.time()
    log_room_action(room, "🃏 Bluff started! Hands dealt.")

def next_bluff_turn(room):
    active_cards = [p for p in room['turn_order'] if len(room['players'][p]['cards']) > 0]
    
    if len(active_cards) <= 1:
        room['phase'] = 'BLUFF_FINISHED'
        loser_id = active_cards[0] if active_cards else None
        room['winner'] = loser_id
        if loser_id:
            log_room_action(room, f"🏁 Game Over! {room['players'][loser_id]['name']} is the last one with cards!")
        return None
        
    for _ in range(len(room['turn_order'])):
        room['current_turn_index'] = (room['current_turn_index'] + 1) % len(room['turn_order'])
        pid = room['turn_order'][room['current_turn_index']]
        if len(room['players'][pid]['cards']) > 0:
            return pid
    return None

# ---------- BACKGROUND THREAD ----------
def cleanup_loop():
    while True:
        time.sleep(60)
        clean_expired_rooms()
threading.Thread(target=cleanup_loop, daemon=True).start()

# ---------- ROUTES ----------
@app.route('/')
def index():
    if 'player_id' not in session:
        session['player_id'] = str(uuid.uuid4())
    return render_template_string(HTML_TEMPLATE, topics=list(TOPIC_CARDS.keys()))

@app.route('/global_chat/get_messages')
def global_chat_get_messages():
    with CHAT_LOCK:
        return jsonify(GLOBAL_CHAT_MESSAGES[-50:])

@app.route('/global_chat/send', methods=['POST'])
def global_chat_send():
    data = request.json
    username = data.get('username', 'Anonymous').strip()[:20]
    text = data.get('text', '').strip()[:200]
    if text:
        add_global_message(username or 'Anonymous', text)
    return jsonify({'success': True})

# ---------- LOCAL PASS & PLAY ROUTES ----------
@app.route('/local/state', methods=['POST'])
def local_state():
    with GAME_STATE_LOCK:
        return jsonify({
            'phase': game_state['phase'],
            'topic_name': game_state['topic_name'],
            'grid': game_state['grid'],
            'players_count': game_state['players_count'],
            'current_player_idx': game_state['current_player_idx'],
            'use_codes': game_state['use_codes']
        })

@app.route('/local/start_game', methods=['POST'])
def local_start_game():
    data = request.json or {}
    players_count = int(data.get('players_count', 3))
    use_codes = data.get('use_codes', True)
    
    with GAME_STATE_LOCK:
        game_state['players_count'] = players_count
        game_state['use_codes'] = use_codes
        game_state['current_player_idx'] = 0
        game_state['valid_codes'].clear()
        game_state['player_codes'].clear()
        roles = ['CHAMELEON'] + ['CLUED_IN'] * (players_count - 1)
        random.shuffle(roles)
        game_state['roles'] = roles
        shared_clued_code = str(random.randint(0, 9))
        while True:
            chameleon_code = str(random.randint(0, 9))
            if chameleon_code != shared_clued_code:
                break
        for i in range(players_count):
            if roles[i] == 'CLUED_IN':
                game_state['player_codes'][i] = shared_clued_code
                game_state['valid_codes'].add(shared_clued_code)
            else:
                game_state['player_codes'][i] = chameleon_code
                game_state['chameleon_idx'] = i
        game_state['col'], game_state['row'] = get_random_coordinates()
        topic_name, grid = random.choice(list(TOPIC_CARDS.items()))
        game_state['topic_name'] = topic_name
        game_state['grid'] = grid
        # For local, we don't need secret_word separately; it's derived from grid and coordinates.
        game_state['phase'] = 'ROLES' if use_codes else 'PUBLIC_GRID'
    return jsonify({'success': True})

@app.route('/local/get_role', methods=['POST'])
def local_get_role():
    with GAME_STATE_LOCK:
        idx = game_state['current_player_idx']
        role = game_state['roles'][idx]
        code = game_state['player_codes'][idx]
    return jsonify({'player': idx+1, 'is_chameleon': (role == 'CHAMELEON'), 'code': code})

@app.route('/local/next_player', methods=['POST'])
def local_next_player():
    with GAME_STATE_LOCK:
        game_state['current_player_idx'] += 1
        if game_state['current_player_idx'] >= game_state['players_count']:
            game_state['phase'] = 'PUBLIC_GRID'
    return jsonify({'success': True})

@app.route('/local/verify_code', methods=['POST'])
def local_verify_code():
    with GAME_STATE_LOCK:
        if game_state['use_codes']:
            code = str(request.json.get('code', '')).strip()
            if code in game_state['valid_codes']:
                return jsonify({'valid': True, 'is_chameleon': False, 'col': game_state['col'], 'row': game_state['row']})
            elif code == str(game_state['player_codes'].get(game_state['chameleon_idx'])):
                return jsonify({'valid': True, 'is_chameleon': True})
            return jsonify({'valid': False})
        else:
            player_idx = int(request.json.get('player_idx', 0))
            if player_idx < 0 or player_idx >= game_state['players_count']:
                return jsonify({'valid': False})
            is_chameleon = (game_state['roles'][player_idx] == 'CHAMELEON')
            return jsonify({'valid': True, 'is_chameleon': is_chameleon, 'col': game_state['col'], 'row': game_state['row']})

@app.route('/local/change_topic', methods=['POST'])
def local_change_topic():
    data = request.json
    req_type = data.get('type')
    topic_name = data.get('topic')
    
    with GAME_STATE_LOCK:
        if req_type == 'random' or not topic_name or topic_name not in TOPIC_CARDS:
            topic_name, grid = random.choice(list(TOPIC_CARDS.items()))
        else:
            grid = TOPIC_CARDS[topic_name]
        
        game_state['topic_name'] = topic_name
        game_state['grid'] = grid
        game_state['col'], game_state['row'] = get_random_coordinates()
    return jsonify({'success': True})

@app.route('/local/restart', methods=['POST'])
def local_restart():
    with GAME_STATE_LOCK:
        game_state['phase'] = 'START_SCREEN'
    return jsonify({'success': True})

# ---------- ONLINE ROUTES ----------
@app.route('/online/list_games')
def online_list_games():
    clean_expired_rooms()
    games = []
    with ROOMS_LOCK:
        for room_id, room in ROOMS.items():
            games.append({
                'id': room_id,
                'host_name': room['players'][room['host_id']]['name'],
                'player_count': len(room['players']),
                'phase': room['phase'],
                'game_type': room.get('game_type', 'chameleon'),
                'keep_until': room.get('keep_until', 0)
            })
    return jsonify(games)

@app.route('/online/create_game', methods=['POST'])
def online_create_game():
    player_id = session.get('player_id')
    name = html.escape(request.json.get('name', 'Host').strip()[:12] or 'Host')
    room_id = generate_room_id()
    
    room_data = {
        'host_id': player_id,
        'phase': 'LOBBY',
        'game_type': 'chameleon',
        'game_log': [],
        'players': {player_id: {'name': name, 'is_host': True, 'is_manual': False}},
        'roles': {},
        'player_codes': {},
        'votes': {},
        'topic_name': '',
        'grid': [],
        'chameleon_id': None,
        'secret_word': '',
        'col': '',
        'row': 0,
        'created_at': time.time(),
        'use_codes': True,
        'last_activity': time.time(),
        'keep_until': 0,
        'revealed_players': set(),
        'turn_order': [],
        'current_turn_index': 0,
        'discard_pile': [],
        'played_cards': [],
        'last_played_cards': [], 
        'claimed_rank': '',
        'played_by': None,
        'consecutive_passes': 0,
        'winner': None,
        'voting': None
    }
    
    with ROOMS_LOCK:
        ROOMS[room_id] = room_data
        log_room_action(ROOMS[room_id], f"Room created by {name}")
    
    return jsonify({'room_id': room_id, 'is_host': True})

@app.route('/online/set_game', methods=['POST'])
def online_set_game():
    room_id = request.json.get('room_id')
    game_type = request.json.get('game_type')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room or player_id != room['host_id']:
            return jsonify({'error': 'Host required'}), 403
        if game_type not in ['chameleon', 'bluff']:
            return jsonify({'error': 'Invalid game type'}), 400
        room['game_type'] = game_type
        room['phase'] = 'LOBBY'
        log_room_action(room, f"⚙️ Gamemode: {game_type.upper()}")
    return jsonify({'success': True})

@app.route('/online/request_gamemode', methods=['POST'])
def online_request_gamemode():
    room_id = request.json.get('room_id')
    mode = request.json.get('mode')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if room and player_id in room['players']:
            p_name = room['players'][player_id]['name']
            log_room_action(room, f"🔔 {p_name} wants {mode.upper()}!")
            return jsonify({'success': True})
    return jsonify({'error': 'Not found'}), 404

@app.route('/online/join_game', methods=['POST'])
def online_join_game():
    player_id = session.get('player_id')
    name = html.escape(request.json.get('name', 'Player').strip()[:12] or 'Player')
    room_id = request.json.get('room_id')
    
    with ROOMS_LOCK:
        if room_id not in ROOMS:
            return jsonify({'success': False, 'error': 'Room not found.'})
        room = ROOMS[room_id]
        if room['phase'] not in ['LOBBY', 'WAITING_DEVICE_SETUP']:
            return jsonify({'success': False, 'error': 'Game in progress.'})
        if player_id in room['players']:
            return jsonify({'success': False, 'error': 'Already in game.'})
        room['players'][player_id] = {'name': name, 'is_host': False, 'is_manual': False}
        room['last_activity'] = time.time()
        log_room_action(room, f"👋 {name} joined")
    return jsonify({'success': True, 'room_id': room_id, 'is_host': False})

@app.route('/online/add_manual_player', methods=['POST'])
def online_add_manual_player():
    room_id = request.json.get('room_id')
    player_id = session.get('player_id')
    name = html.escape(request.json.get('name', 'Player').strip()[:12] or 'Player')
    device_id = request.json.get('device_id', player_id)
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room or player_id != room['host_id']:
            return jsonify({'error': 'Host required'}), 403
        
        manual_id = f"manual_{int(time.time())}_{random.randint(100,999)}"
        room['players'][manual_id] = {'name': name, 'is_host': False, 'is_manual': True, 'device_id': device_id}
        room['last_activity'] = time.time()
    return jsonify({'success': True, 'player_id': manual_id})

@app.route('/online/remove_player', methods=['POST'])
def online_remove_player():
    room_id = request.json.get('room_id')
    target_id = request.json.get('player_id')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room or player_id != room['host_id']:
            return jsonify({'error': 'Host required'}), 403
        if target_id == room['host_id']:
            return jsonify({'error': 'Cannot remove host'}), 400
        if target_id not in room['players']:
            return jsonify({'error': 'Player not found'}), 404
        
        p_name = room['players'][target_id]['name']
        remove_player_and_manuals(room, target_id)
        
        room['last_activity'] = time.time()
        log_room_action(room, f"🚪 {p_name} was removed.")
        
        if room['phase'] not in ['LOBBY', 'WAITING_DEVICE_SETUP']:
            room['phase'] = 'LOBBY'
    return jsonify({'success': True})

@app.route('/online/keep_room', methods=['POST'])
def online_keep_room():
    room_id = request.json.get('room_id')
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if room and session.get('player_id') == room['host_id']:
            room['keep_until'] = time.time() + ROOM_KEEP_ALIVE
            return jsonify({'success': True})
    return jsonify({'error': 'Unauthorized'}), 403

@app.route('/online/leave_room', methods=['POST'])
def online_leave_room():
    room_id = request.json.get('room_id')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            return jsonify({'success': False, 'error': 'Room not found'})
            
        if player_id == room['host_id']:
            del ROOMS[room_id]
            return jsonify({'success': True, 'disbanded': True})
            
        if player_id in room['players']:
            remove_player_and_manuals(room, player_id)
            if room['phase'] not in ['LOBBY', 'WAITING_DEVICE_SETUP']:
                room['phase'] = 'LOBBY'
                
    return jsonify({'success': True, 'disbanded': False})

@app.route('/online/toggle_codes', methods=['POST'])
def online_toggle_codes():
    room_id = request.json.get('room_id')
    use_codes = request.json.get('use_codes')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if room and session.get('player_id') == room['host_id']:
            room['use_codes'] = use_codes
            return jsonify({'success': True})
    return jsonify({'error': 'Unauthorized'}), 403

@app.route('/online/room_state')
def online_room_state():
    room_id = request.args.get('room')
    player_id = session.get('player_id')
    clean_expired_rooms()
    
    with ROOMS_LOCK:
        if room_id not in ROOMS:
            return jsonify({'error': 'Room not found.'})
        room = ROOMS[room_id]
        room['last_activity'] = time.time()

        if room['host_id'] not in room['players'] and len(room['players']) > 0:
            new_host_id = list(room['players'].keys())[0]
            room['host_id'] = new_host_id
            for pid in room['players']:
                room['players'][pid]['is_host'] = (pid == new_host_id)

        players_list = []
        for pid, info in room['players'].items():
            players_list.append({
                'id': pid, 'name': info['name'], 'is_host': info['is_host'],
                'is_manual': info.get('is_manual', False),
                'card_count': len(info.get('cards', [])) if room['game_type'] == 'bluff' else 0
            })

        response = {
            'phase': room['phase'],
            'game_type': room.get('game_type', 'chameleon'),
            'game_log': room.get('game_log', [])[-15:], 
            'players': players_list,
            'total_players': len(room['players']),
            'is_host': (player_id == room['host_id']),
            'my_id': player_id
        }

        if response['game_type'] == 'chameleon':
            device_players = [
                {'id': pid, 'name': pinfo['name']}
                for pid, pinfo in room['players'].items()
                if pid == player_id or pinfo.get('device_id') == player_id
            ]
            
            response.update({
                'topic_name': room['topic_name'],
                'grid': room['grid'],
                'categories': list(TOPIC_CARDS.keys()),
                'votes_count': len(room['votes']),
                'chameleon_name': room['players'].get(room['chameleon_id'], {}).get('name', 'Unknown') if room['chameleon_id'] else '',
                'secret_word': room['secret_word'] if room['phase'] == 'RESULTS' else None,
                'vote_results': [],
                'use_codes': room.get('use_codes', True),
                'device_players': device_players,
                'chameleon_caught': None
            })
            
            if room['phase'] == 'RESULTS':
                counts = {pid: 0 for pid in room['players']}
                for target in room['votes'].values():
                    if target in counts: counts[target] += 1
                for pid, cnt in counts.items():
                    response['vote_results'].append({'name': room['players'][pid]['name'], 'count': cnt})
                
                # Determine if chameleon was caught
                if counts:
                    max_votes = max(counts.values())
                    # If there's a tie, chameleon is not caught (standard rule)
                    if max_votes > 0 and counts.get(room['chameleon_id'], 0) == max_votes:
                        response['chameleon_caught'] = True
                    else:
                        response['chameleon_caught'] = False
                else:
                    response['chameleon_caught'] = False

            if room['phase'] == 'ROLE_REVEAL':
                unrevealed = [p for p in device_players if p['id'] not in room.get('revealed_players', set())]
                if unrevealed:
                    response['current_reveal_name'] = unrevealed[0]['name']
                    response['current_reveal_id'] = unrevealed[0]['id']
                    response['already_revealed'] = False
                else:
                    response['already_revealed'] = True

        else:  # BLUFF
            response.update({
                'current_player': room['turn_order'][room['current_turn_index']] if room['turn_order'] else None,
                'your_hand': room['players'].get(player_id, {}).get('cards', []),
                'played_cards': room['played_cards'],
                'claimed_rank': room['claimed_rank'],
                'played_by': room['played_by'],
                'discard_pile_count': len(room['discard_pile']),
                'winner': room['winner']
            })

    return jsonify(response)

@app.route('/online/start_game', methods=['POST'])
def online_start_game():
    room_id = request.json.get('room_id')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room or player_id != room['host_id']:
            return jsonify({'error': 'Host required'}), 403
        if room['game_type'] == 'bluff':
            active = [p for p in room['players'] if not room['players'][p].get('is_manual')]
            if len(active) < 2:
                return jsonify({'error': 'Need at least 2 online players for Bluff'}), 400
            start_bluff_round(room)
        else:
            if len(room['players']) < 3:
                return jsonify({'error': 'Need at least 3 players for Chameleon'}), 400
            room['votes'] = {}
            setup_new_online_round(room)
    return jsonify({'success': True})

@app.route('/online/next_round', methods=['POST'])
def online_next_round():
    room_id = request.json.get('room_id')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room or player_id != room['host_id']:
            return jsonify({'error': 'Host required'}), 403
        if room['game_type'] == 'chameleon':
            room['votes'] = {}
            setup_new_online_round(room)
        else:
            start_bluff_round(room)
    return jsonify({'success': True})

# --- CHAMELEON ACTIONS ---
@app.route('/online/reveal_role', methods=['POST'])
def online_reveal_role():
    room_id = request.json.get('room_id')
    target_id = request.json.get('target_id')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room or room['phase'] != 'ROLE_REVEAL':
            return jsonify({'error': 'Invalid phase'}), 400
        
        target_player = room['players'].get(target_id)
        if not target_player:
            return jsonify({'error': 'Invalid target'}), 400
            
        if target_id != player_id and target_player.get('device_id') != player_id:
            return jsonify({'error': 'Unauthorized to reveal this role'}), 403
            
        if target_id in room.get('revealed_players', set()):
            return jsonify({'error': 'Already revealed'}), 400
            
        room['revealed_players'].add(target_id)
        return jsonify({
            'is_chameleon': (room['roles'][target_id] == 'CHAMELEON'),
            'code': room['player_codes'][target_id],
            'player_name': target_player['name']
        })

@app.route('/online/player_done', methods=['POST'])
def online_player_done():
    room_id = request.json.get('room_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room: return jsonify({'success': False})
        
        if len(room['revealed_players']) >= len(room['players']):
            room['phase'] = 'PLAYING'
            log_room_action(room, "🎭 Everyone revealed their roles. Phase transitioned to Playing.")
            
    return jsonify({'success': True})

@app.route('/online/verify_code', methods=['POST'])
def online_verify_code():
    data = request.json
    room_id = data.get('room_id')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            return jsonify({'valid': False})
        
        if room.get('use_codes', True):
            code = str(data.get('code', '')).strip()
            for pid, expected_code in room['player_codes'].items():
                if expected_code == code:
                    if pid != player_id and room['players'][pid].get('device_id') != player_id:
                        continue
                    is_cham = (room['roles'][pid] == 'CHAMELEON')
                    return jsonify({'valid': True, 'is_chameleon': is_cham, 'col': room['col'], 'row': room['row']})
            return jsonify({'valid': False})
        else:
            tgt = data.get('player_id')
            tgt_player = room['players'].get(tgt)
            if not tgt_player:
                return jsonify({'valid': False})
                
            if tgt != player_id and tgt_player.get('device_id') != player_id:
                return jsonify({'valid': False})
                
            is_cham = (room['roles'][tgt] == 'CHAMELEON')
            return jsonify({'valid': True, 'is_chameleon': is_cham, 'col': room['col'], 'row': room['row']})

@app.route('/online/change_topic', methods=['POST'])
def online_change_topic():
    data = request.json
    room_id = data.get('room_id')
    req_type = data.get('type')
    topic_name = data.get('topic')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
            
        if room['host_id'] != player_id:
            return jsonify({'error': 'Only the host can change the topic'}), 403
        
        if req_type == 'random' or not topic_name or topic_name not in TOPIC_CARDS:
            topic_name = random.choice(list(TOPIC_CARDS.keys()))
        
        room['topic_name'] = topic_name
        room['grid'] = TOPIC_CARDS[topic_name]
        # FIX: regenerate col/row and set secret_word accordingly
        room['col'], room['row'] = get_random_coordinates()
        col_idx = ord(room['col']) - ord('A')
        row_idx = room['row'] - 1
        room['secret_word'] = room['grid'][row_idx][col_idx]
        log_room_action(room, f"🔄 Topic changed to {topic_name}")
    return jsonify({'success': True})

@app.route('/online/start_voting_phase', methods=['POST'])
def online_start_voting():
    room_id = request.json.get('room_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if room:
            room['phase'] = 'VOTING'
            log_room_action(room, "🗳️ Voting started!")
    return jsonify({'success': True})

@app.route('/online/cast_vote', methods=['POST'])
def online_cast_vote():
    data = request.json
    room_id = data.get('room_id')
    voter_id = data.get('voter_id')
    target_id = data.get('target_id')
    player_id = session.get('player_id')
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
            
        voter_player = room['players'].get(voter_id)
        if not voter_player:
            return jsonify({'error': 'Invalid voter'}), 400
            
        if voter_id != player_id and voter_player.get('device_id') != player_id:
            return jsonify({'error': 'Unauthorized to cast this vote'}), 403
        
        if voter_id in room['votes']:
            return jsonify({'error': 'Already voted'}), 400
        
        if target_id not in room['players']:
            return jsonify({'error': 'Invalid target'}), 400
        
        room['votes'][voter_id] = target_id
        if len(room['votes']) >= len(room['players']):
            room['phase'] = 'RESULTS'
            log_room_action(room, "🗳️ All votes cast, moving to results.")
    
    return jsonify({'success': True})

@app.route('/online/end_voting', methods=['POST'])
def online_end_voting():
    room_id = request.json.get('room_id')
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if room:
            room['phase'] = 'RESULTS'
            log_room_action(room, "🗳️ Voting ended by host.")
    return jsonify({'success': True})

@app.route('/online/restart', methods=['POST'])
def online_restart():
    room_id = request.json.get('room_id')
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if room:
            room['phase'] = 'LOBBY'
            room['revealed_players'] = set()
            room['votes'] = {}
            room['turn_order'] = []
            room['current_turn_index'] = 0
            room['discard_pile'] = []
            room['played_cards'] = []
            room['last_played_cards'] = []
            room['claimed_rank'] = ''
            room['played_by'] = None
            room['consecutive_passes'] = 0
            room['winner'] = None
    return jsonify({'success': True})

# --- BLUFF ACTIONS ---
@app.route('/online/bluff_action', methods=['POST'])
def online_bluff_action():
    data = request.json
    action = data.get('action')
    room_id = data.get('room_id')
    pid = session['player_id']
    
    with ROOMS_LOCK:
        room = ROOMS.get(room_id)
        if not room or room['game_type'] != 'bluff': 
            return jsonify({'error': 'Invalid state'}), 400

        if action == 'play_cards':
            if room['phase'] != 'BLUFF_PLAYING' or pid != room['turn_order'][room['current_turn_index']]:
                return jsonify({'error': 'Not your turn'})
            if room.get('played_by') is not None:
                return jsonify({'error': 'Already a play pending'})
                
            indices = data.get('indices', [])
            rank = data.get('rank', '')
            if not indices or not rank:
                return jsonify({'error': 'Select cards and rank'})
            
            hand = room['players'][pid]['cards']
            if max(indices) >= len(hand) or min(indices) < 0:
                return jsonify({'error': 'Invalid card indices'})
            
            played = [hand[i] for i in sorted(indices, reverse=True)]
            for i in sorted(indices, reverse=True): del hand[i]
            
            room['played_cards'] = played
            room['last_played_cards'] = played  
            room['claimed_rank'] = rank
            room['played_by'] = pid
            room['consecutive_passes'] = 0
            
            log_room_action(room, f"🃏 {room['players'][pid]['name']} started pile with {len(played)} card(s), claiming {rank}s")
            next_bluff_turn(room)
            return jsonify({'success': True})

        elif action == 'play_more':
            if room['phase'] != 'BLUFF_PLAYING' or pid != room['turn_order'][room['current_turn_index']]:
                return jsonify({'error': 'Not your turn'})
            if room.get('played_by') is None:
                return jsonify({'error': 'No claim to follow'})
                
            indices = data.get('indices', [])
            if not indices:
                return jsonify({'error': 'Select cards to play'})
            
            hand = room['players'][pid]['cards']
            if max(indices) >= len(hand) or min(indices) < 0:
                return jsonify({'error': 'Invalid card indices'})
            
            played = [hand[i] for i in sorted(indices, reverse=True)]
            for i in sorted(indices, reverse=True): del hand[i]
            
            room['played_cards'].extend(played)
            room['last_played_cards'] = played  
            room['played_by'] = pid             
            room['consecutive_passes'] = 0
            
            log_room_action(room, f"➕ {room['players'][pid]['name']} added {len(played)} card(s) to the pile")
            next_bluff_turn(room)
            return jsonify({'success': True})

        elif action == 'call_bluff':
            if room['phase'] != 'BLUFF_PLAYING' or pid != room['turn_order'][room['current_turn_index']]:
                return jsonify({'error': 'Not your turn'})
                
            played_by = room.get('played_by')
            if not played_by or played_by == pid:
                return jsonify({'error': 'Invalid call'})
                
            is_true = all(rank_of(c) == room['claimed_rank'] for c in room.get('last_played_cards', []))
            room['consecutive_passes'] = 0
            
            log_room_action(room, f"🚨 {room['players'][pid]['name']} called bluff on {room['players'][played_by]['name']}!")
            
            if is_true:
                pick_up, turn_to = pid, played_by
                log_room_action(room, f"✔️ TRUE! {room['players'][played_by]['name']} told the truth. {room['players'][pid]['name']} picks up pile.")
            else:
                pick_up, turn_to = played_by, pid
                log_room_action(room, f"❌ FALSE! {room['players'][played_by]['name']} lied. {room['players'][played_by]['name']} picks up pile.")
                
            cards = room['discard_pile'] + room['played_cards']
            room['players'][pick_up]['cards'].extend(cards)
            
            room['discard_pile'] = []
            room['played_cards'] = []
            room['last_played_cards'] = []
            room['claimed_rank'] = ''
            room['played_by'] = None
            
            if turn_to in room['turn_order']:
                room['current_turn_index'] = room['turn_order'].index(turn_to)
            else:
                next_bluff_turn(room)
                
            return jsonify({'success': True})

        elif action == 'pass_bluff':
            if room['phase'] != 'BLUFF_PLAYING' or pid != room['turn_order'][room['current_turn_index']]:
                return jsonify({'error': 'Not your turn'})
                
            played_by = room.get('played_by')
            if not played_by:
                return jsonify({'error': 'Nothing to pass on'})
                
            room['consecutive_passes'] = room.get('consecutive_passes', 0) + 1
            log_room_action(room, f"⏭️ {room['players'][pid]['name']} passed.")
            
            active_count = len([p for p in room['turn_order'] if len(room['players'][p]['cards']) > 0])
            
            if room['consecutive_passes'] >= active_count - 1:
                room['discard_pile'].extend(room['played_cards'])
                room['played_cards'] = []
                room['last_played_cards'] = []
                room['claimed_rank'] = ''
                room['played_by'] = None
                room['consecutive_passes'] = 0
                
                if played_by in room['turn_order'] and len(room['players'][played_by]['cards']) == 0:
                    room['turn_order'].remove(played_by)
                    log_room_action(room, f"💀 {room['players'][played_by]['name']} is eliminated (no cards left)")
                    next_bluff_turn(room)
                else:
                    log_room_action(room, f"🔄 Everyone passed. {room['players'][played_by]['name']} clears the pile and goes again.")
                    if played_by in room['turn_order']:
                        room['current_turn_index'] = room['turn_order'].index(played_by)
            else:
                next_bluff_turn(room)
                
            return jsonify({'success': True})

    return jsonify({'error': 'Unknown action'}), 400

# ---------- HTML TEMPLATE ----------
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Game Hub - Chameleon & Bluff</title>
    <style>
        :root { --bg-color: #0f172a; --card-bg: #1e293b; --accent: #06b6d4; --danger: #ef4444; --warning: #f59e0b; --purple: #8b5cf6; --success: #10b981; --text: #f8fafc; --text-muted: #94a3b8; }
        * { touch-action: manipulation; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg-color); color: var(--text); text-align: center; margin: 0; padding: 16px; min-height: 100vh; display: flex; align-items: center; justify-content: center; user-select: none; }
        .card { background: var(--card-bg); border-radius: 20px; padding: 24px; width: 100%; max-width: 480px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.08); }
        h2 { margin-top: 0; font-size: 26px; }
        .btn { background: var(--accent); color: white; border: none; padding: 14px 20px; font-size: 16px; font-weight: 700; border-radius: 12px; cursor: pointer; width: 100%; margin: 8px 0; transition: all 0.2s ease; }
        .btn:active { transform: scale(0.98); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-start { background: var(--success); }
        .btn-topic { background: var(--purple); }
        .btn-danger { background: var(--danger); }
        .btn-option { background: #334155; border: 1px solid var(--accent); color: var(--accent); }
        .btn-small { width: auto; padding: 6px 12px; margin: 0 4px; display: inline-block; }
        .btn-toggle { background: #1e293b; border: 2px solid var(--accent); color: var(--accent); padding: 10px; font-size:14px; margin-bottom:15px;}
        .btn-toggle.on { background: var(--accent); color: #000; }
        input, select { width: 100%; padding: 12px; font-size: 16px; border-radius: 10px; border: 1px solid #475569; background: #0f172a; color: #fff; margin: 8px 0; }
        .badge { display: inline-block; background: #334155; padding: 4px 12px; border-radius: 20px; font-size: 14px; color: var(--accent); margin-bottom: 12px; font-weight: bold; }
        .screen { display: none; }
        .active-screen { display: block; }
        .player-selector { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 15px 0; }
        .player-option { background: #334155; padding: 12px; border-radius: 10px; cursor: pointer; font-weight: bold; border: 2px solid transparent; transition: all 0.2s; }
        .player-option.selected { border-color: var(--accent); background: rgba(6, 182, 212, 0.2); color: var(--accent); }
        table { width: 100%; border-collapse: separate; border-spacing: 6px; margin-top: 15px; }
        th, td { border-radius: 8px; padding: 12px 4px; text-align: center; font-size: 14px; background: #334155; }
        td.highlight { background: var(--accent) !important; color: #000 !important; font-weight: bold; box-shadow: 0 0 12px rgba(6, 182, 212, 0.6); }
        .alert-box { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); font-weight: 600; padding: 14px; border-radius: 12px; margin: 12px 0; }
        .game-log { background: #0f172a; border-radius: 8px; padding: 8px; margin: 12px 0; overflow-y: auto; text-align: left; font-size: 13.5px; border: 1px solid #334155; color: var(--text-muted); scroll-behavior: smooth;}
        .game-log div { border-bottom: 1px solid #1e293b; padding: 5px 6px; }
        .game-log div:last-child { border-bottom: none; font-weight: bold; color: var(--text); }
        .hand { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; margin: 12px 0; }
        .card-item { background: white; color: #000; border-radius: 8px; padding: 8px 6px; min-width: 40px; font-weight: bold; text-align: center; cursor: pointer; border: 2px solid transparent; transition: all 0.2s; }
        .card-item.selected { border-color: var(--accent); box-shadow: 0 0 12px var(--accent); transform: scale(1.05); background: #e0f2fe; }
        .card-item.red { color: #dc2626; }
        .player-tag { display: inline-block; background: #334155; padding: 4px 10px; border-radius: 12px; margin: 4px; font-size: 13px; }
        .player-tag.current { background: var(--accent); color: #000; font-weight:bold; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.7); } 70% { box-shadow: 0 0 0 10px rgba(6, 182, 212, 0); } 100% { box-shadow: 0 0 0 0 rgba(6, 182, 212, 0); } }
        @keyframes pulseBadge { 0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); } 70% { transform: scale(1.2); box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); } 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); } }
        .pulse-anim { animation: pulseBadge 1.5s infinite; }
        #chat-toggle-btn { position: fixed; bottom: 20px; right: 20px; z-index: 1000; width: 60px; height: 60px; border-radius: 50%; background: var(--accent); color: white; border: none; font-size: 28px; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; }
        #chat-toggle-btn .badge { position: absolute; top: -5px; right: -5px; background: var(--danger); color: white; border-radius: 50%; width: 22px; height: 22px; font-size: 12px; display: flex; align-items: center; justify-content: center; font-weight: bold; margin:0;}
        #chat-container { position: fixed; bottom: 90px; right: 20px; z-index: 999; width: 320px; max-width: 90vw; height: 400px; max-height: 60vh; background: var(--card-bg); border-radius: 16px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 8px 30px rgba(0,0,0,0.6); display: none; flex-direction: column; overflow: hidden; }
        #chat-container.open { display: flex; }
        #chat-header { padding: 12px 16px; background: rgba(0,0,0,0.3); font-weight: bold; color: var(--accent); display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.05); }
        #chat-header button { background: none; border: none; color: var(--text-muted); font-size: 20px; cursor: pointer; }
        #chat-messages { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 4px; }
        .chat-msg { background: rgba(255,255,255,0.05); border-radius: 8px; padding: 6px 12px; font-size: 14px; text-align: left; }
        .chat-msg .username { color: var(--accent); font-weight: 600; margin-right: 6px; }
        .chat-msg .time { color: var(--text-muted); font-size: 11px; margin-left: 8px; }
        #chat-input-row { display: flex; padding: 8px; gap: 6px; border-top: 1px solid rgba(255,255,255,0.05); background: rgba(0,0,0,0.2); }
        #chat-input-row input { margin:0; font-size:14px; }
        #chat-input-row button { background: var(--accent); color: white; border: none; padding: 8px 16px; border-radius: 8px; cursor: pointer; }
        .toast { position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #334155; color: white; padding: 12px 20px; border-radius: 8px; z-index: 2000; animation: slideDown 0.3s ease; }
        @keyframes slideDown { from { opacity: 0; transform: translate(-50%, -20px); } to { opacity: 1; transform: translate(-50%, 0); } }
        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 1500; display: flex; align-items: center; justify-content: center; }
        .modal-content { background: var(--card-bg); border-radius: 16px; padding: 20px; max-width: 400px; width: 90%; max-height: 80vh; overflow-y: auto; }
        .topic-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 10px 0; }
        .topic-item { background: #334155; padding: 10px; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
        .topic-item:hover { background: var(--accent); color: #000; }
    </style>
</head>
<body>
<div class="card">
    <h2>🎮 Game Hub</h2>

    <div id="screen-landing" class="screen active-screen">
        <button class="btn btn-start" onclick="selectMode('LOCAL')">📱 Pass & Play (Local)</button>
        <button class="btn btn-topic" onclick="selectMode('ONLINE')">🌐 Online Multiplayer</button>
        <button class="btn" style="background:#475569;" onclick="showRules()">📖 How to Play</button>
    </div>

    <div id="screen-local-start" class="screen">
        <p style="color: var(--text-muted);">Number of Players:</p>
        <div class="player-selector" id="local-player-grid">
            <div class="player-option p-opt selected" onclick="selectLocalPlayers(3)">3</div>
            <div class="player-option p-opt" onclick="selectLocalPlayers(4)">4</div>
            <div class="player-option p-opt" onclick="selectLocalPlayers(5)">5</div>
            <div class="player-option p-opt" onclick="selectLocalPlayers(6)">6</div>
        </div>
        <button id="btn-local-toggle-codes" class="btn btn-toggle on" onclick="toggleLocalCodes()">🔒 Secret Codes: ON</button>
        <button class="btn btn-start" onclick="startLocalGame()">🎮 Start Game</button>
        <button class="btn" style="background:#334155;" onclick="goToLanding()">⬅ Back</button>
    </div>
    
    <div id="screen-local-roles" class="screen">
        <h3 id="local-player-turn-header" style="color: var(--accent);">Player 1's Turn</h3>
        <button id="local-reveal-role-btn" class="btn" onclick="revealLocalRole()">👁️ Show Secret Role</button>
        <div id="local-role-details" style="display: none;">
            <div id="local-role-alert-box" class="alert-box"><span id="local-role-message"></span></div>
            <div style="font-size:20px; margin: 10px 0;">CODE: <span id="local-assigned-code" style="color:var(--warning); font-weight:bold;">-</span></div>
            <button class="btn btn-start" onclick="nextLocalPlayer()">✅ Done - Pass Phone</button>
        </div>
    </div>

    <div id="screen-local-grid" class="screen">
        <h3 id="local-topic-title" style="color: var(--warning);"></h3>
        <button class="btn btn-topic" onclick="openTopicModal('local')">🔀 Change Topic</button>
        <table id="local-grid-table"></table>
        <div style="margin-top:15px;">
            <div id="local-code-input-area"><input type="text" id="local-player-code-input" placeholder="Enter Secret Code"/></div>
            <div id="local-no-code-area" style="display:none;"><select id="local-viewer-select"></select></div>
            <button class="btn" onclick="verifyLocalCode()">🔓 Reveal Target</button>
        </div>
        <div id="local-decrypted-info" style="display:none; margin-top:20px;">
            <div id="local-result-alert" class="alert-box"></div>
            <button class="btn" onclick="resetLocalGrid()" style="margin-top:15px;">🔒 Hide</button>
        </div>
        <button class="btn" style="background:#475569; margin-top:20px;" onclick="goToLanding()">🏠 End Game</button>
    </div>

    <div id="screen-online-start" class="screen">
        <input type="text" id="online-player-name" placeholder="Your Name" maxlength="12">
        <button class="btn btn-start" onclick="createOnlineGame()">➕ Create Lobby</button>
        <div id="online-game-list" style="margin-top:15px; text-align:left;"></div>
        <button class="btn" style="background:#334155; margin-top:10px;" onclick="goToLanding()">⬅ Back</button>
    </div>

    <div id="screen-online-lobby" class="screen">
        <div id="host-game-settings" style="display:none; background: #334155; padding:15px; border-radius:10px; margin-bottom:15px;">
            <label style="color:var(--accent); font-weight:bold;">Select Gamemode:</label>
            <select id="online-game-type" onchange="setGamemode(this.value)">
                <option value="chameleon">🦎 Chameleon</option>
                <option value="bluff">🃏 Bluff</option>
            </select>
        </div>
        <div id="player-request-gamemode" style="display:none; margin-bottom:15px;">
            <button class="btn btn-option btn-small" onclick="requestGamemode('chameleon')">Request Chameleon 🦎</button>
            <button class="btn btn-option btn-small" onclick="requestGamemode('bluff')">Request Bluff 🃏</button>
        </div>
        
        <div id="online-game-log" class="game-log" style="height: 120px;"></div>

        <div id="chameleon-lobby-features" style="background: rgba(0,0,0,0.2); padding:10px; border-radius:8px;">
            <button id="btn-online-toggle-codes" class="btn btn-toggle on btn-small" style="display:none;" onclick="toggleOnlineCodes()">🔒 Codes: ON</button>
            <div id="online-players-list" style="margin-top:10px;"></div>
            <div id="host-add-manual" style="display:none; margin-top:15px; border-top: 1px solid #475569; padding-top: 10px;">
                <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 5px;">Add offline players and assign to a device:</p>
                <div style="display:flex; gap:8px;">
                    <input type="text" id="manual-player-name" placeholder="Player Name">
                    <select id="manual-device-assign" style="margin:0;"></select>
                </div>
                <button class="btn btn-small" onclick="addManualPlayer()" style="margin-top: 5px; width: 100%;">Add Offline Player</button>
            </div>
        </div>

        <button id="btn-start-online" class="btn btn-start" style="display:none; margin-top:20px;" onclick="startOnlineGame()">🚀 Start Game</button>
        <p id="online-wait-msg" style="color:var(--warning); display:none; margin-top:20px;">Waiting for host...</p>
        <button class="btn" style="background:#475569; margin-top:10px;" onclick="leaveOnlineGame()">🚪 Leave</button>
        <button id="btn-disband-room" class="btn btn-danger" style="display:none; margin-top:10px;" onclick="disbandRoom()">❌ Disband Room</button>
    </div>

    <div id="screen-online-roles" class="screen">
        <h3 id="online-player-turn-header" style="color: var(--accent);"></h3>
        <button id="online-reveal-role-btn" class="btn" onclick="revealOnlineRole()">👁️ Show Secret Role</button>
        <div id="online-role-details" style="display: none;">
            <div id="online-role-alert-box" class="alert-box"></div>
            <div style="font-size:20px; margin: 10px 0;">CODE: <span id="online-assigned-code" style="color:var(--warning); font-weight:bold;"></span></div>
            <button class="btn btn-start" onclick="nextOnlinePlayer()">✅ Done</button>
        </div>
    </div>

    <div id="screen-online-grid" class="screen">
        <h3 id="online-topic-title" style="color: var(--warning);"></h3>
        <button id="btn-online-change-topic" class="btn btn-topic" style="display:none;" onclick="openTopicModal('online')">🔀 Change Topic</button>
        <table id="online-grid-table"></table>
        <div style="margin-top:15px;">
            <div id="online-code-input-area">
                <input type="text" id="online-player-code-input" placeholder="Enter your secret code"/>
                <button class="btn" onclick="verifyOnlineCode()">🔓 Reveal My Info</button>
            </div>
            <div id="online-no-code-area" style="display:none;">
                <select id="online-viewer-select"></select>
                <button class="btn" onclick="verifyOnlineCode()">🔓 Reveal My Info</button>
            </div>
        </div>
        <div id="online-decrypted-info" style="display:none; margin-top:20px;">
            <div id="online-result-alert" class="alert-box"></div>
            <button class="btn" onclick="resetOnlineGrid()" style="margin-top:15px;">🔒 Hide Info</button>
        </div>
        <div id="online-chameleon-log" class="game-log" style="height: 90px;"></div>
        <button id="btn-start-voting" class="btn btn-danger" style="display:none; margin-top:20px;" onclick="startOnlineVoting()">🗳️ Start Voting</button>
    </div>

    <div id="screen-online-voting" class="screen">
        <h3 style="color:var(--warning);">Who is the Chameleon?</h3>
        <p style="color:var(--text-muted); font-size:14px;">Select your voter profile, then pick a target.</p>
        <select id="vote-as-select" style="margin-bottom:10px;"></select>
        <div id="vote-targets" style="display:grid; grid-template-columns:1fr 1fr; gap:8px;"></div>
        <button id="btn-end-voting" class="btn btn-danger" style="display:none; margin-top:20px;" onclick="endOnlineVoting()">Force End Voting</button>
    </div>

    <div id="screen-online-bluff" class="screen">
        <div id="bluff-players"></div>
        <div id="bluff-game-log" class="game-log" style="height: 120px;"></div>
        <div id="bluff-turn" style="color:var(--warning); font-weight:bold; margin:10px 0;"></div>
        <div id="bluff-hand"></div>
        <div id="bluff-controls" style="margin-top:15px;"></div>
        <div id="bluff-winner" style="display:none; margin-top:20px;"></div>
        <button class="btn" style="background:#475569; margin-top:20px;" onclick="leaveOnlineGame()">🚪 Leave Room</button>
    </div>
</div>

<button id="chat-toggle-btn" onclick="toggleChat()">💬<span id="chat-badge" class="badge pulse-anim" style="display:none;">0</span></button>
<div id="chat-container">
    <div id="chat-header"><span>💬 Global Chat</span><button onclick="toggleChat()">✕</button></div>
    <div id="chat-messages"></div>
    <div id="chat-input-row"><input type="text" id="chat-input" placeholder="Type..." maxlength="200"><button onclick="sendChat()">Send</button></div>
</div>

<script>
// Global state for UI preservation
let onlineSecretRevealed = false;
let onlineRevealedData = null;
let localSecretRevealed = false;
let localRevealedData = null;

// Track dropdown states
let voteAsSelectValue = '';
let onlineViewerSelectValue = '';
let localViewerSelectValue = '';
let onlineGameTypeValue = '';
let manualDeviceAssignValue = '';

// Chat
let chatVisible = false, chatUnread = 0, chatUsername = localStorage.getItem('chatUsername') || '', lastMsgCount = 0;

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerText = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function toggleChat() {
    chatVisible = !chatVisible;
    document.getElementById('chat-container').classList.toggle('open', chatVisible);
    const badge = document.getElementById('chat-badge');
    if (chatVisible) {
        badge.style.display = 'none';
        badge.classList.remove('pulse-anim');
        chatUnread = 0;
        document.getElementById('chat-input').focus();
        loadChat();
    }
}
function sendChat() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;
    if (!chatUsername) {
        chatUsername = prompt("Username:") || "Anonymous";
        localStorage.setItem('chatUsername', chatUsername);
    }
    fetch('/global_chat/send', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({username: chatUsername, text}) }).then(() => { input.value = ''; loadChat(); });
}
function loadChat() {
    fetch('/global_chat/get_messages').then(r => r.json()).then(messages => {
        const container = document.getElementById('chat-messages');
        container.innerHTML = messages.map(m => `<div class="chat-msg"><span class="username">${m.username}</span><span class="text">${m.text}</span><span class="time">${m.time}</span></div>`).join('');
        container.scrollTop = container.scrollHeight;
        if (!chatVisible && messages.length > lastMsgCount) {
            chatUnread += (messages.length - lastMsgCount);
            const badge = document.getElementById('chat-badge');
            badge.style.display = 'flex';
            badge.textContent = chatUnread;
            badge.classList.add('pulse-anim');
        }
        lastMsgCount = messages.length;
    });
}
document.getElementById('chat-input').addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });
setInterval(loadChat, 3000);

function showScreen(id) { document.querySelectorAll('.screen').forEach(el => el.classList.remove('active-screen')); document.getElementById(id).classList.add('active-screen'); }
function selectMode(mode) { if (mode === 'LOCAL') { showScreen('screen-local-start'); } else { showScreen('screen-online-start'); refreshOnlineGames(); } }
function goToLanding() {
    if (pollInterval) clearInterval(pollInterval);
    currentRoom = null;
    showScreen('screen-landing');
}

function showRules() {
    const rules = `
        <div class="modal-overlay" onclick="this.remove()">
            <div class="modal-content" onclick="event.stopPropagation()">
                <h3>📖 How to Play</h3>
                <h4>🦎 Chameleon</h4>
                <p>All players except one (the Chameleon) know a secret word. Players take turns saying a word related to the secret word. The Chameleon must blend in without knowing the word. After discussion, vote on who you think the Chameleon is!</p>
                <h4>🃏 Bluff</h4>
                <p>Players take turns playing cards face down, claiming a rank. You can lie about what you're playing. If someone thinks you're lying, they can call your bluff. If they're right, you pick up the pile. If they're wrong, they pick it up. First to empty their hand wins!</p>
                <button class="btn" onclick="this.closest('.modal-overlay').remove()">Close</button>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', rules);
}

// Local game state
let localPlayers = 3, localUseCodes = true;
function selectLocalPlayers(num) { localPlayers = num; document.querySelectorAll('#local-player-grid .p-opt').forEach(el => el.classList.toggle('selected', parseInt(el.innerText) === num)); }
function toggleLocalCodes() {
    localUseCodes = !localUseCodes;
    const btn = document.getElementById('btn-local-toggle-codes');
    btn.classList.toggle('on', localUseCodes);
    btn.innerText = localUseCodes ? '🔒 Secret Codes: ON' : '🔓 Secret Codes: OFF';
}
function startLocalGame() { fetch('/local/start_game', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({players_count: localPlayers, use_codes: localUseCodes}) }).then(() => pollLocalState()); }
function revealLocalRole() {
    fetch('/local/get_role', { method: 'POST' }).then(r => r.json()).then(data => {
        document.getElementById('local-reveal-role-btn').style.display = 'none';
        document.getElementById('local-role-details').style.display = 'block';
        document.getElementById('local-assigned-code').innerText = data.code;
        document.getElementById('local-role-message').innerHTML = data.is_chameleon ? '<span style="color:var(--warning)">You are the CHAMELEON</span>' : '<span style="color:var(--accent)">You are Clued-In</span>';
    });
}
function nextLocalPlayer() { fetch('/local/next_player', { method: 'POST' }).then(() => pollLocalState()); }
function verifyLocalCode() {
    let payload = localUseCodes ? { code: document.getElementById('local-player-code-input').value } : { player_idx: document.getElementById('local-viewer-select').value };
    fetch('/local/verify_code', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }).then(r => r.json()).then(data => {
        if (!data.valid) { showToast("Invalid selection/code."); return; }
        localSecretRevealed = true;
        localRevealedData = data;
        document.getElementById('local-code-input-area').style.display = 'none';
        document.getElementById('local-no-code-area').style.display = 'none';
        document.getElementById('local-decrypted-info').style.display = 'block';
        if (data.is_chameleon) {
            document.getElementById('local-result-alert').innerHTML = 'You are the <span style="color:var(--warning)">CHAMELEON</span>. Blend in!';
            renderGrid('local-grid-table', null, null);
        } else {
            document.getElementById('local-result-alert').innerHTML = `Target: <span style="color:var(--accent)">${data.col}${data.row}</span>`;
            renderGrid('local-grid-table', data.col, data.row);
        }
    });
}
function resetLocalGrid() {
    localSecretRevealed = false;
    localRevealedData = null;
    document.getElementById('local-decrypted-info').style.display = 'none';
    if(localUseCodes) document.getElementById('local-code-input-area').style.display = 'block';
    else document.getElementById('local-no-code-area').style.display = 'block';
    document.getElementById('local-player-code-input').value = '';
    renderGrid('local-grid-table', null, null);
}
function pollLocalState() {
    fetch('/local/state', { method: 'POST' }).then(r => r.json()).then(data => {
        localUseCodes = data.use_codes;
        if (data.phase === 'ROLES') {
            localSecretRevealed = false;
            localRevealedData = null;
            showScreen('screen-local-roles');
            document.getElementById('local-player-turn-header').innerText = `Player ${data.current_player_idx + 1}'s Turn`;
            document.getElementById('local-reveal-role-btn').style.display = 'block';
            document.getElementById('local-role-details').style.display = 'none';
        } else if (data.phase === 'PUBLIC_GRID') {
            showScreen('screen-local-grid');
            document.getElementById('local-topic-title').innerText = data.topic_name;
            window.currentGrid = data.grid;
            // Always render grid
            if (localRevealedData && !localRevealedData.is_chameleon) {
                renderGrid('local-grid-table', localRevealedData.col, localRevealedData.row);
            } else {
                renderGrid('local-grid-table', null, null);
            }
            // Preserve reveal state
            if (localSecretRevealed && localRevealedData) {
                document.getElementById('local-code-input-area').style.display = 'none';
                document.getElementById('local-no-code-area').style.display = 'none';
                document.getElementById('local-decrypted-info').style.display = 'block';
                if (localRevealedData.is_chameleon) {
                    document.getElementById('local-result-alert').innerHTML = 'You are the <span style="color:var(--warning)">CHAMELEON</span>. Blend in!';
                } else {
                    document.getElementById('local-result-alert').innerHTML = `Target: <span style="color:var(--accent)">${localRevealedData.col}${localRevealedData.row}</span>`;
                }
            } else {
                if (localUseCodes) { 
                    document.getElementById('local-code-input-area').style.display = 'block'; 
                    document.getElementById('local-no-code-area').style.display = 'none'; 
                } else {
                    document.getElementById('local-code-input-area').style.display = 'none';
                    document.getElementById('local-no-code-area').style.display = 'block';
                    const viewerSelect = document.getElementById('local-viewer-select');
                    if (viewerSelect) {
                        const currentValue = viewerSelect.value || localViewerSelectValue;
                        viewerSelect.innerHTML = Array.from({length: data.players_count}, (_,i) => `<option value="${i}">Player ${i+1}</option>`).join('');
                        if (currentValue !== '') {
                            viewerSelect.value = currentValue;
                            localViewerSelectValue = currentValue;
                        }
                    }
                }
                document.getElementById('local-decrypted-info').style.display = 'none';
                if (!document.activeElement || document.activeElement.id !== 'local-player-code-input') {
                    document.getElementById('local-player-code-input').value = '';
                }
            }
        }
    });
}

function renderGrid(tableId, targetCol, targetRow) {
    const cols = ['A','B','C','D'];
    let html = '<tr><th></th>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr>';
    window.currentGrid.forEach((rowWords, rowIdx) => {
        html += `<tr><td class="row-header">${rowIdx+1}</td>`;
        rowWords.forEach((word, colIdx) => {
            const isTarget = (targetCol === cols[colIdx] && targetRow == (rowIdx+1));
            html += `<td class="${isTarget ? 'highlight' : ''}">${word}</td>`;
        });
        html += '</tr>';
    });
    document.getElementById(tableId).innerHTML = html;
}

// Topic modal
function openTopicModal(prefix) {
    const topicNames = {{ topics|tojson }};
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content">
            <h3>🔀 Change Topic</h3>
            <p style="color:var(--text-muted); font-size:14px;">Select a topic or use random:</p>
            <button class="btn btn-topic" onclick="changeTopic('${prefix}', 'random'); this.closest('.modal-overlay').remove();">🎲 Random Topic</button>
            <div class="topic-grid">
                ${topicNames.map(t => `<div class="topic-item" onclick="changeTopic('${prefix}', '${t}'); this.closest('.modal-overlay').remove();">${t}</div>`).join('')}
            </div>
            <button class="btn" style="background:#475569;" onclick="this.closest('.modal-overlay').remove();">Cancel</button>
        </div>
    `;
    document.body.appendChild(modal);
}

function changeTopic(prefix, type) {
    let payload = { type: 'random' };
    if (type !== 'random') {
        payload = { type: 'specific', topic: type };
    }
    const endpoint = prefix === 'local' ? '/local/change_topic' : '/online/change_topic';
    if (prefix === 'online') payload.room_id = currentRoom;
    fetch(endpoint, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) })
        .then(r => r.json())
        .then(data => {
            if (data.error) showToast(data.error);
            else showToast('Topic changed!');
        });
}

// Online
let currentRoom = null, isHost = false, myPlayerId = null, pollInterval = null;
let selectedBluffCards = [];
window.currentRevealId = null;
let roleRevealed = false;

function refreshOnlineGames() {
    fetch('/online/list_games').then(r => r.json()).then(games => {
        const list = document.getElementById('online-game-list');
        list.innerHTML = games.length ? games.map(g => `<div style="background:#1e293b; padding:10px; border-radius:8px; margin:5px 0; display:flex; justify-content:space-between; align-items:center;"><div>${g.host_name}'s Room<br><small>${g.player_count} players | ${g.game_type}</small></div><button class="btn btn-small btn-start" onclick="joinOnlineGame('${g.id}')">Join</button></div>`).join('') : '<p>No active rooms.</p>';
    });
}
setInterval(() => { if (document.getElementById('screen-online-start').classList.contains('active-screen')) refreshOnlineGames(); }, 5000);

function createOnlineGame() {
    const name = document.getElementById('online-player-name').value;
    fetch('/online/create_game', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name}) })
        .then(r => r.json()).then(data => { currentRoom = data.room_id; isHost = true; startOnlinePoll(); });
}
function joinOnlineGame(rid) {
    const name = document.getElementById('online-player-name').value;
    fetch('/online/join_game', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: rid, name}) })
        .then(r => r.json()).then(data => { if(data.error) showToast(data.error); else { currentRoom = rid; isHost = false; startOnlinePoll(); } });
}
function leaveOnlineGame() {
    fetch('/online/leave_room', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom}) }).then(() => goToLanding());
}
function disbandRoom() {
    if (confirm('Are you sure you want to disband this room?')) {
        fetch('/online/leave_room', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom}) })
            .then(() => goToLanding());
    }
}

function startOnlinePoll() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(onlinePollState, 1000);
    onlinePollState();
}

function setGamemode(type) { 
    onlineGameTypeValue = type;
    fetch('/online/set_game', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, game_type: type}) }); 
}
function requestGamemode(type) { fetch('/online/request_gamemode', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, mode: type}) }); }
function toggleOnlineCodes() { fetch('/online/toggle_codes', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, use_codes: !window.onlineUseCodes}) }); }
function kickPlayer(pid) { fetch('/online/remove_player', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, player_id: pid}) }); }
function addManualPlayer() {
    const name = document.getElementById('manual-player-name').value;
    const device_id = document.getElementById('manual-device-assign').value;
    fetch('/online/add_manual_player', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, name, device_id}) }).then(() => document.getElementById('manual-player-name').value='');
}
function startOnlineGame() { fetch('/online/start_game', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom}) }).then(r=>r.json()).then(data=>{if(data.error)showToast(data.error);}); }
function nextRound() { fetch('/online/next_round', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom}) }).then(r=>r.json()).then(data=>{if(data.error)showToast(data.error);}); }
function restartOnlineGame() { fetch('/online/restart', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom}) }); }

function updateLogBox(elementId, messages) {
    const logBox = document.getElementById(elementId);
    if (!logBox) return;
    const newHtml = messages.map(m => `<div>${m}</div>`).join('');
    if (logBox.innerHTML !== newHtml) {
        logBox.innerHTML = newHtml;
        logBox.scrollTop = logBox.scrollHeight;
    }
}

function updateElementIfChanged(element, newHtml) {
    if (element.innerHTML !== newHtml) {
        element.innerHTML = newHtml;
        return true;
    }
    return false;
}

// Prevent dropdown reset
document.addEventListener('change', function(e) {
    if (e.target.id === 'online-game-type') onlineGameTypeValue = e.target.value;
    else if (e.target.id === 'vote-as-select') voteAsSelectValue = e.target.value;
    else if (e.target.id === 'online-viewer-select') onlineViewerSelectValue = e.target.value;
    else if (e.target.id === 'local-viewer-select') localViewerSelectValue = e.target.value;
    else if (e.target.id === 'manual-device-assign') manualDeviceAssignValue = e.target.value;
});

function onlinePollState() {
    fetch(`/online/room_state?room=${currentRoom}`).then(r => r.json()).then(data => {
        if (data.error) { goToLanding(); return; }
        myPlayerId = data.my_id;
        isHost = data.is_host;
        window.onlineUseCodes = data.use_codes;

        if (data.phase === 'LOBBY') {
            onlineSecretRevealed = false;
            onlineRevealedData = null;
            roleRevealed = false;
            updateLogBox('online-game-log', data.game_log);
            showScreen('screen-online-lobby');
            document.getElementById('host-game-settings').style.display = isHost ? 'block' : 'none';
            document.getElementById('player-request-gamemode').style.display = isHost ? 'none' : 'block';
            document.getElementById('btn-start-online').style.display = isHost ? 'block' : 'none';
            document.getElementById('online-wait-msg').style.display = isHost ? 'none' : 'block';
            document.getElementById('btn-disband-room').style.display = isHost ? 'block' : 'none';
            if (isHost) {
                const gameTypeSelect = document.getElementById('online-game-type');
                if (gameTypeSelect && onlineGameTypeValue) {
                    gameTypeSelect.value = onlineGameTypeValue;
                } else if (gameTypeSelect) {
                    gameTypeSelect.value = data.game_type;
                    onlineGameTypeValue = data.game_type;
                }
            }

            if (data.game_type === 'bluff') {
                document.getElementById('chameleon-lobby-features').style.display = 'none';
                document.getElementById('online-wait-msg').innerText = "Bluff mode selected. Waiting for host to start...";
            } else {
                document.getElementById('chameleon-lobby-features').style.display = 'block';
                document.getElementById('online-wait-msg').innerText = "Chameleon mode selected. Waiting for host...";
                document.getElementById('host-add-manual').style.display = isHost ? 'block' : 'none';
                
                if (isHost) {
                    const onlinePlayers = data.players.filter(p => !p.is_manual);
                    const devSelect = document.getElementById('manual-device-assign');
                    if (devSelect) {
                        const currentDev = devSelect.value || manualDeviceAssignValue;
                        devSelect.innerHTML = onlinePlayers.map(p => `<option value="${p.id}">${p.name}'s Device</option>`).join('');
                        if (currentDev && onlinePlayers.some(p => p.id === currentDev)) {
                            devSelect.value = currentDev;
                            manualDeviceAssignValue = currentDev;
                        }
                    }
                }
                
                const btnCodes = document.getElementById('btn-online-toggle-codes');
                btnCodes.style.display = isHost ? 'inline-block' : 'none';
                btnCodes.classList.toggle('on', data.use_codes);
                btnCodes.innerText = data.use_codes ? '🔒 Codes: ON' : '🔓 Codes: OFF';
                
                document.getElementById('online-players-list').innerHTML = data.players.map(p => {
                    const kickBtn = (isHost && p.id !== myPlayerId) ? `<span style="cursor:pointer;color:var(--danger);margin-left:5px;font-weight:bold;" onclick="kickPlayer('${p.id}')">✕</span>` : '';
                    const manualTag = p.is_manual ? ' 📱' : '';
                    return `<span class="badge" style="background:#475569;">${p.name}${manualTag}${kickBtn}</span>`;
                }).join(' ');
            }
        } 
        else if (data.phase.startsWith('BLUFF_')) {
            onlineSecretRevealed = false;
            onlineRevealedData = null;
            roleRevealed = false;
            showScreen('screen-online-bluff');
            updateLogBox('bluff-game-log', data.game_log);
            renderBluffGame(data);
        }
        else {
            if (data.phase === 'ROLE_REVEAL') {
                onlineSecretRevealed = false;
                onlineRevealedData = null;
                showScreen('screen-online-roles');
                
                if (!roleRevealed && !data.already_revealed) {
                    window.currentRevealId = data.current_reveal_id;
                    document.getElementById('online-player-turn-header').innerText = `${data.current_reveal_name}'s Turn`;
                    document.getElementById('online-reveal-role-btn').style.display = 'block';
                    document.getElementById('online-role-details').style.display = 'none';
                } else if (roleRevealed) {
                    document.getElementById('online-reveal-role-btn').style.display = 'none';
                    document.getElementById('online-role-details').style.display = 'block';
                } else {
                    document.getElementById('online-player-turn-header').innerText = `Done. Waiting for others...`;
                    document.getElementById('online-reveal-role-btn').style.display = 'none';
                    document.getElementById('online-role-details').style.display = 'none';
                }
            } else if (data.phase === 'PLAYING') {
                roleRevealed = false;
                showScreen('screen-online-grid');
                updateLogBox('online-chameleon-log', data.game_log);
                document.getElementById('online-topic-title').innerText = data.topic_name;
                window.currentGrid = data.grid;
                
                // Always render grid
                if (onlineRevealedData && !onlineRevealedData.is_chameleon) {
                    renderGrid('online-grid-table', onlineRevealedData.col, onlineRevealedData.row);
                } else {
                    renderGrid('online-grid-table', null, null);
                }
                
                document.getElementById('btn-online-change-topic').style.display = isHost ? 'inline-block' : 'none';
                document.getElementById('btn-start-voting').style.display = isHost ? 'inline-block' : 'none';
                
                // Preserve secret reveal state
                if (onlineSecretRevealed && onlineRevealedData) {
                    document.getElementById('online-code-input-area').style.display = 'none';
                    document.getElementById('online-no-code-area').style.display = 'none';
                    document.getElementById('online-decrypted-info').style.display = 'block';
                    if (onlineRevealedData.is_chameleon) {
                        document.getElementById('online-result-alert').innerHTML = 'You are the <span style="color:var(--warning)">CHAMELEON</span>.';
                    } else {
                        document.getElementById('online-result-alert').innerHTML = `Target: <span style="color:var(--accent)">${onlineRevealedData.col}${onlineRevealedData.row}</span>`;
                    }
                } else {
                    document.getElementById('online-code-input-area').style.display = data.use_codes ? 'block' : 'none';
                    document.getElementById('online-no-code-area').style.display = !data.use_codes ? 'block' : 'none';
                    if (!data.use_codes) {
                        const viewerSelect = document.getElementById('online-viewer-select');
                        if (viewerSelect) {
                            const currentValue = viewerSelect.value || onlineViewerSelectValue;
                            viewerSelect.innerHTML = data.device_players.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
                            if (currentValue && data.device_players.some(p => p.id === currentValue)) {
                                viewerSelect.value = currentValue;
                                onlineViewerSelectValue = currentValue;
                            }
                        }
                    }
                    document.getElementById('online-decrypted-info').style.display = 'none';
                    if (!document.activeElement || document.activeElement.id !== 'online-player-code-input') {
                        document.getElementById('online-player-code-input').value = '';
                    }
                }
            } else if (data.phase === 'VOTING') {
                onlineSecretRevealed = false;
                onlineRevealedData = null;
                roleRevealed = false;
                showScreen('screen-online-voting');
                
                // Preserve vote dropdown
                const voteAsSelect = document.getElementById('vote-as-select');
                if (voteAsSelect) {
                    const currentVote = voteAsSelect.value || voteAsSelectValue;
                    voteAsSelect.innerHTML = data.device_players.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
                    if (currentVote && data.device_players.some(p => p.id === currentVote)) {
                        voteAsSelect.value = currentVote;
                        voteAsSelectValue = currentVote;
                    }
                }
                
                document.getElementById('vote-targets').innerHTML = data.players.map(p => `<button class="btn btn-option" onclick="castOnlineVote('${p.id}')">${p.name}</button>`).join('');
                document.getElementById('btn-end-voting').style.display = isHost ? 'block' : 'none';
                document.getElementById('vote-as-select').style.display = 'block';
            } else if (data.phase === 'RESULTS') {
                onlineSecretRevealed = false;
                onlineRevealedData = null;
                roleRevealed = false;
                showScreen('screen-online-voting');
                let html = `<h3 style="color:var(--success);">Word: ${data.secret_word}</h3>`;
                html += `<h4 style="color:var(--warning);">Chameleon: ${data.chameleon_name}</h4>`;
                if (data.chameleon_caught !== null) {
                    const resultText = data.chameleon_caught ? 'The Chameleon was caught!' : 'The Chameleon escaped!';
                    html += `<p style="font-size:18px; font-weight:bold;">${resultText}</p>`;
                }
                html += `<div>${data.vote_results.map(v => `<p>${v.name}: ${v.count} votes</p>`).join('')}</div>`;
                if (isHost) {
                    html += `<button class="btn btn-start" onclick="nextRound()">🔄 Play Again</button>`;
                    html += `<button class="btn" style="background:#475569;" onclick="restartOnlineGame()">🏠 Return to Lobby</button>`;
                }
                document.getElementById('vote-targets').innerHTML = html;
                document.getElementById('vote-as-select').style.display = 'none';
                document.getElementById('btn-end-voting').style.display = 'none';
            }
        }
    });
}

function revealOnlineRole() {
    fetch('/online/reveal_role', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, target_id: window.currentRevealId}) }).then(r=>r.json()).then(data => {
        if (data.error) { showToast(data.error); return; }
        roleRevealed = true;
        document.getElementById('online-reveal-role-btn').style.display = 'none';
        document.getElementById('online-role-details').style.display = 'block';
        document.getElementById('online-assigned-code').innerText = data.code;
        document.getElementById('online-role-alert-box').innerHTML = data.is_chameleon ? '<span style="color:var(--warning)">You are the CHAMELEON</span>' : '<span style="color:var(--accent)">You are Clued-In</span>';
    });
}

function nextOnlinePlayer() { 
    roleRevealed = false;
    document.getElementById('online-role-details').style.display = 'none';
    fetch('/online/player_done', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom}) }).then(() => onlinePollState());
}

function verifyOnlineCode() {
    let payload = { room_id: currentRoom };
    if (window.onlineUseCodes) {
        payload.code = document.getElementById('online-player-code-input').value;
    } else {
        payload.player_id = document.getElementById('online-viewer-select').value;
    }
    fetch('/online/verify_code', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }).then(r=>r.json()).then(data => {
        if (!data.valid) { showToast("Invalid code or unauthorized."); return; }
        onlineSecretRevealed = true;
        onlineRevealedData = data;
        document.getElementById('online-code-input-area').style.display = 'none';
        document.getElementById('online-no-code-area').style.display = 'none';
        document.getElementById('online-decrypted-info').style.display = 'block';
        if (data.is_chameleon) {
            document.getElementById('online-result-alert').innerHTML = 'You are the <span style="color:var(--warning)">CHAMELEON</span>.';
            renderGrid('online-grid-table', null, null);
        } else {
            document.getElementById('online-result-alert').innerHTML = `Target: <span style="color:var(--accent)">${data.col}${data.row}</span>`;
            renderGrid('online-grid-table', data.col, data.row);
        }
    });
}

function resetOnlineGrid() {
    onlineSecretRevealed = false;
    onlineRevealedData = null;
    document.getElementById('online-decrypted-info').style.display = 'none';
    if (window.onlineUseCodes) {
        document.getElementById('online-code-input-area').style.display = 'block';
        document.getElementById('online-player-code-input').value = '';
    } else {
        document.getElementById('online-no-code-area').style.display = 'block';
    }
    renderGrid('online-grid-table', null, null);
}

function startOnlineVoting() { fetch('/online/start_voting_phase', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom}) }); }
function castOnlineVote(targetId) {
    const voterId = document.getElementById('vote-as-select').value;
    fetch('/online/cast_vote', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, voter_id: voterId, target_id: targetId}) }).then(r=>r.json()).then(data => { if(data.error) showToast(data.error); });
}
function endOnlineVoting() { fetch('/online/end_voting', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom}) }); }

// Bluff rendering
function renderBluffGame(data) {
    const isMyTurn = (data.current_player === myPlayerId);
    const currentHandLength = data.your_hand ? data.your_hand.length : 0;
    if (!isMyTurn || currentHandLength !== window.prevHandLength) {
        selectedBluffCards = [];
    }
    window.prevHandLength = currentHandLength;

    let playersHtml = data.players.map(p => {
        let cls = 'player-tag';
        if (p.id === data.current_player) cls += ' current';
        return `<span class="${cls}">${p.name} (${p.card_count})</span>`;
    }).join(' ');
    updateElementIfChanged(document.getElementById('bluff-players'), playersHtml);
    
    if (data.phase === 'BLUFF_FINISHED') {
        document.getElementById('bluff-winner').style.display = 'block';
        const winnerObj = data.players.find(p => p.id === data.winner);
        const isLoser = winnerObj && winnerObj.card_count > 0;
        const title = isLoser ? `🤡 ${winnerObj.name} is the last one left! (Loser)` : `🏆 ${winnerObj.name} Wins!`;
        document.getElementById('bluff-winner').innerHTML = `
            <h3 style="${isLoser ? 'color:var(--danger);' : 'color:var(--success);'}">${title}</h3>
            <button class="btn btn-start" onclick="nextRound()">🔄 Play Again</button>
            <button class="btn" style="background:#475569;" onclick="restartOnlineGame()">🏠 Return to Lobby</button>
        `;
        document.getElementById('bluff-controls').innerHTML = '';
        document.getElementById('bluff-turn').innerText = '';
        return;
    } else {
        document.getElementById('bluff-winner').style.display = 'none';
    }

    let turnMsg = data.current_player === myPlayerId ? '▶ It is your turn!' : `⏳ Waiting for ${data.players.find(p=>p.id === data.current_player)?.name}...`;
    document.getElementById('bluff-turn').innerText = turnMsg;

    const handBox = document.getElementById('bluff-hand');
    let handHtml = '<div style="font-weight:bold; margin-top:10px;">Your Hand:</div><div class="hand">';
    if (data.your_hand && data.your_hand.length > 0) {
        data.your_hand.forEach((card, idx) => {
            const suit = card.slice(-1);
            const color = (suit === '♥' || suit === '♦') ? 'red' : '';
            const sel = selectedBluffCards.includes(idx) ? 'selected' : '';
            handHtml += `<div class="card-item ${color} ${sel}" onclick="toggleBluffCard(${idx})">${card}</div>`;
        });
    } else {
        handHtml += '<p style="color:var(--text-muted);">No cards</p>';
    }
    handHtml += '</div>';
    if (selectedBluffCards.length > 0) {
        handHtml += `<button class="btn btn-small" onclick="clearBluffSelection()" style="background:#475569;">Clear Selection (${selectedBluffCards.length})</button>`;
    }
    updateElementIfChanged(handBox, handHtml);

    const controls = document.getElementById('bluff-controls');
    let controlsHtml = '';

    if (data.phase === 'BLUFF_PLAYING' && isMyTurn) {
        if (!data.played_by) {
            controlsHtml = `
                <div style="margin-bottom: 10px;">
                    <label>Choose rank to claim:</label> 
                    <select id="bluff-rank" style="width:auto; display:inline-block; padding:8px; margin:8px;">
                        ${['2','3','4','5','6','7','8','9','10','J','Q','K','A'].map(r=>`<option value="${r}">${r}</option>`).join('')}
                    </select> 
                    <button class="btn btn-start btn-small" onclick="playBluffCards()">🃏 Play Cards</button>
                </div>
            `;
        } else {
            controlsHtml = `
                <div style="margin-bottom: 10px; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">
                    <p style="color:var(--text-muted);">Current claim: <strong>${data.claimed_rank}s</strong> by ${data.players.find(p=>p.id===data.played_by)?.name}</p>
                    <div style="display:flex; flex-wrap:wrap; gap:8px; justify-content:center;">
                        <button class="btn btn-start btn-small" onclick="playMoreCards()">➕ Play Cards (same rank)</button>
                        <button class="btn btn-danger btn-small" onclick="bluffAction('call_bluff')">🚨 Call Bluff!</button>
                        <button class="btn btn-small" onclick="bluffAction('pass_bluff')" style="background:#475569;">⏭️ Pass</button>
                    </div>
                </div>
            `;
        }
    } else {
        controlsHtml = '';
    }

    if (controls.innerHTML !== controlsHtml) {
        controls.innerHTML = controlsHtml;
    }
}

function toggleBluffCard(idx) {
    const pos = selectedBluffCards.indexOf(idx);
    if (pos > -1) selectedBluffCards.splice(pos, 1);
    else selectedBluffCards.push(idx);
    onlinePollState();
}

function clearBluffSelection() {
    selectedBluffCards = [];
    onlinePollState();
}

function playBluffCards() {
    if (selectedBluffCards.length === 0) { showToast('Select cards to play.'); return; }
    const rank = document.getElementById('bluff-rank').value;
    fetch('/online/bluff_action', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, action: 'play_cards', indices: selectedBluffCards, rank}) })
        .then(r=>r.json()).then(data => { if(data.error) showToast(data.error); else { selectedBluffCards = []; } });
}

function playMoreCards() {
    if (selectedBluffCards.length === 0) { showToast('Select cards to play.'); return; }
    fetch('/online/bluff_action', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, action: 'play_more', indices: selectedBluffCards}) })
        .then(r=>r.json()).then(data => { if(data.error) showToast(data.error); else { selectedBluffCards = []; } });
}

function bluffAction(act) { 
    fetch('/online/bluff_action', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({room_id: currentRoom, action: act}) })
        .then(r=>r.json()).then(data => { if(data.error) showToast(data.error); else { selectedBluffCards = []; } });
}
</script>
</body>
</html>
"""

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
