from flask import Flask, render_template_string, jsonify, request, session
import random
import string
import uuid
import time
import html

app = Flask(__name__)
app.secret_key = "chameleon_secret_key_change_in_production"

# --- GLOBAL CHAT (no room required) ---
GLOBAL_CHAT_MESSAGES = []
MAX_CHAT_MESSAGES = 100

def add_global_message(username, text):
    timestamp = time.strftime("%H:%M")
    GLOBAL_CHAT_MESSAGES.append({
        'username': html.escape(username)[:20],
        'text': html.escape(text)[:200],
        'time': timestamp
    })
    if len(GLOBAL_CHAT_MESSAGES) > MAX_CHAT_MESSAGES:
        GLOBAL_CHAT_MESSAGES.pop(0)

# --- GAME DATA ---
TOPIC_CARDS = {
    "Food & Drink": [
        ["Pizza", "Sushi", "Taco", "Burger"],
        ["Pasta", "Curry", "Ramen", "Burrito"],
        ["Coffee", "Espresso", "Matcha", "Boba"],
        ["Donut", "Ice Cream", "Pancake", "Waffle"]
    ],
    "Movies & Cinema": [
        ["Titanic", "Inception", "Avatar", "Jaws"],
        ["Matrix", "Star Wars", "Avengers", "Jurassic Park"],
        ["Godfather", "Gladiator", "Oppenheimer", "Interstellar"],
        ["Shrek", "Toy Story", "Frozen", "Finding Nemo"]
    ],
    "Animals & Wildlife": [
        ["Lion", "Elephant", "Giraffe", "Cheetah"],
        ["Penguin", "Flamingo", "Dolphin", "Octopus"],
        ["Kangaroo", "Koala", "Panda", "Grizzly Bear"],
        ["Eagle", "Owl", "Shark", "Chameleon"]
    ],
    "Countries & Nations": [
        ["Japan", "Brazil", "France", "Canada"],
        ["Egypt", "Australia", "Italy", "India"],
        ["Mexico", "Germany", "Greece", "Spain"],
        ["South Korea", "Norway", "Kenya", "Thailand"]
    ],
    "Superheroes & Villains": [
        ["Spider-Man", "Batman", "Superman", "Iron Man"],
        ["Wonder Woman", "Thor", "Captain America", "Hulk"],
        ["Black Panther", "Flash", "Aquaman", "Doctor Strange"],
        ["Joker", "Thanos", "Loki", "Venom"]
    ],
    "Video Games": [
        ["Minecraft", "Fortnite", "Pokemon", "Tetris"],
        ["Super Mario", "Zelda", "Pac-Man", "GTA"],
        ["Roblox", "Call of Duty", "Overwatch", "Valorant"],
        ["The Witcher", "Skyrim", "Elden Ring", "Sonic"]
    ],
    "Sports & Fitness": [
        ["Soccer", "Basketball", "Tennis", "Baseball"],
        ["Volleyball", "Golf", "Swimming", "Boxing"],
        ["Skiing", "Surfing", "Rugby", "Cricket"],
        ["Cycling", "Running", "Gymnastics", "Ice Hockey"]
    ],
    "Space & Astronomy": [
        ["Mars", "Jupiter", "Saturn", "Moon"],
        ["Black Hole", "Supernova", "Asteroid", "Comet"],
        ["Telescope", "Rocket", "Astronaut", "Milky Way"],
        ["Nebula", "Satellite", "Solar Eclipse", "Galaxy"]
    ],
    "Music Genres": [
        ["Rock", "Pop", "Jazz", "Classical"],
        ["Hip Hop", "Country", "Reggae", "Blues"],
        ["Electronic", "Folk", "R&B", "Metal"],
        ["Disco", "Punk", "Soul", "K-Pop"]
    ],
    "Mythical Creatures": [
        ["Dragon", "Unicorn", "Griffin", "Phoenix"],
        ["Mermaid", "Centaur", "Minotaur", "Pegasus"],
        ["Werewolf", "Vampire", "Goblin", "Troll"],
        ["Fairy", "Elf", "Kraken", "Yeti"]
    ],
    "School Subjects": [
        ["Math", "History", "Science", "Art"],
        ["Music", "Geography", "Literature", "P.E."],
        ["Physics", "Chemistry", "Biology", "Drama"],
        ["Computer Science", "Economics", "Languages", "Philosophy"]
    ],
    "Famous Landmarks": [
        ["Eiffel Tower", "Great Wall", "Pyramids", "Colosseum"],
        ["Taj Mahal", "Statue of Liberty", "Big Ben", "Machu Picchu"],
        ["Mount Rushmore", "Stonehenge", "Sydney Opera", "Acropolis"],
        ["Burj Khalifa", "Golden Gate", "Christ the Redeemer", "Mount Fuji"]
    ],
    "Board Games": [
        ["Chess", "Monopoly", "Scrabble", "Risk"],
        ["Catan", "Carcassonne", "Ticket to Ride", "Pandemic"],
        ["Clue", "Battleship", "Stratego", "Sorry"],
        ["Checkers", "Backgammon", "Dominoes", "Mahjong"]
    ],
    "Fictional Characters": [
        ["Sherlock Holmes", "James Bond", "Harry Potter", "Atticus Finch"],
        ["Elizabeth Bennet", "Holden Caulfield", "Jay Gatsby", "Hamlet"],
        ["Frodo Baggins", "Katniss Everdeen", "Gandalf", "Dumbledore"],
        ["Bruce Wayne", "Clark Kent", "Peter Parker", "Tony Stark"]
    ],
    "Musical Instruments": [
        ["Guitar", "Piano", "Violin", "Drums"],
        ["Flute", "Trumpet", "Saxophone", "Cello"],
        ["Harp", "Trombone", "Clarinet", "Bass"],
        ["Organ", "Mandolin", "Banjo", "Accordion"]
    ],
    "Types of Dance": [
        ["Ballet", "Tap", "Jazz", "Hip Hop"],
        ["Salsa", "Tango", "Waltz", "Foxtrot"],
        ["Breakdance", "Contemporary", "Flamenco", "Belly Dance"],
        ["Swing", "Rumba", "Cha Cha", "Bolero"]
    ]
}

def get_random_coordinates():
    cols = ['A', 'B', 'C', 'D']
    rows = [1, 2, 3, 4]
    return random.choice(cols), random.choice(rows)

