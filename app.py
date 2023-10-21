from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from board import generate_dynamic_board_html
from decks import create_energy_deck, create_environment_deck, create_mission_deck, create_organism_deck, shuffle_decks
from mission import mission_objectives
import random
from logging import debug as ld

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Structured game state
game_state = {
    'players': {},
    'board': {},
    'organism_deck': [],
    'organism_discard_deck':[],
    'energy_deck': [],
    'environment_deck': [],
    'mission_deck': [],
    'mission_objectives': [],
    'round_number': 1,
    'stored_energy': 0,
    'starting_player':None,
    'current_player': None,
    'players_completed_card_change': [],
    'consecutive_skips': 0
}


def initialize_game():
    # Populate and shuffle decks
    game_state['organism_deck'] = create_organism_deck()
    game_state['energy_deck'] = create_energy_deck()
    game_state['environment_deck'] = create_environment_deck()
    game_state['mission_deck'] = create_mission_deck()
    game_state['organism_discard_deck'] = []
    shuffle_decks(game_state['organism_deck'], game_state['energy_deck'], 
                  game_state['environment_deck'], game_state['mission_deck'])

    # Assign the top card of the environment deck as the current environment card
    game_state['environment_card'] = game_state['environment_deck'].pop()

    # Initialize players' hands and tasks
    for player_id in game_state['players']:
        game_state['players'][player_id]['tasks'] = [game_state['mission_deck'].pop() for _ in range(3)]
        game_state['players'][player_id]['hands'] = [game_state['organism_deck'].pop() for _ in range(4)]

    # Initialize other game states
    game_state['round_number'] = 1
    game_state['stored_energy'] = 0
    initial_player = random.choice(list(game_state['players'].keys()))
    game_state['starting_player'] = initial_player
    game_state['current_player'] = initial_player
    game_state['board']={}


@socketio.on('initialize_game')
def handle_initialize_game():
    initialize_game()
    
    # Prepare the mission card data to be sent to the client
    mission_card_data = {}
    for player_id, player_data in game_state['players'].items():
        player_tasks = player_data['tasks']
        player_hands = player_data['hands']
        # Convert player tasks to the required format for the client
        # (This step might need adjustments based on the format you want)
        mission_card_data = {}
        for task in player_tasks:
            point = task['point']
            mission_card_data[point] = {
                'point': point,
                'content': mission_objectives[point]['content']
            }
        emit('game_initialized', {
            'environment_card': game_state['environment_card'],
            'mission_card_data': mission_card_data,
            'initial_hand': game_state['players'][player_id]['hands']
            }, room=player_id)

def check_room_status():
    if len(game_state['players']) == 2:
        emit('transition_to_preparation', broadcast=True, room='game_room')

def check_player_readiness():
    if all(player_state.get('ready', False) for player_state in game_state['players'].values()):
        print("Emitting transition_to_game event")
        print(game_state['environment_card'])
        emit('transition_to_game', {
        'environment_card': game_state['environment_card'],
    }, broadcast=True, room='game_room')
        run_game_loop()

@socketio.on('player_ready')
def handle_player_ready():
    player_id = request.sid
    game_state['players'][player_id]['ready'] = True
    i=0
    for _ in game_state['players']:
        if game_state['players'][player_id]['ready'] == True:
            i+=1
    emit('update_prepared_player_count', i, broadcast=True, room='game_room')
    check_player_readiness()

@socketio.on('select_mission')
def handle_select_mission(mission_point):
    player_id = request.sid
    player_data = game_state['players'].get(player_id, {})
    mission_point = int(mission_point)
    player_data['chosen_mission'] = mission_point
    chosen_mission_data = {
        'point': mission_point,
        'content': mission_objectives[mission_point]['content']
    }
    emit('mission_selected', chosen_mission_data, room=player_id)


