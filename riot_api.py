import pandas as pd
import requests
import time
import numpy as np
import json
import concurrent.futures
import jsonlines
import config
import sys
from urllib.parse import quote

region_base_url_dict = config.region_base_url_dict

api_key = pd.read_json('./secrets.json')['riot_api_key'][0]

timeline_by_match_id_url = '/lol/match/v4/timelines/by-match/'

match_by_match_id_url = '/lol/match/v4/matches/'

account_by_name_url = '/lol/summoner/v4/summoners/by-name/'

match_hist_by_id_url = '/lol/match/v4/matchlists/by-account/'

champions_df = pd.read_csv('./data/champions_df.csv')

def to_op_gg(name, region):
    name = quote(name)

    if region == 'kr':
        base_url = 'https://www.op.gg/summoner/userName='
    elif region == 'eun':
        base_url = 'https://eune.op.gg/summoner/userName='
    elif region == 'la1':
        base_url = 'https://lan.op.gg/summoner/userName='
    elif region == 'la2':
        base_url = 'https://las.op.gg/summoner/userName='
    else:
        base_url = f'https://{region}.op.gg/summoner/userName='
    
    return f'{base_url}{name}'

def champ_number_to_name(champ_number):
    return champions_df.loc[champions_df['key'] == int(champ_number),'name'].values[0]

def roles_to_single_value(role, lane):
    if lane == 'TOP':
        return 'Top'
    elif lane == 'MIDDLE':
        return 'Mid'
    elif lane == 'JUNGLE':
        return 'Jungle'
    elif role == 'DUO_CARRY':
        return 'Bot_Carry'
    elif role =='DUO_SUPPORT':
        return 'Support'

def get_summoner_by_name(base_url, summoner_name):
    return requests.get(f'https://{base_url}{account_by_name_url}{summoner_name}?api_key={api_key}')

def get_match_hist(account_id, base_url, queue = '420'):
    return requests.get(f'https://{base_url}{match_hist_by_id_url}{account_id}?api_key={api_key}&queue={queue}')

def get_match(match_id, base_url):
    return requests.get(f'https://{base_url}{match_by_match_id_url}{match_id}?api_key={api_key}'),requests.get(f'https://{base_url}{timeline_by_match_id_url}{match_id}?api_key={api_key}')

def remove_short_games(match_list, timeline_list):                    
    good_matches = []
    good_timelines = []
    valid = []
    game_ids = set()
    
    for i, match in enumerate(match_list):
        if match['gameDuration'] / 60 > 15 and match['gameId'] not in game_ids:
            add = True
            # Remove games where a player didn't reach level 6 (based on EDA)
            for participant in match['participants']:
                if participant['stats']['champLevel'] < 7:
                    add = False
            if add:
                good_matches.append(match)
                valid.append(i)
                game_ids.add(match['gameId'])
            else:
                pass
        
    for i, timeline in enumerate(timeline_list):
        if i in valid:
            good_timelines.append(timeline)
    
    return good_matches, good_timelines