# --- LOCAL (Pass & Play) ---
game_state = {
    'phase': 'START_SCREEN',
    'players_count': 4,
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

# --- ONLINE ---
ROOMS = {}
MAX_ROOM_AGE = 7200

def clean_expired_rooms():
    now = time.time()
    expired = [code for code, room in ROOMS.items() if now - room.get('created_at', now) > MAX_ROOM_AGE or len(room['players']) == 0]
    for code in expired:
        del ROOMS[code]

def generate_room_id():
    clean_expired_rooms()
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if code not in ROOMS:
            return code

def setup_new_online_round(room, category=None):
    player_ids = list(room['players'].keys())
    if len(player_ids) < 3:
        return

    room['roles'] = {}
    chameleon_id = random.choice(player_ids)
    room['chameleon_id'] = chameleon_id
    for pid in player_ids:
        room['roles'][pid] = 'CHAMELEON' if pid == chameleon_id else 'CLUED_IN'

    chameleon_count = sum(1 for r in room['roles'].values() if r == 'CHAMELEON')
    if chameleon_count != 1:
        chameleon_id = random.choice(player_ids)
        room['chameleon_id'] = chameleon_id
        for pid in player_ids:
            room['roles'][pid] = 'CHAMELEON' if pid == chameleon_id else 'CLUED_IN'

    if not category or category not in TOPIC_CARDS:
        category = random.choice(list(TOPIC_CARDS.keys()))
    grid = TOPIC_CARDS[category]
    room['topic_name'] = category
    room['grid'] = grid
    room['secret_word'] = random.choice([word for row in grid for word in row])

    shared_clued_code = str(random.randint(0, 9))
    while True:
        chameleon_code = str(random.randint(0, 9))
        if chameleon_code != shared_clued_code:
            break
    room['player_codes'] = {}
    for pid in player_ids:
        room['player_codes'][pid] = chameleon_code if room['roles'][pid] == 'CHAMELEON' else shared_clued_code

    room['col'], room['row'] = get_random_coordinates()
    room['device_current_idx'] = 0
    room['device_player_idx'] = {i: 0 for i in range(len(room['devices']))}
    room['device_revealed'] = {i: set() for i in range(len(room['devices']))}
    
    if not room.get('use_codes', True):
        room['phase'] = 'PLAYING'
    else:
        room['phase'] = 'ROLE_REVEAL'

# ---------- ROUTES ----------
@app.route('/')
def index():
    if 'player_id' not in session:
        session['player_id'] = str(uuid.uuid4())
    return render_template_string(HTML_TEMPLATE, topics=list(TOPIC_CARDS.keys()))

# ---------- GLOBAL CHAT ----------
@app.route('/global_chat/get_messages')
def global_chat_get_messages():
    return jsonify(GLOBAL_CHAT_MESSAGES[-50:])

@app.route('/global_chat/send', methods=['POST'])
def global_chat_send():
    data = request.json
    username = data.get('username', 'Anonymous').strip()[:20]
    text = data.get('text', '').strip()[:200]
    if text:
        add_global_message(username or 'Anonymous', text)
    return jsonify({'success': True})

# ---------- LOCAL ----------
@app.route('/local/state', methods=['POST'])
def local_state():
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
    players_count = int(data.get('players_count', 4))
    use_codes = data.get('use_codes', True)
    
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
    
    game_state['phase'] = 'ROLES' if use_codes else 'PUBLIC_GRID'
    return jsonify({'success': True})

@app.route('/local/get_role', methods=['POST'])
def local_get_role():
    idx = game_state['current_player_idx']
    role = game_state['roles'][idx]
    code = game_state['player_codes'][idx]
    return jsonify({'player': idx+1, 'is_chameleon': (role == 'CHAMELEON'), 'code': code})

@app.route('/local/next_player', methods=['POST'])
def local_next_player():
    game_state['current_player_idx'] += 1
    if game_state['current_player_idx'] >= game_state['players_count']:
        game_state['phase'] = 'PUBLIC_GRID'
    return jsonify({'success': True})

@app.route('/local/verify_code', methods=['POST'])
def local_verify_code():
    use_codes = game_state['use_codes']
    
    if use_codes:
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
    req_type = request.json.get('type')
    if req_type == 'random':
        topic_name, grid = random.choice(list(TOPIC_CARDS.items()))
    else:
        topic_name = request.json.get('topic')
        grid = TOPIC_CARDS.get(topic_name, game_state['grid'])
    game_state['topic_name'] = topic_name
    game_state['grid'] = grid
    game_state['col'], game_state['row'] = get_random_coordinates()
    return jsonify({'success': True})

@app.route('/local/restart', methods=['POST'])
def local_restart():
    game_state['phase'] = 'START_SCREEN'
    return jsonify({'success': True})

# ---------- ONLINE ----------
@app.route('/online/list_games')
def online_list_games():
    clean_expired_rooms()
    games = []
    for room_id, room in ROOMS.items():
        games.append({
            'id': room_id,
            'host_name': room['players'][room['host_id']]['name'],
            'player_count': len(room['players']),
            'phase': room['phase']
        })
    return jsonify(games)

@app.route('/online/create_game', methods=['POST'])
def online_create_game():
    player_id = session.get('player_id')
    name = request.json.get('name', 'Host').strip()[:12] or 'Host'
    room_id = generate_room_id()
    ROOMS[room_id] = {
        'host_id': player_id,
        'phase': 'LOBBY',
        'players': {player_id: {'name': name, 'is_host': True, 'is_manual': False}},
        'roles': {},
        'player_codes': {},
        'votes': {},
        'topic_name': '',
        'grid': [],
        'chameleon_id': None,
        'secret_word': '',
        'devices': [[player_id]], 
        'device_current_idx': 0,
        'device_player_idx': {0: 0},
        'device_revealed': {0: set()},
        'col': '',
        'row': 0,
        'created_at': time.time(),
        'use_codes': True
    }
    return jsonify({'room_id': room_id, 'is_host': True})

@app.route('/online/join_game', methods=['POST'])
def online_join_game():
    player_id = session.get('player_id')
    name = request.json.get('name', 'Player').strip()[:12] or 'Player'
    room_id = request.json.get('room_id')
    if room_id not in ROOMS:
        return jsonify({'success': False, 'error': 'Game not found.'})
    room = ROOMS[room_id]
    if room['phase'] != 'LOBBY':
        return jsonify({'success': False, 'error': 'Game already in progress.'})
    if player_id in room['players']:
        return jsonify({'success': False, 'error': 'Already in game.'})
    
    room['players'][player_id] = {'name': name, 'is_host': False, 'is_manual': False}
    room['devices'].append([player_id])
    room['device_player_idx'] = {i: 0 for i in range(len(room['devices']))}
    room['device_revealed'] = {i: set() for i in range(len(room['devices']))}
    return jsonify({'success': True, 'room_id': room_id, 'is_host': False})

@app.route('/online/add_manual_player', methods=['POST'])
def online_add_manual_player():
    room_id = request.json.get('room_id')
    player_id = session.get('player_id')
    room = ROOMS.get(room_id)
    if not room or player_id != room['host_id']:
        return jsonify({'error': 'Host required'}), 403
    name = request.json.get('name', 'Player').strip()[:12] or 'Player'
    manual_id = f"manual_{int(time.time())}_{random.randint(100,999)}"
    room['players'][manual_id] = {'name': name, 'is_host': False, 'is_manual': True}
    room['devices'].append([manual_id])
    room['device_player_idx'] = {i: 0 for i in range(len(room['devices']))}
    room['device_revealed'] = {i: set() for i in range(len(room['devices']))}
    return jsonify({'success': True, 'player_id': manual_id})

@app.route('/online/remove_player', methods=['POST'])
def online_remove_player():
    room_id = request.json.get('room_id')
    target_id = request.json.get('player_id')
    player_id = session.get('player_id')
    room = ROOMS.get(room_id)
    
    if not room or player_id != room['host_id']:
        return jsonify({'error': 'Host required'}), 403
    if target_id == room['host_id']:
        return jsonify({'error': 'Cannot remove host'}), 400
    if target_id not in room['players']:
        return jsonify({'error': 'Player not found'}), 404
        
    for dev in room['devices']:
        if target_id in dev:
            dev.remove(target_id)
            
    room['devices'] = [dev for dev in room['devices'] if dev]
    if not room['devices']:
        room['devices'] = [[room['host_id']]]
        
    room['device_player_idx'] = {i: 0 for i in range(len(room['devices']))}
    room['device_revealed'] = {i: set() for i in range(len(room['devices']))}
    del room['players'][target_id]
    return jsonify({'success': True})

@app.route('/online/toggle_codes', methods=['POST'])
def online_toggle_codes():
    room_id = request.json.get('room_id')
    use_codes = request.json.get('use_codes')
    room = ROOMS.get(room_id)
    if room and session.get('player_id') == room['host_id']:
        room['use_codes'] = use_codes
        return jsonify({'success': True})
    return jsonify({'error': 'Unauthorized'}), 403

@app.route('/online/room_state')
def online_room_state():
    room_id = request.args.get('room')
    player_id = session.get('player_id')
    if room_id not in ROOMS:
        return jsonify({'error': 'Invalid room'})
    room = ROOMS[room_id]

    if room['host_id'] not in room['players'] and len(room['players']) > 0:
        new_host_id = list(room['players'].keys())[0]
        room['host_id'] = new_host_id
        for pid in room['players']:
            room['players'][pid]['is_host'] = (pid == new_host_id)

    players_list = []
    for pid, info in room['players'].items():
        players_list.append({'id': pid, 'name': info['name'], 'is_host': info['is_host'], 'is_manual': info.get('is_manual', False)})

    response = {
        'phase': room['phase'],
        'topic_name': room['topic_name'],
        'grid': room['grid'],
        'players': players_list,
        'categories': list(TOPIC_CARDS.keys()),
        'votes_count': len(room['votes']),
        'total_players': len(room['players']),
        'chameleon_name': room['players'].get(room['chameleon_id'], {}).get('name', 'Unknown') if room['chameleon_id'] else '',
        'secret_word': room['secret_word'] if room['phase'] == 'RESULTS' else None,
        'vote_results': [],
        'is_host': (player_id == room['host_id']),
        'devices': room['devices'],
        'device_count': len(room['devices']),
        'use_codes': room.get('use_codes', True)
    }

    if room['phase'] == 'RESULTS':
        counts = {pid: 0 for pid in room['players']}
        for target in room['votes'].values():
            if target in counts:
                counts[target] += 1
        for pid, cnt in counts.items():
            response['vote_results'].append({'name': room['players'][pid]['name'], 'count': cnt})

    if room['phase'] == 'ROLE_REVEAL':
        if not room['devices']:
            response['phase'] = 'WAITING_DEVICE_SETUP'
        else:
            current_dev_idx = room['device_current_idx']
            if current_dev_idx < len(room['devices']):
                current_device = room['devices'][current_dev_idx]
                current_player_pos = room['device_player_idx'].get(current_dev_idx, 0)
                if current_player_pos < len(current_device):
                    current_player_id = current_device[current_player_pos]
                    if player_id in current_device:
                        response['current_player_on_device'] = current_player_id
                        response['current_player_name'] = room['players'][current_player_id]['name']
                        response['device_index'] = current_dev_idx
                        response['player_index_in_device'] = current_player_pos
                        response['already_revealed'] = (current_player_id in room['device_revealed'].get(current_dev_idx, set()))
                    else:
                        response['waiting_for_device'] = True

    if room['phase'] in ['VOTING', 'PLAYING']:
        device_players = []
        for dev in room['devices']:
            if player_id in dev:
                for pid in dev:
                    if room['phase'] == 'VOTING' and pid in room['votes']:
                        continue
                    device_players.append({'id': pid, 'name': room['players'][pid]['name']})
                break
        response['device_players'] = device_players

    return jsonify(response)

@app.route('/online/set_devices', methods=['POST'])
def online_set_devices():
    data = request.json
    room_id = data.get('room_id')
    player_id = session.get('player_id')
    room = ROOMS.get(room_id)
    if not room or player_id != room['host_id']:
        return jsonify({'error': 'Host required'}), 403

    devices = data.get('devices')
    if not devices or not isinstance(devices, list):
        return jsonify({'error': 'Invalid devices configuration'}), 400

    all_players = set(room['players'].keys())
    assigned = set()
    for dev in devices:
        for pid in dev:
            if pid not in all_players:
                return jsonify({'error': f'Player {pid} not in room'}), 400
            if pid in assigned:
                return jsonify({'error': f'Player {pid} assigned twice'}), 400
            assigned.add(pid)
            
    if assigned != all_players:
        return jsonify({'error': 'Not all players assigned'}), 400

    room['devices'] = devices
    room['device_current_idx'] = 0
    room['device_player_idx'] = {i: 0 for i in range(len(devices))}
    room['device_revealed'] = {i: set() for i in range(len(devices))}
    return jsonify({'success': True})

@app.route('/online/start_game', methods=['POST'])
def online_start_game():
    data = request.json
    room_id = data.get('room_id')
    player_id = session.get('player_id')
    room = ROOMS.get(room_id)
    
    if not room or player_id != room['host_id']:
        return jsonify({'error': 'Host required'}), 403
    if len(room['players']) < 3:
        return jsonify({'error': 'Need at least 3 players'}), 400
        
    all_players = set(room['players'].keys())
    assigned = set()
    for dev in room['devices']:
        for pid in dev:
            assigned.add(pid)
    if assigned != all_players:
        return jsonify({'error': 'Not all players assigned to devices'}), 400

    room['votes'] = {}
    setup_new_online_round(room)
    return jsonify({'success': True})

@app.route('/online/reveal_role', methods=['POST'])
def online_reveal_role():
    data = request.json
    room_id = data.get('room_id')
    player_id = session.get('player_id')
    room = ROOMS.get(room_id)
    
    if not room or room['phase'] != 'ROLE_REVEAL':
        return jsonify({'error': 'Not in role reveal phase'}), 400

    current_dev_idx = room['device_current_idx']
    if current_dev_idx >= len(room['devices']):
        return jsonify({'error': 'Invalid device index'}), 400

    current_dev = room['devices'][current_dev_idx]
    if player_id not in current_dev:
        return jsonify({'error': 'Not your turn / device'}), 400

    current_player_pos = room['device_player_idx'].get(current_dev_idx, 0)
    if current_player_pos >= len(current_dev):
        return jsonify({'error': 'No more players on this device'}), 400
        
    current_player_id = current_dev[current_player_pos]
    
    room['device_revealed'][current_dev_idx].add(current_player_id)
    role = room['roles'][current_player_id]
    code = room['player_codes'][current_player_id]
    
    return jsonify({
        'is_chameleon': (role == 'CHAMELEON'),
        'code': code,
        'player_name': room['players'][current_player_id]['name']
    })

@app.route('/online/next_on_device', methods=['POST'])
def online_next_on_device():
    data = request.json
    room_id = data.get('room_id')
    player_id = session.get('player_id')
    room = ROOMS.get(room_id)
    
    if not room or room['phase'] != 'ROLE_REVEAL':
        return jsonify({'error': 'Not in role reveal phase'}), 400

    current_dev_idx = room['device_current_idx']
    current_dev = room['devices'][current_dev_idx]
    
    if player_id not in current_dev:
        return jsonify({'error': 'Not your turn / device'}), 400

    current_player_pos = room['device_player_idx'].get(current_dev_idx, 0)
    current_player_pos += 1
    
    if current_player_pos < len(current_dev):
        room['device_player_idx'][current_dev_idx] = current_player_pos
    else:
        next_device_idx = current_dev_idx + 1
        if next_device_idx < len(room['devices']):
            room['device_current_idx'] = next_device_idx
            room['device_player_idx'][next_device_idx] = 0
        else:
            room['phase'] = 'PLAYING'
            room['device_current_idx'] = 0
            room['device_player_idx'] = {}
            room['device_revealed'] = {}

    return jsonify({'success': True})

@app.route('/online/verify_code', methods=['POST'])
def online_verify_code():
    data = request.json
    room_id = data.get('room_id')
    room = ROOMS.get(room_id)
    
    if not room or room['phase'] != 'PLAYING':
        return jsonify({'error': 'Not in playing phase'}), 400

    use_codes = room.get('use_codes', True)
    player_id = session.get('player_id')

    if use_codes:
        code = str(data.get('code', '')).strip()
        expected_code = room['player_codes'].get(player_id)
        if not expected_code:
            return jsonify({'valid': False, 'error': 'No code assigned'}), 400

        if str(expected_code) == code:
            is_chameleon = (room['roles'][player_id] == 'CHAMELEON')
            if is_chameleon:
                return jsonify({'valid': True, 'is_chameleon': True})
            else:
                return jsonify({'valid': True, 'is_chameleon': False, 'col': room['col'], 'row': room['row']})
        else:
            return jsonify({'valid': False})
    else:
        target_pid = data.get('player_id')
        if target_pid not in room['roles']:
            return jsonify({'valid': False})
        is_chameleon = (room['roles'][target_pid] == 'CHAMELEON')
        return jsonify({'valid': True, 'is_chameleon': is_chameleon, 'col': room['col'], 'row': room['row']})

@app.route('/online/change_topic', methods=['POST'])
def online_change_topic():
    room_id = request.json.get('room_id')
    req_type = request.json.get('type')
    room = ROOMS.get(room_id)
    
    if not room or session.get('player_id') != room['host_id']:
        return jsonify({'error': 'Host required'}), 403

    if req_type == 'random':
        category = random.choice(list(TOPIC_CARDS.keys()))
    else:
        category = request.json.get('topic')
        if category not in TOPIC_CARDS:
            category = random.choice(list(TOPIC_CARDS.keys()))

    grid = TOPIC_CARDS[category]
    room['topic_name'] = category
    room['grid'] = grid
    room['secret_word'] = random.choice([word for row in grid for word in row])
    room['col'], room['row'] = get_random_coordinates()
    
    return jsonify({'success': True})

@app.route('/online/start_voting_phase', methods=['POST'])
def online_start_voting():
    room_id = request.json.get('room_id')
    room = ROOMS.get(room_id)
    if room and session.get('player_id') == room['host_id']:
        room['phase'] = 'VOTING'
        return jsonify({'success': True})
    return jsonify({'error': 'Only host can start voting'}), 403

@app.route('/online/cast_vote', methods=['POST'])
def online_cast_vote():
    data = request.json
    room_id = data.get('room_id')
    voter_id = data.get('voter_id')   
    target_id = data.get('target_id')
    room = ROOMS.get(room_id)
    
    if not room:
        return jsonify({'success': False, 'error': 'Room not found'}), 404
    
    if voter_id not in room['players']:
        return jsonify({'success': False, 'error': 'Invalid voter'}), 400
    
    if voter_id in room['votes']:
        return jsonify({'success': False, 'error': 'You already voted'}), 400
    
    if target_id not in room['players']:
        return jsonify({'success': False, 'error': 'Invalid target'}), 400
    
    room['votes'][voter_id] = target_id
    
    if len(room['votes']) >= len(room['players']):
        room['phase'] = 'RESULTS'
    
    return jsonify({'success': True})

@app.route('/online/end_voting', methods=['POST'])
def online_end_voting():
    room_id = request.json.get('room_id')
    room = ROOMS.get(room_id)
    if room and session.get('player_id') == room['host_id']:
        room['phase'] = 'RESULTS'
        return jsonify({'success': True})
    return jsonify({'error': 'Host authority required'}), 403

@app.route('/online/restart', methods=['POST'])
def online_restart():
    room_id = request.json.get('room_id')
    room = ROOMS.get(room_id)
    if room and session.get('player_id') == room['host_id']:
        room['votes'] = {}
        room['phase'] = 'LOBBY'
        room['devices'] = [[pid] for pid in room['players'].keys()]
        room['device_current_idx'] = 0
        room['device_player_idx'] = {i: 0 for i in range(len(room['devices']))}
        room['device_revealed'] = {i: set() for i in range(len(room['devices']))}
        room['roles'] = {}
        room['player_codes'] = {}
        room['chameleon_id'] = None
        return jsonify({'success': True})
    return jsonify({'error': 'Host authority required'}), 403

# ---------- HTML TEMPLATE (with Global Chat) ----------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>The Chameleon</title>
    <style>
        :root { --bg-color: #0f172a; --card-bg: #1e293b; --accent: #06b6d4; --danger: #ef4444; --warning: #f59e0b; --purple: #8b5cf6; --success: #10b981; --text: #f8fafc; --text-muted: #94a3b8; }
        * { touch-action: manipulation; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg-color); color: var(--text); text-align: center; margin: 0; padding: 16px; min-height: 100vh; display: flex; align-items: center; justify-content: center; user-select: none; }
        .card { background: var(--card-bg); border-radius: 20px; padding: 24px; width: 100%; max-width: 460px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.08); }
        h2 { margin-top: 0; font-size: 28px; }
        .btn { background: var(--accent); color: white; border: none; padding: 14px 20px; font-size: 16px; font-weight: 700; border-radius: 12px; cursor: pointer; width: 100%; margin: 8px 0; transition: all 0.2s ease; }
        .btn:active { transform: scale(0.98); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .btn-start { background: var(--success); font-size: 18px; padding: 16px; }
        .btn-topic { background: var(--purple); }
        .btn-danger { background: var(--danger); }
        .btn-option { background: #334155; border: 1px solid var(--accent); color: var(--accent); }
        .btn-option:hover, .btn-option.selected { background: var(--accent); color: white; }
        .btn-locked { background: #475569; border-color: #64748b; color: #94a3b8; cursor: not-allowed; }
        .btn-small { width: auto; padding: 6px 12px; margin: 0 4px; display: inline-block; }
        .btn-toggle { background: #1e293b; border: 2px solid var(--accent); color: var(--accent); padding: 10px; font-size:14px; margin-bottom:15px;}
        .btn-toggle.on { background: var(--accent); color: #000; }
        .player-selector { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 15px 0; }
        .player-option { background: #334155; padding: 12px; border-radius: 10px; cursor: pointer; font-weight: bold; border: 2px solid transparent; transition: all 0.2s; }
        .player-option.selected { border-color: var(--accent); background: rgba(6, 182, 212, 0.2); color: var(--accent); }
        table { width: 100%; border-collapse: separate; border-spacing: 6px; margin-top: 15px; }
        th, td { border-radius: 8px; padding: 12px 4px; text-align: center; font-size: 14px; background: #334155; }
        th { background: transparent; color: var(--accent); font-weight: 800; }
        td.row-header { background: transparent; color: var(--accent); font-weight: 800; }
        td.highlight { background: var(--accent) !important; color: #000 !important; font-weight: bold; box-shadow: 0 0 12px rgba(6, 182, 212, 0.6); }
        input, select { width: 100%; padding: 14px; font-size: 20px; border-radius: 10px; border: 1px solid #475569; background: #0f172a; color: #fff; text-align: center; margin: 8px 0; }
        select { font-size: 16px; padding: 10px; }
        .code-box { background: #fef08a; color: #854d0e; font-size: 28px; font-weight: 800; padding: 16px; border-radius: 12px; margin: 16px 0; }
        .alert-box { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: var(--text); font-weight: 600; padding: 14px; border-radius: 12px; margin: 12px 0; }
        .alert-box .chameleon-text { color: var(--warning); }
        .alert-box .clued-text { color: var(--accent); }
        .badge { display: inline-block; background: #334155; padding: 4px 12px; border-radius: 20px; font-size: 14px; color: var(--accent); margin-bottom: 12px; font-weight: bold; }
        .warning-text { color: var(--warning); font-size: 14px; margin-top: 8px; }
        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); backdrop-filter: blur(4px); z-index: 100; align-items: center; justify-content: center; }
        .modal-content { background: var(--card-bg); padding: 24px; border-radius: 20px; width: 90%; max-width: 400px; border: 1px solid rgba(255,255,255,0.1); }
        .screen { display: none; }
        .active-screen { display: block; }
        .device-box { background: #0f172a; padding: 10px; border-radius: 8px; border: 1px solid #334155; margin: 4px 0; }
        .device-box .player-tag { display: inline-block; background: #334155; padding: 2px 8px; border-radius: 4px; margin: 2px; font-size: 13px; }
        .device-assign-row { display: flex; align-items: center; justify-content: space-between; margin: 4px 0; }
        .device-assign-row select { padding: 4px; width: auto; font-size:14px; }
        .game-list-item { background: #1e293b; padding: 12px; border-radius: 8px; margin: 8px 0; display: flex; justify-content: space-between; align-items: center; }
        .game-list-item .info { text-align: left; }
        .game-list-item .join-btn { width: auto; padding: 8px 16px; margin: 0; }
        .player-entry { display: flex; align-items: center; justify-content: space-between; margin: 2px 0; }
        .player-entry .name { flex: 1; text-align: left; }
        .player-entry .remove-btn { background: var(--danger); color: white; border: none; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 12px; }
        .add-player-row { display: flex; gap: 8px; margin: 8px 0; }
        .add-player-row input { flex: 1; padding: 8px; font-size: 14px; }
        .add-player-row button { width: auto; padding: 8px 16px; margin: 0; }
        .voted-btn { background: var(--success) !important; color: white !important; border-color: var(--success) !important; }
        .vote-flash { background: var(--success); color: white; padding: 12px; border-radius: 10px; margin-bottom: 10px; font-weight: bold; display: none; }

        /* GLOBAL CHAT STYLES */
        #chat-toggle-btn {
            position: fixed; bottom: 20px; right: 20px; z-index: 1000;
            width: 60px; height: 60px; border-radius: 50%;
            background: var(--accent); color: white; border: none;
            font-size: 28px; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            display: flex; align-items: center; justify-content: center;
            transition: transform 0.2s;
        }
        #chat-toggle-btn:hover { transform: scale(1.05); }
        #chat-toggle-btn .badge {
            position: absolute; top: -5px; right: -5px;
            background: var(--danger); color: white; border-radius: 50%;
            width: 22px; height: 22px; font-size: 12px;
            display: flex; align-items: center; justify-content: center;
            font-weight: bold;
        }
        #chat-container {
            position: fixed; bottom: 90px; right: 20px; z-index: 999;
            width: 320px; max-width: 90vw; height: 400px; max-height: 60vh;
            background: var(--card-bg); border-radius: 16px;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 8px 30px rgba(0,0,0,0.6);
            display: none; flex-direction: column;
            overflow: hidden;
        }
        #chat-container.open { display: flex; }
        #chat-header {
            padding: 12px 16px; background: rgba(0,0,0,0.3);
            font-weight: bold; color: var(--accent);
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        #chat-header button {
            background: none; border: none; color: var(--text-muted);
            font-size: 20px; cursor: pointer; padding: 0 8px;
        }
        #chat-messages {
            flex: 1; overflow-y: auto; padding: 10px;
            display: flex; flex-direction: column;
            gap: 4px; min-height: 0;
        }
        .chat-msg {
            background: rgba(255,255,255,0.05); border-radius: 8px;
            padding: 6px 12px; font-size: 14px;
            word-wrap: break-word; max-width: 95%;
            align-self: flex-start;
        }
        .chat-msg .username { color: var(--accent); font-weight: 600; margin-right: 6px; }
        .chat-msg .time { color: var(--text-muted); font-size: 11px; margin-left: 6px; }
        .chat-msg .text { color: var(--text); }
        #chat-input-row {
            display: flex; padding: 8px; gap: 6px;
            border-top: 1px solid rgba(255,255,255,0.05);
            background: rgba(0,0,0,0.2);
        }
        #chat-input-row input {
            flex: 1; padding: 8px 12px; border-radius: 8px;
            border: 1px solid #334155; background: #0f172a;
            color: white; font-size: 14px;
        }
        #chat-input-row button {
            padding: 8px 16px; border-radius: 8px;
            background: var(--accent); color: white; border: none;
            cursor: pointer; font-weight: 600;
        }
        @media (max-width: 480px) {
            #chat-container { width: 90vw; right: 5vw; bottom: 80px; height: 50vh; }
            #chat-toggle-btn { width: 50px; height: 50px; font-size: 22px; bottom: 15px; right: 15px; }
        }
    </style>
</head>
<body>
<div class="card">
    <h2>🦎 The Chameleon</h2>
    <div id="room-badge" class="badge" style="display: none;">ROOM: <span id="room-code-display"></span></div>

    <!-- LANDING -->
    <div id="screen-landing" class="screen active-screen">
        <p style="color: var(--text-muted); margin-bottom: 20px;">Choose Game Mode:</p>
        <button class="btn btn-start" onclick="selectMode('LOCAL')">📱 Pass & Play (Local)</button>
        <button class="btn btn-topic" onclick="selectMode('ONLINE')">🌐 Online Multiplayer</button>
    </div>

    <!-- LOCAL START -->
    <div id="screen-local-start" class="screen">
        <p style="color: var(--text-muted); margin-bottom: 8px;">Number of Players:</p>
        <div class="player-selector" id="local-player-grid">
            <div class="player-option p-opt" onclick="selectLocalPlayers(3)">3</div>
            <div class="player-option p-opt selected" onclick="selectLocalPlayers(4)">4</div>
            <div class="player-option p-opt" onclick="selectLocalPlayers(5)">5</div>
            <div class="player-option p-opt" onclick="selectLocalPlayers(6)">6</div>
            <div class="player-option p-opt" onclick="selectLocalPlayers(7)">7</div>
            <div class="player-option p-opt" onclick="selectLocalPlayers(9)">9</div>
        </div>
        
        <button id="btn-local-toggle-codes" class="btn btn-toggle on" onclick="toggleLocalCodes()">🔒 Secret Codes: ON</button>
        <p style="color:var(--text-muted); font-size:12px; margin-top:-5px; margin-bottom:15px;">If OFF, bypasses entering codes entirely.</p>
        
        <button class="btn btn-start" onclick="startLocalGame()">🎮 Start Game</button>
        <button class="btn" style="background:#334155; margin-top:10px;" onclick="goToLanding()">⬅ Back</button>
    </div>

    <div id="screen-local-roles" class="screen">
        <h3 id="local-player-turn-header" style="color: var(--accent); font-size: 22px;">Player 1's Turn</h3>
        <p style="color: var(--text-muted); font-size:14px;">Pass the phone!</p>
        <button id="local-reveal-role-btn" class="btn" onclick="revealLocalRole()">👁️ Show Secret Role</button>
        <div id="local-role-details" style="display: none;">
            <div id="local-role-alert-box" class="alert-box"><span id="local-role-message">Tap to reveal</span></div>
            <div class="code-box">SECRET CODE:<br><span id="local-assigned-code">-</span></div>
            <button id="local-next-player-btn" class="btn btn-start" onclick="nextLocalPlayer()">✅ Done - Pass Phone</button>
        </div>
    </div>

    <div id="screen-local-grid" class="screen">
        <h3 id="local-topic-title" style="color: var(--warning);"></h3>
        <button class="btn btn-topic" onclick="openTopicModal('local')">🔀 Change Topic</button>
        <div style="margin-top:15px;">
            <div id="local-code-input-area">
                <input type="text" id="local-player-code-input" placeholder="Enter Secret Code" pattern="[0-9]*" inputmode="numeric" maxlength="1" />
            </div>
            <div id="local-no-code-area" style="display:none;">
                <p style="color:var(--text-muted); font-size:14px; margin-bottom:4px;">Who is viewing?</p>
                <select id="local-viewer-select"></select>
            </div>
            <button class="btn" onclick="verifyLocalCode()">🔓 Reveal Target</button>
        </div>
        <div id="local-decrypted-info" style="display:none; background:#0f172a; padding:14px; border-radius:12px; margin:15px 0; border:1px solid #334155;">
            <div id="local-coord-val" style="display:none; color:var(--accent); font-weight:bold; font-size:18px;"></div>
            <div id="local-chameleon-text-output" style="display:none; color:var(--accent); font-size:18px; font-weight:bold;">🦎 You are the Chameleon</div>
            <button id="local-toggle-target-btn" class="btn btn-option" onclick="toggleLocalTarget()">👁️ Hide Target</button>
            <div id="local-target-lock-warning" class="warning-text" style="display:none;">🔒 Locked – re‑enter code to reveal</div>
        </div>
        <table id="local-topic-table"><thead><tr><th></th><th>A</th><th>B</th><th>C</th><th>D</th></tr></thead><tbody id="local-table-body"></tbody></table>
        <hr>
        <button class="btn btn-danger" onclick="restartLocalGame()">🔄 Restart</button>
    </div>

    <!-- ONLINE -->
    <div id="screen-online-menu" class="screen">
        <input type="text" id="online-player-name" placeholder="Your Name" maxlength="12" />
        <button class="btn btn-start" onclick="createGame()">🚀 Create New Game</button>
        <div style="margin:15px 0; color:var(--text-muted);">— or join an existing game —</div>
        <div id="game-list-container">
            <p style="color:var(--text-muted);">Loading games...</p>
        </div>
        <button class="btn" style="background:#334155; margin-top:20px;" onclick="goToLanding()">⬅ Back</button>
    </div>

    <div id="screen-online-lobby" class="screen">
        <h3>Lobby</h3>
        <div id="online-player-list" style="margin:15px 0; background:#0f172a; padding:12px; border-radius:10px;"></div>
        <div id="host-device-setup" style="display:none;">
            <button id="btn-online-toggle-codes" class="btn btn-toggle on" onclick="toggleOnlineCodes()">🔒 Secret Codes: ON</button>
            <p style="color:var(--text-muted);">Add manual players, then assign each player to a device.</p>
            <div id="manual-player-area"></div>
            <div id="device-assignment-area"></div>
            <button class="btn btn-start" onclick="saveDeviceAssignments()">💾 Save Device Setup</button>
            <button class="btn btn-start" onclick="startOnlineGame()">🚀 Start Game</button>
        </div>
        <p id="guest-waiting-msg" style="color:var(--text-muted); display:none;">Waiting for host to configure devices...</p>
    </div>

    <div id="screen-online-role" class="screen">
        <h3 id="online-role-header">Your Secret Role</h3>
        <p id="online-device-info" style="color:var(--text-muted);">Pass device to the active player</p>
        <button id="online-show-role-btn" class="btn" onclick="revealOnlineRole()">👁️ Tap to Reveal</button>
        <div id="online-role-card" style="display:none;">
            <div id="online-role-alert" class="alert-box"><span id="online-role-message">Role</span></div>
            <div id="online-code-box" class="code-box">SECRET CODE:<br><span id="online-assigned-code">-</span></div>
            <button id="online-next-device-btn" class="btn btn-start" onclick="nextOnlinePlayer()">✅ Done - Pass to Next</button>
        </div>
        <p id="online-role-wait" style="color:var(--text-muted); display:none;">Waiting for your turn on this device...</p>
    </div>

    <div id="screen-online-board" class="screen">
        <h3 id="online-topic-title" style="color:var(--warning);"></h3>
        
        <div id="host-topic-control" style="display:none;">
            <button class="btn btn-topic" onclick="openTopicModal('online')">🔀 Change Topic</button>
        </div>
        
        <div style="margin-top:15px;" id="online-code-entry-section">
            <div id="online-code-input-area">
                <input type="text" id="online-player-code-input" placeholder="Enter Secret Code" pattern="[0-9]*" inputmode="numeric" maxlength="1" />
            </div>
            <div id="online-no-code-area" style="display:none;">
                <p style="color:var(--text-muted); font-size:14px; margin-bottom:4px;">Who is viewing?</p>
                <select id="online-viewer-select"></select>
            </div>
            <button class="btn" onclick="verifyOnlineCode()">🔓 Reveal Target</button>
        </div>
        
        <div id="online-decrypted-info" style="display:none; background:#0f172a; padding:12px; border-radius:10px; margin:12px 0;">
            <div id="online-coord-val" style="display:none; color:var(--accent); font-weight:bold; font-size:18px;"></div>
            <div id="online-chameleon-val" style="display:none; color:var(--accent); font-size:18px; font-weight:bold;">🦎 You are the Chameleon<br><small style="font-weight:normal;color:var(--text-muted);">Try to blend in!</small></div>
            <button id="online-toggle-target-btn" class="btn btn-option" onclick="toggleOnlineTarget()">👁️ Hide Target</button>
            <div id="online-target-lock-warning" class="warning-text" style="display:none;">🔒 Locked – re‑enter code to reveal</div>
        </div>
        
        <table id="online-topic-table"><tbody id="online-table-body"></tbody></table>
        <div id="host-voting-control" style="display:none; margin-top:15px;">
            <button class="btn btn-topic" onclick="goToOnlineVoting()">🗳️ Proceed to Voting</button>
        </div>
        <p id="guest-voting-msg" style="color:var(--text-muted); display:none;">Discuss clues! Waiting for host...</p>
    </div>

    <!-- VOTING SCREEN -->
    <div id="screen-online-voting" class="screen">
        <h3>Who is the Chameleon?</h3>
        <div id="shared-voting-flash" class="vote-flash">✅ Vote Cast! Pass to next player.</div>
        <div id="voter-selector" style="margin: 10px 0; display: none;">
            <label style="color: var(--text-muted);">Who is voting? </label>
            <select id="voter-dropdown"></select>
        </div>
        <div id="vote-options"></div>
        <p id="vote-status-msg" style="color:var(--text-muted); margin-top:15px;"></p>
        <div id="host-voting-control-end" style="display:none; margin-top:15px;">
            <button class="btn btn-danger" onclick="endOnlineVoting()">🛑 End Voting & Show Results</button>
        </div>
    </div>

    <div id="screen-online-results" class="screen">
        <h3>Round Results</h3>
        <div style="background:#0f172a; border-radius:12px; padding:16px; margin:12px 0; border:1px solid var(--accent);">
            <div id="chameleon-identity" style="font-size:20px; font-weight:bold; color:var(--danger);"></div>
            <div id="target-word-identity" style="margin-top:8px; color:var(--accent);"></div>
        </div>
        <h4>Vote Breakdown:</h4>
        <div id="vote-breakdown" style="background:#0f172a; padding:12px; border-radius:10px; margin-bottom:15px;"></div>
        <div id="host-results-controls" style="display:none;">
            <button class="btn btn-start" onclick="startOnlineGame()">🔄 Next Round</button>
            <button class="btn btn-danger" onclick="restartOnlineGame()">🏠 Return to Lobby</button>
        </div>
        <p id="guest-results-msg" style="color:var(--text-muted); display:none;">Waiting for host...</p>
    </div>

    <!-- SHARED TOPIC MODAL -->
    <div id="shared-topic-modal" class="modal">
        <div class="modal-content">
            <h3>Change Topic</h3>
            <button class="btn" style="background:var(--accent);" onclick="changeTopic('random')">🎲 Random</button>
            <p style="color:var(--text-muted); margin:12px 0;">or select:</p>
            <select id="shared-topic-select">
                {% for topic in topics %}
                <option value="{{ topic }}">{{ topic }}</option>
                {% endfor %}
            </select>
            <button class="btn" style="background:#10b981; margin-top:12px;" onclick="changeTopic('manual')">Select</button>
            <button class="btn" style="background:#475569;" onclick="closeTopicModal()">Cancel</button>
        </div>
    </div>
</div>

<!-- GLOBAL CHAT TOGGLE BUTTON -->
<button id="chat-toggle-btn" onclick="toggleChat()">
    💬
    <span id="chat-badge" class="badge" style="display:none;">0</span>
</button>

<!-- GLOBAL CHAT CONTAINER -->
<div id="chat-container">
    <div id="chat-header">
        <span>💬 Global Chat</span>
        <button onclick="toggleChat()">✕</button>
    </div>
    <div id="chat-messages"></div>
    <div id="chat-input-row">
        <input type="text" id="chat-input" placeholder="Type a message..." maxlength="200">
        <button onclick="sendChatMessage()">Send</button>
    </div>
</div>

<script>
// ========== GLOBAL CHAT ==========
let chatVisible = false;
let chatUnread = 0;
let chatUsername = '';

function toggleChat() {
    chatVisible = !chatVisible;
    document.getElementById('chat-container').classList.toggle('open', chatVisible);
    if (chatVisible) {
        document.getElementById('chat-badge').style.display = 'none';
        chatUnread = 0;
        document.getElementById('chat-input').focus();
        loadChatMessages();
    }
}

function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;
    if (!chatUsername) {
        chatUsername = prompt("Enter your username for chat:", "Player");
        if (!chatUsername) chatUsername = "Anonymous";
    }
    fetch('/global_chat/send', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({username: chatUsername, text: text})
    }).then(() => {
        input.value = '';
        loadChatMessages();
    });
}

function loadChatMessages() {
    fetch('/global_chat/get_messages')
        .then(r => r.json())
        .then(messages => {
            const container = document.getElementById('chat-messages');
            container.innerHTML = messages.map(m => 
                `<div class="chat-msg">
                    <span class="username">${m.username}</span>
                    <span class="text">${m.text}</span>
                    <span class="time">${m.time}</span>
                </div>`
            ).join('');
            container.scrollTop = container.scrollHeight;
            // Update badge if chat is closed
            if (!chatVisible && messages.length > 0) {
                const badge = document.getElementById('chat-badge');
                badge.style.display = 'inline-block';
                badge.textContent = messages.length;
            }
        });
}

// Poll for new messages every 3 seconds
setInterval(loadChatMessages, 3000);

// Enter key to send
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('chat-input').addEventListener('keydown', function(e) {
        if (e.key === 'Enter') sendChatMessage();
    });
});

