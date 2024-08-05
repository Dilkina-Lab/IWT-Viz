import pandas as pd
import folium
from shiny import App, render, ui
import branca.colormap as cm
import os

# Load airport data
df = pd.read_csv('airport_features.csv')

# Print the first few rows to verify data is loaded correctly
print(df.head())

# Define the UI
app_ui = ui.page_fluid(
    ui.h2("Airport Incidents Map"),
    ui.output_ui("map_ui")
)

# Create the server function
def server(input, output, session):
    @output
    @render.ui
    def map_ui():
        # Create a map centered at an arbitrary location with max bounds and no tile wrapping
        m = folium.Map(
            location=[20, 0],
            zoom_start=2,
            max_bounds=True,
            no_wrap=True
        )

        # Set max bounds to the world
        m.fit_bounds([[-90, -180], [90, 180]])

        # Add a tile layer with English labels and no wrapping
        folium.TileLayer(
            tiles='https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
            attr='&copy; <a href="https://carto.com/">Carto</a> contributors',
            subdomains='abcd',
            min_zoom=1,
            max_zoom=19,
            no_wrap=True  # Prevent map wrapping
        ).add_to(m)

        # Create a colormap for the incident counts
        colormap = cm.LinearColormap(
            colors=['yellow', 'orange', 'red', 'darkred'],
            vmin=1,
            vmax=25,
            caption='Incident Counts'
        )
        colormap.add_to(m)

        # Add markers for each airport, color-coded by incident counts
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

        # Save the map to an HTML file
        map_path = 'map.html'
        m.save(map_path)

        # Return an iframe containing the map
        return ui.HTML(f'<iframe src="{map_path}" width="100%" height="600"></iframe>')

# Create the app
app = App(app_ui, server)

# Run the app
if __name__ == '__main__':
    app.run()
