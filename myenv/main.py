import pandas as pd
import folium
from flask import Flask, render_template_string
from flask_cors import CORS

# Load airport data
df = pd.read_csv('airport_features.csv')

#print(df.head())

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Function to create the map
def create_map():
    print("creating map...")
    # Create a map centered at an arbitrary location
    m = folium.Map(location=[20, 0], zoom_start=2)

    # Add a tile layer
    folium.TileLayer('openstreetmap').add_to(m)

    # Add markers for each airport
    for _, airport in df.iterrows():
        if pd.notnull(airport['latitude']) and pd.notnull(airport['longitude']):
            folium.CircleMarker(
                location=[airport['latitude'], airport['longitude']],
                radius=5,
                color='red',
                fill=True,
                fill_color='red',
                fill_opacity=0.8,
                popup=folium.Popup(
                    f"<b>{airport['name']}</b><br>Code: {airport['IATA']}<br>{airport['city']}, {airport['country']}<br>Incidents: {airport['incident_counts']}")
            ).add_to(m)

    # Save the map to an HTML file
    m.save('map.html')

# Create the map
create_map()

# Route to serve the map
@app.route('/')
def index():
    return render_template_string(open('map.html').read())

# Run the Flask app without the reloader
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)