// ========== GAME ==========
let gameMode = null, pollInterval = null;
let currentRoom = null, isHost = false, myPlayerId = null;

// Local
let localPlayerCount = 4;
let localUseCodes = true;
let localActiveHighlight = null, localIsChameleonUser = false;
let localTargetHidden = false, localTargetLocked = false;
let modalTargetMode = 'local';

// Online
let currentGridData = [];
let onlineTargetLocked = false;
let onlineTargetHidden = false;
let onlineActiveHighlight = null;
let onlineIsChameleonUser = false;
let onlineDeviceAssignments = [];
let lastOnlineRevealState = null;
let onlineUseCodes = true;
let unvotedDevicePlayers = [];
let lastTopic = '';

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active-screen'));
    document.getElementById(id).classList.add('active-screen');
}

function goToLanding() {
    if (pollInterval) clearInterval(pollInterval);
    gameMode = null;
    showScreen('screen-landing');
    document.getElementById('room-badge').style.display = 'none';
}

function selectMode(mode) {
    gameMode = mode;
    if (mode === 'LOCAL') {
        showScreen('screen-local-start');
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(checkLocalState, 1000);
    } else {
        showScreen('screen-online-menu');
        refreshGameList();
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(refreshGameList, 3000);
    }
}

// ========== LOCAL ==========
function selectLocalPlayers(n) {
    localPlayerCount = n;
    document.querySelectorAll('.p-opt').forEach(el => el.classList.toggle('selected', parseInt(el.innerText) === n));
}

