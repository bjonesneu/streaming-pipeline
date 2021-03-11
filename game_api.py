#!/usr/bin/env python
import json
import uuid

from datetime import timedelta
from datetime import datetime

from kafka import KafkaProducer
from flask import Flask, request, redirect

import redis
datastore = redis.Redis(host='redis', port='6379')

app = Flask(__name__)
producer = KafkaProducer(bootstrap_servers='kafka:29092')

all_events_topic = 'placebo_all_events'
buy_events_topic = 'placebo_buy_events'
social_events_topic = 'placebo_social_events'

def generate_UUID():
    return str(uuid.uuid4())

def get_timestamp():
#    print(str(datetime.now()))
    return str(datetime.now())

def log_to_kafka(topic, event):
    event.update(request.headers)
    producer.send(topic, json.dumps(event).encode())

def purchase_item(event):
    userid = event['user_id']
    item = event['type']
    cost = event['cost']
    # get user account info from redis
    user_account = json.loads(datastore.get(userid))
    user_account['user_pwd'] = '****'
    event['player_created'] = user_account['created']
    event['player_wealth'] = user_account['wealth']
    event['player_num_items'] = len(user_account['inventory'])
    success_flag = False # user did not have adequate funds
    if user_account['wealth'] > cost: # user_has_funds
        user_account['wealth'] = user_account['wealth'] - cost
        user_account['inventory'].append(item)
        datastore.set(userid, json.dumps(user_account))
        success_flag = True
    buy_event = {
        'event_type': event['event_type'],
        'event': event,
        'user': user_account,
        'item': item,
        'cost': cost,
        'status': success_flag
    }
    log_to_kafka(buy_events_topic, buy_event)
    return success_flag

def join_org(event):
    # the cost does not matter - a player can go into debt to join an org
    user_account = json.loads(datastore.get(event['user_id']))
    user_account['user_pwd'] = '****'
    event['player_created'] = user_account['created']
    event['player_wealth'] = user_account['wealth']
    event['player_num_affiliations'] = len(user_account['affiliations'])
    affiliation = {
        'org': event['org'],
        'level': event['level'],
        'joined_ts': get_timestamp()
    }
    user_account['affiliations'].append(affiliation)
    if event['cost']:
        user_account['wealth'] = user_account['wealth'] - event['cost']
    datastore.set(event['user_id'], json.dumps(user_account))
    log_to_kafka(social_events_topic, event)
    return True

# define common_attributes for the event
def base_event():    
    return {
        'id': generate_UUID(),
        'type': 'default',
        'timestamp': get_timestamp()
    }

@app.route("/")
def default_response():
    game_event = base_event()
    game_event['event_type'] = 'root_url_accessed'
    game_event['agent_meta'] = request.user_agent.string
    log_to_kafka(all_events_topic, game_event)
    return redirect('static/register.html')
    return "Welcome to the game!  Your first mission is to login.\n"

@app.route("/buy/sword", methods=['GET','POST'])   
def buy_a_sword():
    game_event = base_event()
    if request.method == 'GET':                                            
        return 'using GET method - should use POST'
#    print(request.json)
    msg = "You do not have sufficient funds [:(\n"
    game_event['user_id'] = request.json['userid']
    game_event['event_type'] = 'buy_sword'
    game_event['type'] = request.json['type']
    game_event['cost'] = float(request.json['cost'])
    if purchase_item(game_event):
        game_event['status'] = 'approved_purchase'
        msg = "Sword purchased [:)\n"
    else:
        game_event['status'] = 'insufficient_funds'
    log_to_kafka(all_events_topic, game_event)
    return msg

