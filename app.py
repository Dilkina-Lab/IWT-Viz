import ipyleaflet as L
from ipyleaflet import Map, Marker, CircleMarker, basemaps, LayersControl, TileLayer
from faicons import icon_svg
from geopy.distance import geodesic, great_circle
from shared import BASEMAPS, CITIES
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget
import logging
import pandas as pd
import branca.colormap as cm


# Load airport data
df = pd.read_csv('airport_features.csv')

# Print the first few rows to verify data is loaded correctly
print(df.head())

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

city_names = sorted(list(CITIES.keys()))

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_selectize(
            "loc1", "IWT Information",
            choices=["Overall Incidents", "Transit", "Origin", "Destination", "Seizure"],
            selected="Overall Incidents"
        ),
        ui.input_selectize(
            "loc2", "Location Granularity",
            choices=["Countries", "Airport"],
            selected="Countries"
        ),
        ui.input_selectize(
            "basemap",
            "Choose a basemap",
            choices=["Mapnik", "WorldImagery", "Positron", "DarkMatter", "NatGeoWorldMap"],
            selected="Mapnik",
        ),
        ui.input_dark_mode(mode="dark"),
    ),
    ui.layout_column_wrap(
        ui.value_box(
            "Scale",
            ui.output_text("combined_distances"),
            theme="gradient-blue-indigo",
            style="flex: 3;"  # Set this box to take up 3/4 of the width
        ),
        ui.value_box(
            "Country IWT Value",  # Change the label to "Country IWT Value"
            ui.output_text("altitude"),
            theme="gradient-blue-indigo",
            style="flex: 1;"  # Set this box to take up 1/4 of the width
        ),
        fill=False,
        style="display: flex; justify-content: space-between;"  # Add this line
    ),
    ui.card(
        ui.card_header("Map (drag the markers to change locations)"),
        output_widget("map_widget"),
    ),
    title="Illegal Wildlife Trade Visualization",
    fillable=True,
    class_="bslib-page-dashboard",
)



def server(input, output, session):
    # Create the initial map
    m = Map(center=(20, 0), zoom=2, basemap=basemaps.OpenStreetMap.Mapnik, scroll_wheel_zoom=True)

    # Add a tile layer with English labels and no wrapping
    tile_layer = TileLayer(
        url='https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
        attribution='&copy; <a href="https://carto.com/">Carto</a> contributors',
    )
    m.add_layer(tile_layer)

    # Create a colormap for the incident counts
    colormap = cm.LinearColormap(
        colors=['yellow', 'orange', 'red', 'darkred'],
        vmin=1,
        vmax=25,
        caption='Incident Counts'
    )

    # Add markers for each airport, color-coded by incident counts
    for _, airport in df.iterrows():
        if pd.notnull(airport['latitude']) and pd.notnull(airport['longitude']) and airport['incident_counts'] > 0:
            color = colormap(airport['incident_counts'])
            marker = CircleMarker(
                location=(airport['latitude'], airport['longitude']),
                radius=5,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                title=f"{airport['name']} - Incidents: {airport['incident_counts']}"
            )
            m.add_layer(marker)

# Render the map widget
    @output
    @render_widget
    def map_widget():
        return m

app = App(app_ui, server)


if __name__ == "__main__":
    logger.info("Starting the app")
    app.run()