function toggleLocalCodes() {
    localUseCodes = !localUseCodes;
    const btn = document.getElementById('btn-local-toggle-codes');
    if (localUseCodes) {
        btn.innerText = "🔒 Secret Codes: ON";
        btn.classList.add('on');
    } else {
        btn.innerText = "🔓 Secret Codes: OFF";
        btn.classList.remove('on');
    }
}

function startLocalGame() {
    resetLocalUI();
    fetch('/local/start_game', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ players_count: localPlayerCount, use_codes: localUseCodes })
    }).then(() => {
        document.getElementById('local-reveal-role-btn').style.display = 'block';
        document.getElementById('local-role-details').style.display = 'none';
        checkLocalState();
    });
}

function revealLocalRole() {
    fetch('/local/get_role', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            document.getElementById('local-reveal-role-btn').style.display = 'none';
            document.getElementById('local-role-details').style.display = 'block';
            document.getElementById('local-assigned-code').innerText = data.code;
            const alertBox = document.getElementById('local-role-alert-box');
            if (data.is_chameleon) {
                alertBox.innerHTML = '⚠️ <span class="chameleon-text">YOU ARE THE CHAMELEON</span><br><small style="font-weight:normal;color:var(--text-muted);">Blend in and fake checking the code.</small>';
            } else {
                alertBox.innerHTML = '✅ <span class="clued-text">YOU ARE CLUED-IN</span><br><small style="font-weight:normal;color:var(--text-muted);">Remember your code to decrypt the target word.</small>';
            }
        });
}