@app.route("/buy/spell", methods=['GET','POST'])   
def buy_a_spell():
    game_event = base_event()
    if request.method == 'GET':                                            
        return 'using GET method - should use POST'

    msg = "You do not have sufficient funds <:(\n"
    game_event['user_id'] = request.json['userid']
    game_event['event_type'] = 'buy_spell'
    game_event['type'] = request.json['type']
    game_event['cost'] = float(request.json['cost'])
    if purchase_item(game_event):
        game_event['status'] = 'approved_purchase'
        msg = "Spell purchased <:)\n"
    else:
        game_event['status'] = 'insufficient_funds'
    log_to_kafka(all_events_topic, game_event)
    return msg

@app.route("/join/guild", methods=['GET','POST'])   
def join_a_guild():
    game_event = base_event()
    if request.method == 'GET':                                            
        return 'using GET method - should use POST'

    game_event['user_id'] = request.json['userid']
    game_event['event_type'] = 'join_guild'
    game_event['org'] = request.json['org']
    game_event['level'] = request.json['level']
    game_event['cost'] = float(request.json['cost'])

    msg = "Guild not joined [:(\n"
    if join_org(game_event):
        game_event['status'] = 'approved_join'
        msg = "Joined #guild\n"
    else:
        game_event['status'] = 'denied_join'

    log_to_kafka(all_events_topic, game_event)
    return msg

@app.route("/join/team", methods=['GET','POST'])   
def join_a_team():
    game_event = base_event()
    if request.method == 'GET':                                            
        return 'using GET method - should use POST'

    game_event['user_id'] = request.json['userid']
    game_event['event_type'] = 'join_team'
    game_event['org'] = request.json['org']
    game_event['cost'] = float(request.json['cost'])
    game_event['level'] = request.json['level']

    msg = "Team not joined [:(\n"
    if join_org(game_event):
        game_event['status'] = 'approved_join'
        msg = "Joined @team\n"
    else:
        game_event['status'] = 'denied_join'

    log_to_kafka(all_events_topic, game_event)
    return msg

@app.route("/login", methods=['GET','POST'])   
def login():
    game_event = base_event()
    if request.method == 'GET':
        return redirect('static/login.html')
        return 'using GET method - should use POST'

    game_event['event_type'] = 'login'
    game_event['user_id'] = request.form['userid']
    game_event['user_pwd'] = request.form['userpwd']
    log_to_kafka(all_events_topic, game_event)
    return "Logging in >>>\n"

@app.route("/create/user", methods=['GET','POST'])   
def create_user():
    game_event = base_event()
    if request.method == 'GET':
        return redirect('static/register.html')
        return 'using GET method - should use POST'
    
    game_event['user_id'] = request.form['userid']
    game_event['event_type'] = 'create_user'
    game_event['agent_meta'] = request.user_agent.string

    wealth = int(request.form['wealth'])
    character = {
        'user_id': game_event['user_id'], # in future use generate_UUID(),
        'user_pwd': request.form['userpwd'],
        'user_name': request.form['username'],
        'wealth': wealth or 100000, # default value
        'health': 100, # default vsalue
        'inventory': [], # default value
        'affiliations': [], # default value
        'created': game_event['timestamp']
    }
    #persist user profile to redis
#    print(character['user_id'], json.dumps(character))
    datastore.set(character['user_id'], json.dumps(character))
    
    game_event['user_id'] = character['user_id']
    game_event['meta'] = character
    log_to_kafka(all_events_topic, game_event)
    return "Created user +:)\n"

@app.route("/data/user", methods=['GET','POST'])   
def view_user_data():
    game_event = base_event()
    if request.method == 'POST':                                            
        return 'using POST method - should use GET'

    game_event['user_id'] = request.args.get('userid')
    tmp = datastore.get(game_event['user_id'])
#    print(game_event['user_id'], tmp)
    user_account = json.loads(datastore.get(game_event['user_id']))    
    game_event['event_type'] = 'view_user_data'
    game_event['agent_meta'] = request.user_agent.string
    game_event['meta'] = user_account
    log_to_kafka(all_events_topic, game_event)
    return "User data: \n\n" + json.dumps(user_account) + "\n\n"
