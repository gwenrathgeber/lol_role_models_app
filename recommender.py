import pandas as pd
import numpy as np
import config
from urllib.parse import quote
from sklearn.preprocessing import StandardScaler

def recommend(player_data, options):

    role_models = pd.read_csv('./data/role_models_final.csv')

    X = role_models.drop(columns=['summoner_id','most_played_champ','most_played_role','most_played_lane','region','player_name','most_played_champ_name','op_gg','role'])
    
    y = player_data.drop(columns = ['summoner_id','most_played_champ','most_played_role','most_played_lane','region','player_name','most_played_champ_name','op_gg','role'])

    ss = StandardScaler()
    X_sc = ss.fit_transform(X)
    y_sc = ss.transform(y)

    X_sc = pd.DataFrame(X_sc, columns = X.columns)
    y_sc = pd.DataFrame(y_sc, columns = X.columns)

    differences = X_sc - y_sc.iloc[0,:]
    similarity = differences.apply(np.linalg.norm, ord=2, axis=1)

    role_models['similarity'] = similarity

    results = role_models

    print(options)

    if options['champion'] == 'any_champion' and options['role'] == 'any_role':
        results = results.sort_values('similarity')

    if options['champion'] == 'my_champion':
        results = results[results['most_played_champ_name'] == player_data.loc[0,'most_played_champ_name']]

    if options['role'] == 'my_role':
        results = results[results['role'] == player_data.loc[0,'role']]

    if options['champion'] != 'any_champion' and options['champion'] != 'my_champion':
        results = results[results['most_played_champ_name'].str.lower().str.replace("'","") == options['champion'].lower().replace("'","")]

    if options['role'] != 'any_role' and options['role'] != 'my_role':
        results = results[results['role'] == options['role']]

    results = results[['player_name','most_played_champ_name','role','region','op_gg']]
    
    results = results.head(10)

    return results.to_dict(orient='split')