function nextLocalPlayer() {
    const btn = document.getElementById('local-next-player-btn');
    btn.disabled = true;
    fetch('/local/next_player', { method: 'POST' }).then(() => {
        setTimeout(() => {
            btn.disabled = false;
            resetLocalUI();
            document.getElementById('local-role-details').style.display = 'none';
            document.getElementById('local-reveal-role-btn').style.display = 'block';
            checkLocalState();
        }, 300);
    });
}

function checkLocalState() {
    if (gameMode !== 'LOCAL') return;
    fetch('/local/state', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            localUseCodes = data.use_codes;
            if (data.phase === 'START_SCREEN') showScreen('screen-local-start');
            else if (data.phase === 'ROLES') {
                showScreen('screen-local-roles');
                document.getElementById('local-player-turn-header').innerText = `Player ${data.current_player_idx + 1}'s Turn`;
            } else if (data.phase === 'PUBLIC_GRID') {
                if (!document.getElementById('screen-local-grid').classList.contains('active-screen')) {
                    showScreen('screen-local-grid');
                    setupLocalCodeArea(data.players_count);
                }
                document.getElementById('local-topic-title').innerText = "Topic: " + data.topic_name;
                buildLocalGrid(data.grid, localTargetHidden ? null : localActiveHighlight);
            }
        });
}

