import numpy as np
import pandas as pd
import riot_api as riot
import recommender as rec
import config
from urllib.parse import quote
from flask import Flask, request, render_template

app = Flask('myApp')

champions_df = pd.read_csv('./data/champions_df.csv')

# Home Page
@app.route('/')
def home():
    return render_template('home_page.html')

# Results page
@app.route('/results')
def results():
    # Get request arguments
    region = request.args['region']
    summoner_name = request.args['summoner_name']

    if request.args['champion'] == "any_champion":
        champion = 'any_champion'
    elif request.args['champion'] == "my_champion":
        champion = "my_champion"
    elif request.args['champion'] == "specific_champion":
        champion =  request.args['specific_champion']

    if request.args['role'] == "any_role":
        role = 'any_role'
    elif request.args['role'] == "my_role":
        role = "my_role"
    elif request.args['role'] == "specific_role":
        role = request.args['specific_role']

    filter_options = {'champion':champion,'role':role}

    print(filter_options)

    summoner_account = riot.get_summoner_by_name(config.region_base_url_dict[region], summoner_name)

    if summoner_account.status_code != 200:
        return "<html><body><p>Sorry, we couldn't find this summoner. Please try re-entering your information.</p></body></html>"
    
    player_data = riot.process(summoner_account.json(), region)

    recommendations = rec.recommend(player_data, filter_options)

    return render_template('results_page.html', recommendations=recommendations)


# run the app
if __name__ == '__main__':
    app.run(debug = True)