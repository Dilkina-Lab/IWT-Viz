import pandas as pd
import folium
from flask import Flask, render_template_string
from flask_cors import CORS
import branca.colormap as cm

# load airport data
df = pd.read_csv('airport_features.csv')

#print(df.head())

# Initialize Flask app
app = Flask(__name__)
CORS(app)


def create_map():
    print("creating map...")
    # Create a map centered at an arbitrary location
    m = folium.Map(location=[20, 0], zoom_start=2, max_bounds = True, no_wrap = True)

    # set max bounds  world
    m.fit_bounds([[-90, -180], [90, 180]])


    # add tile layer w/ English labels
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
        attr='&copy; <a href="https://carto.com/">Carto</a> contributors',
        subdomains='abcd',
        min_zoom=1,
        max_zoom=19,
       no_wrap=True,
        #continuous_world=False
    ).add_to(m)


     # create  colormap for  incident counts (example)
    colormap = cm.LinearColormap(
        colors=['yellow', 'orange', 'red', 'darkred'],
        vmin=1,
        vmax=25,
        caption='Incident Counts'
    )
    colormap.add_to(m)

   
    # add markers for each airport
    for _, airport in df.iterrows():
        if pd.notnull(airport['latitude']) and pd.notnull(airport['longitude']) and airport['incident_counts'] > 0:
            color = colormap(airport['incident_counts'])
            folium.CircleMarker(
                location=[airport['latitude'], airport['longitude']],
                radius=5,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                popup=folium.Popup(
                    f"<b>{airport['name']}</b><br>Code: {airport['IATA']}<br>{airport['city']}, {airport['country']}<br>Incidents: {airport['incident_counts']}"
                )
            ).add_to(m)

    # aave  map to  HTML file
    m.save('map.html')

create_map()

# rout to serve  map
@app.route('/')
def index():
    return render_template_string(open('map.html').read())

# run  Flask app without  reloader
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)