function setupLocalCodeArea(playerCount) {
    if (localUseCodes) {
        document.getElementById('local-code-input-area').style.display = 'block';
        document.getElementById('local-no-code-area').style.display = 'none';
    } else {
        document.getElementById('local-code-input-area').style.display = 'none';
        document.getElementById('local-no-code-area').style.display = 'block';
        let sel = document.getElementById('local-viewer-select');
        sel.innerHTML = '';
        for (let i = 0; i < playerCount; i++) {
            sel.innerHTML += `<option value="${i}">Player ${i+1}</option>`;
        }
    }
}

function buildLocalGrid(grid, highlight) {
    const tbody = document.getElementById('local-table-body');
    tbody.innerHTML = "";
    const cols = ['A','B','C','D'];
    grid.forEach((row, rIdx) => {
        let tr = document.createElement('tr');
        let th = document.createElement('td');
        th.className = 'row-header';
        th.innerText = rIdx+1;
        tr.appendChild(th);
        row.forEach((cell, cIdx) => {
            let td = document.createElement('td');
            td.innerText = cell;
            if (highlight && cols[cIdx] === highlight.col && (rIdx+1) === highlight.row) {
                td.classList.add('highlight');
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

function verifyLocalCode() {
    let payload = {};
    if (localUseCodes) {
        payload.code = document.getElementById('local-player-code-input').value;
    } else {
        payload.player_idx = document.getElementById('local-viewer-select').value;
    }
    
    fetch('/local/verify_code', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    }).then(r => r.json()).then(data => {
        if (!data.valid) {
            alert(localUseCodes ? "Invalid Code!" : "Error fetching role");
            return;
        }
        localTargetLocked = false;
        localTargetHidden = false;
        document.getElementById('local-decrypted-info').style.display = 'block';
        localIsChameleonUser = data.is_chameleon;
        
        const btn = document.getElementById('local-toggle-target-btn');
        btn.innerText = "👁️ Hide Target";
        btn.className = "btn btn-option";
        btn.disabled = false;
        document.getElementById('local-target-lock-warning').style.display = 'none';
        
        if (data.is_chameleon) {
            document.getElementById('local-coord-val').style.display = 'none';
            document.getElementById('local-chameleon-text-output').style.display = 'block';
            localActiveHighlight = null;
        } else {
            document.getElementById('local-chameleon-text-output').style.display = 'none';
            document.getElementById('local-coord-val').style.display = 'block';
            document.getElementById('local-coord-val').innerText = `Target: ${data.col}${data.row}`;
            localActiveHighlight = {col: data.col, row: data.row};
        }
        checkLocalState();
    });
}

function toggleLocalTarget() {
    if (localTargetLocked) return;
    
    localTargetHidden = !localTargetHidden;
    const btn = document.getElementById('local-toggle-target-btn');
    const coord = document.getElementById('local-coord-val');
    const cham = document.getElementById('local-chameleon-text-output');
    const warn = document.getElementById('local-target-lock-warning');
    
    if (localTargetHidden) {
        localTargetLocked = true;
        btn.innerText = "🔒 Show Target (locked)";
        btn.className = "btn btn-locked";
        btn.disabled = true;
        coord.style.display = 'none';
        cham.style.display = 'none';
        warn.style.display = 'block';
    } else {
        btn.innerText = "👁️ Hide Target";
        btn.className = "btn btn-option";
        btn.disabled = false;
        warn.style.display = 'none';
        if (localIsChameleonUser) cham.style.display = 'block';
        else coord.style.display = 'block';
    }
    checkLocalState();
}

function resetLocalUI() {
    document.getElementById('local-player-code-input').value = "";
    document.getElementById('local-decrypted-info').style.display = 'none';
    document.getElementById('local-target-lock-warning').style.display = 'none';
    localActiveHighlight = null;
    localTargetHidden = false;
    localTargetLocked = false;
    localIsChameleonUser = false;
    const btn = document.getElementById('local-toggle-target-btn');
    btn.innerText = "👁️ Hide Target";
    btn.className = "btn btn-option";
    btn.disabled = false;
}

function restartLocalGame() {
    fetch('/local/restart', { method: 'POST' }).then(() => checkLocalState());
}

// ========== ONLINE ==========
function refreshGameList() {
    if (gameMode !== 'ONLINE') return;
    if (currentRoom) {
        pollOnlineRoom();
        return;
    }
    fetch('/online/list_games')
        .then(r => r.json())
        .then(games => {
            const container = document.getElementById('game-list-container');
            if (games.length === 0) {
                container.innerHTML = '<p style="color:var(--text-muted);">No active games.</p>';
                return;
            }
            container.innerHTML = games.map(g => `
                <div class="game-list-item">
                    <div class="info">
                        <strong>${g.host_name}'s Game</strong><br>
                        <small style="color:var(--text-muted);">${g.player_count} Players • ${g.phase}</small>
                    </div>
                    <button class="btn btn-small btn-start join-btn" onclick="joinGame('${g.id}')">Join</button>
                </div>
            `).join('');
        });
}

function createGame() {
    const name = document.getElementById('online-player-name').value || 'Host';
    fetch('/online/create_game', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name})
    }).then(r => r.json()).then(data => {
        currentRoom = data.room_id;
        isHost = true;
        document.getElementById('room-badge').style.display = 'inline-block';
        document.getElementById('room-code-display').innerText = currentRoom;
        pollOnlineRoom();
    });
}

function joinGame(room_id) {
    const name = document.getElementById('online-player-name').value || 'Player';
    fetch('/online/join_game', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: room_id, name: name})
    }).then(r => r.json()).then(data => {
        if (!data.success) { alert(data.error); return; }
        currentRoom = data.room_id;
        isHost = data.is_host;
        document.getElementById('room-badge').style.display = 'inline-block';
        document.getElementById('room-code-display').innerText = currentRoom;
        pollOnlineRoom();
    });
}

function toggleOnlineCodes() {
    onlineUseCodes = !onlineUseCodes;
    fetch('/online/toggle_codes', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom, use_codes: onlineUseCodes})
    }).then(() => pollOnlineRoom());
}