@socketio.on('connect')
def handle_connect():
    player_id = request.sid
    if player_id not in game_state['players']:
        join_room('game_room')
        game_state['players'][player_id] = {'ready': False}
        print(f"Player {player_id} connected. Total Players: {len(game_state['players'])}")  # Add this line
        emit('player_connected', player_id, broadcast=True, room='game_room')
        emit('update_player_count', len(game_state['players']), broadcast=True, room='game_room')
        check_room_status()

@socketio.on('disconnect')
def handle_disconnect():
    player_id = request.sid
    print(f"Player {player_id} disconnected. Total Players before disconnect: {len(game_state['players'])}")
    leave_room('game_room')
    game_state['players'].pop(player_id, None)
    emit('player_disconnected', player_id, broadcast=True, room='game_room')
    emit('update_player_count', len(game_state['players']), broadcast=True, room='game_room')
    check_room_status()

@socketio.on('some_event_that_changes_board_state')
def handle_board_state_change():
    # Assume board is a dictionary representing the current state of the board
    board_html = generate_dynamic_board_html(board)
    emit('update_dynamic_board', board_html)

def trigger_change_of_cards_stage():
    if game_state['round_number'] != 1:
        current_player_id = game_state['current_player']
        emit('request_card_change', {'hands': game_state['players'][current_player_id]['hands']}, room=current_player_id)
    else:
        trigger_planning_stage()

@socketio.on('request_discard')
def handle_discard_request(data):
    print("Received discarded indices:", data['discarded_indices'])
    player_id = request.sid
    discarded_indices = data['discarded_indices']
    player_data = game_state['players'][player_id]
    print(game_state['organism_deck'])
    # Discard the specified cards and draw new ones
    discarded_cards = [player_data['hands'][index] for index in discarded_indices]
    for card in discarded_cards:
        game_state['organism_discard_deck'].append(card)
    
    new_cards_count = 4 - len(player_data['hands'])
    print(new_cards_count)
    new_cards = [game_state['organism_deck'].pop() for _ in range(new_cards_count)]
    print(new_cards)
    for card in new_cards:
        player_data['hands'].append(card)
    # Notify the player of their new hand
    emit('update_hand', {'hands': player_data['hands']}, room=player_id)
    game_state['players_completed_card_change'].append(request.sid)
    next_player_id = get_next_player(request.sid)
    
    if next_player_id and next_player_id not in game_state['players_completed_card_change']:
        print('next player')
        game_state['current_player'] = next_player_id
        trigger_change_of_cards_stage()
    else:
        print('no next player')
        game_state['players_completed_card_change'] = []  # Reset for next round
        trigger_planning_stage()
    

def trigger_planning_stage():
    game_state['current_player'] = game_state['starting_player']
    game_state['consecutive_skips'] = 0
    updated_board_html = generate_dynamic_board_html(game_state['board'])
    emit('update_board', updated_board_html, broadcast=True)
    request_player_action(game_state['current_player'])
    

def request_player_action(player_id):
    player_data = game_state['players'][player_id]
    emit('request_planning_action', {'hands': player_data['hands'], 'is_active': True}, room=player_id)

    # Inform other players they are not active, so they see only their cards without buttons
    for pid in game_state['players']:
        if pid != player_id:
            emit('request_planning_action', {'hands': game_state['players'][pid]['hands'], 'is_active': False}, room=pid)


@socketio.on('player_planning_action')
def handle_player_planning_action(data):
    player_id = request.sid

    if data['action'] == "play_card":
        position = tuple(map(int, data['position'].split(',')))  # convert "x,y" to (x,y)
        card = data['card']
        

        # Check if the card position is valid (i.e., adjacent to another card)
        if is_valid_position(position):
            # Add the card to the board
            game_state['board'][position] = card
            updated_board_html = generate_dynamic_board_html(game_state['board'])
            
            # Reset the consecutive skip counter
            game_state['consecutive_skips'] = 0
            game_state['players'][player_id]['hands'].remove(card)
            # Notify all players about the updated board
            emit('update_board', updated_board_html, broadcast=True)
        else:
            # Notify the player of an invalid move
            emit('invalid_move', {'message': 'Invalid card position'}, room=player_id)
            return

    elif data['action'] == "skip":
        game_state['consecutive_skips'] += 1

    # Check if all players have skipped consecutively
    if game_state['consecutive_skips'] == len(game_state['players']):
        trigger_survival_stage()
        return

    next_player_id = get_next_player(player_id)
    request_player_action(next_player_id)