def get_stats(summoner, region, matches, timelines, team_participants = ([1,2,3,4,5],[6,7,8,9,10])):
# For each player:
    output = pd.DataFrame(columns=['champ_played', 'role','lane', 'csd_10',
                                  'gold_d_10','xpd_10','dmg_share','dmg_taken_share','vision_score',
                                  'kill_participation','obj_dmg_share','dragons','barons','wards_cleared',
                                  'vision_wards_purchased','kda_early', 'kda_mid', 'kda_late', 
                                   'solo_kills', 'teamfight_kills', 'skirmish_kills', 'wards_early', 
                                   'wards_mid', 'wards_late'])
    # Main role = most played role where role is played > 40% of the time
    # Main champion = most played champion
    # Select all matches and timelines that they are in
    for i, match in enumerate(matches):
        is_in_game = summoner in [summoner['player']['summonerId'] for summoner in match['participantIdentities']]
        if is_in_game:
        # For each match:
        # Match info:
            game_id = match['gameId']
            player_id = int([player['participantId'] for player in match['participantIdentities'] if player['player']['summonerId'] == summoner][0]) - 1
            player_name = match['participantIdentities'][player_id]['player']['summonerName']
            
            # Identify champion played
            champ_played = match['participants'][player_id]['championId']
            
            # Identify role played
            role = match['participants'][player_id]['timeline']['role']
            lane = match['participants'][player_id]['timeline']['lane']
            # Identify lane opponent
            team = match['participants'][player_id]['teamId']
            team_index = int(str(team)[0]) - 1
            teammates = team_participants[team_index]
               
            # Get CSD, GoldD and XPD @ 10
            csd_10 = match['participants'][player_id]['timeline']['creepsPerMinDeltas']['0-10']
            gold_d_10 = match['participants'][player_id]['timeline']['goldPerMinDeltas']['0-10']
            xpd_10 = match['participants'][player_id]['timeline']['xpPerMinDeltas']['0-10']
            
            # Get DMG share
            total_dmg = np.sum([player['stats']['totalDamageDealtToChampions'] for player in match['participants'] if player['teamId'] == team])
            dmg_share = match['participants'][player_id]['stats']['totalDamageDealtToChampions'] / total_dmg
            
            # Get DMG Taken share
            total_dmg_taken = np.sum([player['stats']['totalDamageTaken'] for player in match['participants'] if player['teamId'] == team])
            dmg_taken_share = match['participants'][player_id]['stats']['totalDamageTaken'] / total_dmg_taken
            
            # Get vision score
            vision_score = match['participants'][player_id]['stats']['visionScore']
            
            # Get overall kill participation
            team_kills = np.sum([player['stats']['kills'] for player in match['participants'] if player['participantId'] in teammates]) + 1
            kill_participation = (match['participants'][player_id]['stats']['kills'] + match['participants'][player_id]['stats']['assists']) / team_kills
            
            # % of team's objective damage % of team's turret damage
            total_obj_dmg = np.sum([player['stats']['damageDealtToObjectives'] for player in match['participants'] if player['teamId'] == team])
            obj_dmg_share = match['participants'][player_id]['stats']['damageDealtToObjectives'] / total_obj_dmg
            
            # Team % of dragons killed
            team_dragons = match['teams'][team_index]['dragonKills']
            total_dragons = team_dragons + match['teams'][0 if team_index == 1 else 1]['dragonKills']
            dragons = team_dragons / (total_dragons + 1)
            
            # Team % of barons killed
            team_barons = match['teams'][team_index]['baronKills']
            total_barons = team_barons + match['teams'][0 if team_index == 1 else 1]['baronKills']
            barons = team_barons / (total_barons + 1)
            
            # Get wards cleared
            wards_cleared = match['participants'][player_id]['stats']['wardsKilled']
            
            # Get pinks purchased
            vision_wards_purchased = match['participants'][player_id]['stats']['visionWardsBoughtInGame']
            
            # For each timeline:
            timeline = timelines[i]
            
            kills = 0
            kda = 0
            kda_early = 0
            kda_mid = 0
            kda_late = 0
            solo_kills = 0
            teamfight_kills = 0
            skirmish_kills = 0
            wards = 0
            wards_early = 0
            wards_mid = 0
            wards_late = 0
            
            for i, frame in enumerate(timeline['frames']):
                for event in frame['events']:
                    # Get 0-10 K+D+A
                    # Get 10-20 K+D+A
                    # Get 20+ K+D+A
                    if event['type'] == 'CHAMPION_KILL':
                        if (player_id + 1) == event['killerId'] or (player_id + 1) == event['victimId'] or (player_id + 1) in event['assistingParticipantIds']:
                            kda += 1
                            if i < 12:
                                kda_early += 1
                            elif i < 22:
                                kda_mid += 1
                            else:
                                kda_late += 1

                        if (player_id + 1) == event['killerId']:
                            kills += 1
                    # get number of solo kills
                    # get number of skirmish kills
                    # get number of teamfight kills
                            if event['assistingParticipantIds'] == []:
                                solo_kills += 1
                            if len(event['assistingParticipantIds']) == 1:
                                skirmish_kills += 1
                            if  len(event['assistingParticipantIds']) > 1:
                                teamfight_kills += 1
                    # Get 0-10 wards placed
                    # Get 10-20 wards placed
                    # Get 20+ wards placed
                    if event['type'] == 'WARD_PLACED' and (player_id + 1) == event['creatorId']:
                        wards += 1
                        if i < 12:
                            wards_early += 1
                        elif i < 22:
                            wards_mid += 1
                        else:
                            wards_late += 1 
            
            solo_kills /= kills + 1
            skirmish_kills /= kills + 1
            teamfight_kills /= kills + 1
            wards_early /= wards + 1
            wards_mid /= wards + 1
            wards_late /= wards + 1 
            kda_early /= kda + 1
            kda_mid /= kda + 1
            kda_late /= kda + 1
            
            # Wards cleared and vision wards purchased as a % of wards placed
            wards_cleared /= wards + 1
            vision_wards_purchased /= wards + 1
            
            output = output.append({'champ_played':champ_played, 'role':role, 'lane':lane,
             'csd_10':csd_10,'gold_d_10':gold_d_10,'xpd_10':xpd_10,'dmg_share':dmg_share,
             'dmg_taken_share':dmg_taken_share,'vision_score':vision_score,
             'kill_participation':kill_participation,'obj_dmg_share':obj_dmg_share,'dragons':dragons,
             'barons':barons,'wards_cleared':wards_cleared,'vision_wards_purchased':vision_wards_purchased,
             'kda_early':kda_early, 'kda_mid':kda_mid, 'kda_late':kda_late, 'solo_kills':solo_kills, 
             'teamfight_kills':teamfight_kills, 'skirmish_kills':skirmish_kills, 'wards_early':wards_early, 
             'wards_mid':wards_mid, 'wards_late':wards_late}, ignore_index=True)
    
    most_played_champ = output['champ_played'].value_counts().index[0]
    most_played_role = output['role'].value_counts().index[0]
    most_played_lane = output['lane'].value_counts().index[0]
    
    output.drop(columns=['champ_played','role','lane'], inplace=True)

    output = pd.DataFrame(output.mean()).transpose()
    output['summoner_id'] = [summoner]
    output['most_played_champ'] = most_played_champ
    output['most_played_role'] = most_played_role
    output['most_played_lane'] = most_played_lane
    output['region'] = region
    output['player_name'] = player_name

    output['op_gg'] = [to_op_gg(name, region) for name, region in zip(output['player_name'], output['region'])]

    output['most_played_champ_name'] = output['most_played_champ'].map(champ_number_to_name)

    output['role'] = [roles_to_single_value(role, lane) for role, lane in zip(output['most_played_role'], output['most_played_lane'])]

    return output

def process(summoner_account, region):

    match_hist = get_match_hist(summoner_account['accountId'], region_base_url_dict[region])

    matches = []
    timelines = []

    for i, match in enumerate(match_hist.json()['matches']):
        match, timeline = get_match(match['gameId'], region_base_url_dict[region])
        if match.status_code == 200 and timeline.status_code == 200:
            matches.append(match.json())
            timelines.append(timeline.json())
        else:
            print(f'Match error code: {match.status_code}\nTimeline error code: {timeline.status_code}\n', file=sys.stderr)
        time.sleep(.05)
        if i % 100 == 0 and i != 0:
            time.sleep(120)

    matches, timelines = remove_short_games(matches, timelines)

    player_stats = get_stats(summoner_account['id'], region, matches, timelines)

    return player_stats