function pollOnlineRoom() {
    if (!currentRoom) return;
    fetch(`/online/room_state?room=${currentRoom}`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                currentRoom = null;
                showScreen('screen-online-menu');
                return;
            }
            isHost = data.is_host;
            myPlayerId = data.my_player_id;
            onlineUseCodes = data.use_codes;
            currentGridData = data.grid || [];
            
            if (data.topic_name && data.topic_name !== lastTopic) {
                resetOnlineUI();
                onlineActiveHighlight = null;
                onlineIsChameleonUser = false;
                document.getElementById('online-decrypted-info').style.display = 'none';
                const btn = document.getElementById('online-toggle-target-btn');
                btn.innerText = "👁️ Hide Target";
                btn.className = "btn btn-option";
                btn.disabled = false;
                lastTopic = data.topic_name;
            }
            
            const btnCode = document.getElementById('btn-online-toggle-codes');
            if (onlineUseCodes) {
                btnCode.innerText = "🔒 Secret Codes: ON";
                btnCode.classList.add('on');
            } else {
                btnCode.innerText = "🔓 Secret Codes: OFF";
                btnCode.classList.remove('on');
            }

            unvotedDevicePlayers = data.device_players || [];

            if (data.phase === 'LOBBY') renderLobby(data);
            else if (data.phase === 'WAITING_DEVICE_SETUP') renderLobby(data); 
            else if (data.phase === 'ROLE_REVEAL') renderRoleReveal(data);
            else if (data.phase === 'PLAYING') renderPlaying(data);
            else if (data.phase === 'VOTING') renderVoting(data);
            else if (data.phase === 'RESULTS') renderResults(data);
        });
}

// ========== ONLINE LOBBY ==========
function renderLobby(data) {
    showScreen('screen-online-lobby');
    
    const list = document.getElementById('online-player-list');
    const newListHtml = data.players.map(p => `
        <div class="player-entry">
            <span class="name">${p.name} ${p.is_host ? '👑' : ''} ${p.is_manual ? '👤' : ''}</span>
            ${isHost && !p.is_host ? `<button class="remove-btn" onclick="removePlayer('${p.id}')">✕</button>` : ''}
        </div>
    `).join('');
    if (list.innerHTML !== newListHtml) {
        list.innerHTML = newListHtml;
    }

    if (isHost) {
        document.getElementById('host-device-setup').style.display = 'block';
        document.getElementById('guest-waiting-msg').style.display = 'none';
        
        const manualArea = document.getElementById('manual-player-area');
        if (!manualArea.dataset.initialized) {
            manualArea.innerHTML = `
                <div class="add-player-row">
                    <input type="text" id="manual-name" placeholder="Manual Player Name" maxlength="12">
                    <button class="btn btn-option" onclick="addManualPlayer()">➕ Add</button>
                </div>
            `;
            manualArea.dataset.initialized = 'true';
        }

        const currentDevices = data.devices || [];
        if (currentDevices.length === 0) currentDevices.push([]);
        
        const sig = JSON.stringify(currentDevices) + JSON.stringify(data.players.map(p => p.id));
        const deviceArea = document.getElementById('device-assignment-area');
        if (deviceArea.dataset.sig !== sig) {
            deviceArea.dataset.sig = sig;
            const playerDeviceMap = {};
            currentDevices.forEach((dev, idx) => {
                dev.forEach(pid => { playerDeviceMap[pid] = idx; });
            });

            let html = '<div style="margin:15px 0;"><strong style="color:var(--text-muted);">Devices:</strong></div>';
            html += '<div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:center; margin-bottom:15px;">';
            for (let i = 0; i < currentDevices.length; i++) {
                html += `<span class="btn btn-small btn-option" style="width:auto; padding:4px 12px; background: ${i === 0 ? 'var(--accent)' : '#334155'}; color: ${i === 0 ? '#000' : 'var(--text)'};">Device ${i+1}</span>`;
            }
            html += `<button class="btn btn-small btn-option" onclick="addDevice()" style="width:auto; padding:4px 12px;">➕ Add Device</button>`;
            html += `<button class="btn btn-small btn-danger" onclick="removeDevice()" style="width:auto; padding:4px 12px;">✕ Remove Last</button>`;
            html += '</div>';

            html += '<div style="margin:10px 0;"><strong style="color:var(--text-muted);">Assign each player to a device:</strong></div>';
            data.players.forEach(p => {
                const currentDevIdx = (playerDeviceMap[p.id] !== undefined) ? playerDeviceMap[p.id] : 0;
                const options = currentDevices.map((_, idx) => 
                    `<option value="${idx}" ${idx === currentDevIdx ? 'selected' : ''}>Device ${idx+1}</option>`
                ).join('');
                html += `<div class="device-assign-row">
                    <span>${p.name}</span>
                    <select id="dev-select-${p.id}" onchange="onDeviceSelect('${p.id}')">
                        ${options}
                    </select>
                </div>`;
            });

            deviceArea.innerHTML = html;
            onlineDeviceAssignments = currentDevices.map(dev => [...dev]);
        }

    } else {
        document.getElementById('host-device-setup').style.display = 'none';
        document.getElementById('guest-waiting-msg').style.display = 'block';
    }
}

// ---------- DEVICE MANAGEMENT ----------
function addDevice() {
    onlineDeviceAssignments.push([]);
    saveDeviceAssignments();
}

function removeDevice() {
    if (onlineDeviceAssignments.length <= 1) {
        alert("Cannot remove the last device.");
        return;
    }
    const last = onlineDeviceAssignments.pop();
    if (last.length > 0) {
        onlineDeviceAssignments[onlineDeviceAssignments.length - 1].push(...last);
    }
    saveDeviceAssignments();
}

function onDeviceSelect(pid) {
    const sel = document.getElementById(`dev-select-${pid}`);
    const newDevIdx = parseInt(sel.value);
    for (let dev of onlineDeviceAssignments) {
        const idx = dev.indexOf(pid);
        if (idx !== -1) dev.splice(idx, 1);
    }
    onlineDeviceAssignments = onlineDeviceAssignments.filter(dev => dev.length > 0);
    if (newDevIdx >= onlineDeviceAssignments.length) {
        while (onlineDeviceAssignments.length <= newDevIdx) {
            onlineDeviceAssignments.push([]);
        }
    }
    onlineDeviceAssignments[newDevIdx].push(pid);
    onlineDeviceAssignments = onlineDeviceAssignments.filter(dev => dev.length > 0);
    saveDeviceAssignments();
}

function saveDeviceAssignments() {
    if (onlineDeviceAssignments.length === 0) {
        alert("At least one device required.");
        return;
    }
    fetch('/online/set_devices', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom, devices: onlineDeviceAssignments})
    }).then(r => r.json()).then(data => {
        if (!data.success) alert(data.error || "Failed to save devices");
        else pollOnlineRoom();
    });
}

function addManualPlayer() {
    const name = document.getElementById('manual-name').value.trim();
    if (!name) return;
    fetch('/online/add_manual_player', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom, name: name})
    }).then(() => pollOnlineRoom());
}

function removePlayer(pid) {
    if (!confirm("Remove this player?")) return;
    fetch('/online/remove_player', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom, player_id: pid})
    }).then(() => pollOnlineRoom());
}

function startOnlineGame() {
    resetOnlineUI();
    fetch('/online/start_game', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom})
    }).then(() => pollOnlineRoom());
}

// ----- ROLE REVEAL -----
function renderRoleReveal(data) {
    showScreen('screen-online-role');
    
    const stateStr = `${data.device_index}-${data.player_index_in_device}-${data.already_revealed}`;
    if (stateStr !== lastOnlineRevealState) {
        document.getElementById('online-role-card').style.display = 'none';
        document.getElementById('online-show-role-btn').style.display = 'block';
        lastOnlineRevealState = stateStr;
    }
    
    if (data.waiting_for_device) {
        document.getElementById('online-role-header').innerText = "Wait...";
        document.getElementById('online-show-role-btn').style.display = 'none';
        document.getElementById('online-role-wait').style.display = 'block';
        document.getElementById('online-device-info').style.display = 'none';
    } else {
        document.getElementById('online-role-header').innerText = `${data.current_player_name}'s Turn`;
        document.getElementById('online-device-info').style.display = 'block';
        document.getElementById('online-role-wait').style.display = 'none';
        
        if (!data.already_revealed) {
            document.getElementById('online-show-role-btn').style.display = 'block';
            document.getElementById('online-role-card').style.display = 'none';
        }
    }
}

function revealOnlineRole() {
    fetch('/online/reveal_role', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom})
    }).then(r => r.json()).then(data => {
        if (data.error) { alert(data.error); return; }
        document.getElementById('online-show-role-btn').style.display = 'none';
        document.getElementById('online-role-card').style.display = 'block';
        document.getElementById('online-assigned-code').innerText = data.code;
        
        const alertBox = document.getElementById('online-role-alert');
        if (data.is_chameleon) {
            alertBox.innerHTML = '⚠️ <span class="chameleon-text">YOU ARE THE CHAMELEON</span><br><small style="font-weight:normal;color:var(--text-muted);">Blend in.</small>';
        } else {
            alertBox.innerHTML = '✅ <span class="clued-text">YOU ARE CLUED-IN</span><br><small style="font-weight:normal;color:var(--text-muted);">Memorize your code.</small>';
        }
    });
}

function nextOnlinePlayer() {
    fetch('/online/next_on_device', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom})
    }).then(() => pollOnlineRoom());
}

// ----- PLAYING -----
function renderPlaying(data) {
    if (!document.getElementById('screen-online-board').classList.contains('active-screen')) {
        showScreen('screen-online-board');
        setupOnlineCodeArea();
    }
    
    document.getElementById('online-topic-title').innerText = "Topic: " + data.topic_name;
    
    if (isHost) {
        document.getElementById('host-voting-control').style.display = 'block';
        document.getElementById('host-topic-control').style.display = 'block';
        document.getElementById('guest-voting-msg').style.display = 'none';
    } else {
        document.getElementById('host-voting-control').style.display = 'none';
        document.getElementById('host-topic-control').style.display = 'none';
        document.getElementById('guest-voting-msg').style.display = 'block';
    }
    
    buildOnlineGrid(data.grid, onlineTargetHidden ? null : onlineActiveHighlight);
}