def is_valid_position(position):
    # If the board is empty, any position is valid
    if not game_state['board']:
        return True

    if position in game_state['board']:
        return False

    # Check if the given position is adjacent to any existing card on the board
    adjacent_positions = [
        (position[0]-1, position[1]),
        (position[0]+1, position[1]),
        (position[0], position[1]-1),
        (position[0], position[1]+1),
        (position[0]-1, position[1]-1),
        (position[0]-1, position[1]+1),
        (position[0]+1, position[1]-1),
        (position[0]+1, position[1]+1)
    ]

    for pos in adjacent_positions:
        if pos in game_state['board']:
            return True
    return False


def get_all_possible_board_positions(board):
    if not board:
        # If board is empty, perhaps start with a default position
        return [(0, 0)]

    # Determine the current bounds of the board
    min_x = min(coord[0] for coord in board.keys())
    max_x = max(coord[0] for coord in board.keys())
    min_y = min(coord[1] for coord in board.keys())
    max_y = max(coord[1] for coord in board.keys())

    # Expand the bounds by 1 in each direction
    min_x -= 1
    max_x += 1
    min_y -= 1
    max_y += 1

    # Generate all positions within the expanded bounds
    return [(x, y) for x in range(min_x, max_x + 1) for y in range(min_y, max_y + 1)]


@socketio.on('get_valid_locations_for_card')
def get_valid_locations(data):
    card = data['card']
    valid_positions = []
    all_possible_board_positions = get_all_possible_board_positions(game_state['board'])
    for pos in all_possible_board_positions:
        if is_valid_position(pos):
            valid_positions.append(f"{pos[0]},{pos[1]}")  # Convert tuple to "x,y" format
    print(card, valid_positions, all_possible_board_positions)
    print(game_state['board'])
    emit('receive_valid_locations', valid_positions)



def trigger_survival_stage():
    determine_survival_stage_player()
    game_state['round_number']+=1
    trigger_change_of_cards_stage()
    # Logic for the survival stage for the given player

def survival_stage(player_data):
    pass

def get_next_player(current_player_id):
    player_ids = list(game_state['players'].keys())
    current_index = player_ids.index(current_player_id)
    next_index = (current_index + 1) % len(player_ids)
    return player_ids[next_index]

@socketio.on('choose_survival_player')
def choose_survival_player(data):
    chosen_player_id = data['chosen_player_id']
    survival_stage(game_state['players'][chosen_player_id])
    # Continue with the survival stage for the chosen player
    # ...
def determine_survival_stage_player():
    # Get all players' hand sizes
    hand_sizes = {player_id: len(player_data['hands']) for player_id, player_data in game_state['players'].items()}
    
    # Find the minimum hand size
    min_hand_size = min(hand_sizes.values())
    
    # Get the players with the minimum hand size
    players_with_min_hand_size = [player_id for player_id, hand_size in hand_sizes.items() if hand_size == min_hand_size]
    
    # If only one player has the minimum hand size, return that player
    if len(players_with_min_hand_size) == 1:
        survival_stage(game_state['players'][players_with_min_hand_size[0]])
    
    # If multiple players have the minimum hand size, let the starting player choose
    else:
        emit('request_survival_player_choice', {"choices": players_with_min_hand_size}, room=game_state['starting_player'])

def run_game_loop():
    trigger_change_of_cards_stage()

@socketio.on('player_action')
def handle_player_action(data):
    action_type = data['action_type']
    player_id = request.sid
    # Based on the action_type, handle the player's action
    # This will involve calling the appropriate stage function
    # and then updating the game state and emitting any necessary updates
    pass

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001)
