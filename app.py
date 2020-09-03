import numpy as np
import pandas as pd
from flask import Flask, request, Response, render_template, jsonify

app = Flask('myApp')

# Home Page
@app.route('/')
def home():
    return render_template('home_page.html')

# Results page
@app.route('/results')
def results():
    return render_template('results_page.html')