function setupOnlineCodeArea() {
    if (onlineUseCodes) {
        document.getElementById('online-code-input-area').style.display = 'block';
        document.getElementById('online-no-code-area').style.display = 'none';
    } else {
        document.getElementById('online-code-input-area').style.display = 'none';
        document.getElementById('online-no-code-area').style.display = 'block';
        
        let sel = document.getElementById('online-viewer-select');
        sel.innerHTML = '';
        if (unvotedDevicePlayers && unvotedDevicePlayers.length > 0) {
            unvotedDevicePlayers.forEach(p => {
                sel.innerHTML += `<option value="${p.id}">${p.name}</option>`;
            });
        }
    }
}

function verifyOnlineCode() {
    let payload = {room_id: currentRoom};
    if (onlineUseCodes) {
        payload.code = document.getElementById('online-player-code-input').value;
    } else {
        payload.player_id = document.getElementById('online-viewer-select').value;
    }
    
    fetch('/online/verify_code', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    }).then(r => r.json()).then(data => {
        if (!data.valid) {
            alert(onlineUseCodes ? "Invalid Code!" : "Error retrieving role.");
            return;
        }
        onlineTargetLocked = false;
        onlineTargetHidden = false;
        document.getElementById('online-decrypted-info').style.display = 'block';
        onlineIsChameleonUser = data.is_chameleon;
        
        const btn = document.getElementById('online-toggle-target-btn');
        btn.innerText = "👁️ Hide Target";
        btn.className = "btn btn-option";
        btn.disabled = false;
        document.getElementById('online-target-lock-warning').style.display = 'none';
        
        if (data.is_chameleon) {
            document.getElementById('online-coord-val').style.display = 'none';
            document.getElementById('online-chameleon-val').style.display = 'block';
            onlineActiveHighlight = null;
        } else {
            document.getElementById('online-chameleon-val').style.display = 'none';
            document.getElementById('online-coord-val').style.display = 'block';
            document.getElementById('online-coord-val').innerText = `Target: ${data.col}${data.row}`;
            onlineActiveHighlight = {col: data.col, row: data.row};
        }
        onlineTargetHidden = false;
        buildOnlineGrid(currentGridData, onlineActiveHighlight);
    });
}

function toggleOnlineTarget() {
    if (onlineTargetLocked) return;
    
    onlineTargetHidden = !onlineTargetHidden;
    const btn = document.getElementById('online-toggle-target-btn');
    const coord = document.getElementById('online-coord-val');
    const cham = document.getElementById('online-chameleon-val');
    const warn = document.getElementById('online-target-lock-warning');
    
    if (onlineTargetHidden) {
        onlineTargetLocked = true;
        btn.innerText = "🔒 Show Target (locked)";
        btn.className = "btn btn-locked";
        btn.disabled = true;
        coord.style.display = 'none';
        cham.style.display = 'none';
        warn.style.display = 'block';
    } else {
        btn.innerText = "👁️ Hide Target";
        btn.className = "btn btn-option";
        btn.disabled = false;
        warn.style.display = 'none';
        if (onlineIsChameleonUser) cham.style.display = 'block';
        else coord.style.display = 'block';
    }
    buildOnlineGrid(currentGridData, onlineTargetHidden ? null : onlineActiveHighlight);
}

function buildOnlineGrid(grid, highlight) {
    const tbody = document.getElementById('online-table-body');
    tbody.innerHTML = `<tr><th></th><th>A</th><th>B</th><th>C</th><th>D</th></tr>`;
    const cols = ['A','B','C','D'];
    grid.forEach((row, rIdx) => {
        let tr = document.createElement('tr');
        let th = document.createElement('td');
        th.className = 'row-header'; th.innerText = rIdx+1;
        tr.appendChild(th);
        row.forEach((cell, cIdx) => {
            let td = document.createElement('td');
            td.innerText = cell;
            if (highlight && cols[cIdx] === highlight.col && (rIdx+1) === highlight.row) {
                td.classList.add('highlight');
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
}

function goToOnlineVoting() {
    fetch('/online/start_voting_phase', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom})
    });
}

// ----- VOTING -----
function renderVoting(data) {
    showScreen('screen-online-voting');
    
    const voterSelector = document.getElementById('voter-selector');
    const voterDropdown = document.getElementById('voter-dropdown');
    const flash = document.getElementById('shared-voting-flash');
    
    const myDevice = data.devices.find(dev => dev.includes(myPlayerId));
    const isShared = myDevice && myDevice.length > 1;
    const unvoted = unvotedDevicePlayers || [];
    
    if (unvoted.length === 0) {
        voterSelector.style.display = 'none';
        document.getElementById('vote-options').innerHTML = `
            <div style="background:#0f172a; border-radius:10px; padding:16px;">
                <p style="color:var(--success); font-weight:bold; font-size:18px;">✅ All votes on this device cast!</p>
                <p style="color:var(--text-muted); font-size:14px;">Pass the device if needed, or wait for others.</p>
            </div>
        `;
    } else {
        if (isShared && unvoted.length > 1) {
            voterDropdown.innerHTML = unvoted.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
            voterSelector.style.display = 'block';
        } else {
            voterSelector.style.display = 'none';
        }
        
        let html = '';
        data.players.forEach(p => {
            const alreadyVoted = data.votes_count && data.votes_count > 0 && p.id in data.votes;
            html += `<button class="btn btn-option" style="text-align:left; padding-left:15px;" onclick="castVote('${p.id}')" id="vote-btn-${p.id}">
                ${p.is_manual ? '👤' : '📱'} ${p.name} ${alreadyVoted ? '✅' : ''}
            </button>`;
        });
        document.getElementById('vote-options').innerHTML = html;
        
        for (let pid in data.votes) {
            const btn = document.getElementById(`vote-btn-${pid}`);
            if (btn) {
                btn.disabled = true;
                btn.classList.add('voted-btn');
                btn.innerText = btn.innerText.replace('✅', '').trim() + ' ✅ Voted';
            }
        }
    }

    document.getElementById('vote-status-msg').innerText = `Votes Cast: ${data.votes_count} / ${data.total_players}`;
    document.getElementById('host-voting-control-end').style.display = isHost ? 'block' : 'none';
}

function castVote(targetId) {
    let voterId = myPlayerId;
    const voterSelector = document.getElementById('voter-selector');
    const voterDropdown = document.getElementById('voter-dropdown');
    if (voterSelector.style.display !== 'none') {
        voterId = voterDropdown.value;
        if (!voterId && unvotedDevicePlayers.length > 0) {
            voterId = unvotedDevicePlayers[0].id;
        }
    } else {
        if (unvotedDevicePlayers.length === 1) {
            voterId = unvotedDevicePlayers[0].id;
        }
    }
    
    if (!voterId) {
        alert("Cannot determine voter. All votes on this device may be cast.");
        return;
    }

    fetch('/online/cast_vote', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom, voter_id: voterId, target_id: targetId})
    }).then(r => r.json()).then(data => {
        if (!data.success) {
            alert(data.error || "Failed to cast vote.");
        } else {
            if (document.getElementById('voter-selector').style.display !== 'none') {
                const flash = document.getElementById('shared-voting-flash');
                flash.style.display = 'block';
                setTimeout(() => { flash.style.display = 'none'; }, 1500);
            }
            pollOnlineRoom();
        }
    });
}

function endOnlineVoting() {
    fetch('/online/end_voting', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom})
    });
}

// ----- RESULTS -----
function renderResults(data) {
    showScreen('screen-online-results');
    document.getElementById('chameleon-identity').innerText = `🦎 The Chameleon was: ${data.chameleon_name}`;
    document.getElementById('target-word-identity').innerText = `🎯 Target Word: ${data.secret_word}`;
    
    let resultsHtml = '';
    data.vote_results.sort((a,b) => b.count - a.count).forEach(vr => {
        resultsHtml += `<div style="display:flex; justify-content:space-between; margin:8px 0; border-bottom:1px solid #334155; padding-bottom:4px;">
            <span>${vr.name}</span>
            <span style="font-weight:bold; color:var(--accent);">${vr.count} vote${vr.count!==1?'s':''}</span>
        </div>`;
    });
    document.getElementById('vote-breakdown').innerHTML = resultsHtml;

    document.getElementById('host-results-controls').style.display = isHost ? 'block' : 'none';
    document.getElementById('guest-results-msg').style.display = isHost ? 'none' : 'block';
}

function resetOnlineUI() {
    document.getElementById('online-player-code-input').value = "";
    document.getElementById('online-decrypted-info').style.display = 'none';
    document.getElementById('online-target-lock-warning').style.display = 'none';
    onlineActiveHighlight = null;
    onlineTargetHidden = false;
    onlineTargetLocked = false;
    onlineIsChameleonUser = false;
    const btn = document.getElementById('online-toggle-target-btn');
    btn.innerText = "👁️ Hide Target";
    btn.className = "btn btn-option";
    btn.disabled = false;
}

function restartOnlineGame() {
    fetch('/online/restart', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({room_id: currentRoom})
    });
}

// ========== SHARED MODAL (TOPIC) ==========
function openTopicModal(mode) {
    modalTargetMode = mode;
    document.getElementById('shared-topic-modal').style.display = 'flex';
}

function closeTopicModal() {
    document.getElementById('shared-topic-modal').style.display = 'none';
}

function changeTopic(type) {
    const topic = document.getElementById('shared-topic-select').value;
    const url = modalTargetMode === 'local' ? '/local/change_topic' : '/online/change_topic';
    const payload = modalTargetMode === 'local' ? {type, topic} : {room_id: currentRoom, type, topic};
    
    fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    }).then(() => {
        closeTopicModal();
        if (modalTargetMode === 'local') {
            resetLocalUI();
            checkLocalState();
        } else {
            resetOnlineUI();
            pollOnlineRoom();
        }
    });
}
</script>
</body>
</html>
"""

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')