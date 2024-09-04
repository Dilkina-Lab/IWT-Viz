import ipyleaflet as L
from ipyleaflet import Map, Marker, CircleMarker, GeoJSON, basemaps, LayersControl, TileLayer, WidgetControl, Choropleth, Popup, ColormapControl
from faicons import icon_svg
from geopy.distance import geodesic, great_circle
from shared import BASEMAPS, CITIES
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget
import logging
import pandas as pd
import branca.colormap as cm
from branca.colormap import linear
from ipywidgets import HTML
import json
import requests



# Load airport data
#df = pd.read_csv('airport_features.csv')
df = pd.read_csv('filtered_airport_features.csv')

country_df = pd.read_csv('country_aggregated_data.csv')

# Print the first few rows to verify data is loaded correctly
print(df.head())



# Load the custom GeoJSON data
with open('custom.geo.json') as f:
    geojson_data = json.load(f)

# Ensure country names are correctly mapped
for feature in geojson_data["features"]:
    feature["name"] = feature["properties"]["name"].lower()

print("Custom GeoJSON data loaded and processed")

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

city_names = sorted(list(CITIES.keys()))

# find  third-highest incident count
sorted_incidents = sorted(df['incident_counts'].dropna(), reverse=True)
third_highest = sorted_incidents[2] if len(sorted_incidents) > 2 else max(sorted_incidents)

# Find third-highest incident count in the country data
sorted_values = sorted(country_df['incident_counts'].dropna(), reverse=True)
third_highest_df = sorted_values[2] if len(sorted_values) > 2 else max(sorted_values)

print("Sort Complete!")

print("Sort Complete!")

#colormap with the appropriate scale
colormap = cm.LinearColormap(
    colors=['yellow', 'orange', 'red', 'darkred'],
    vmin=1,
    vmax=third_highest,
    caption='Incident Counts'
)
colormap.text_color = "black"

colormap_df = cm.LinearColormap(
    colors=['yellow', 'orange', 'red', 'darkred'],
    vmin=1,
    vmax=80,
    #vmax=third_highest_df,
    caption='Incident Counts'
)
colormap_df.text_color = "black"

# Define color scales for both airports and countries
#colormap = cm.linear.YlOrRd_09.scale(1, third_highest)
#colormap.caption = "Airport Incident Counts"
colormap.text_color = "black"  # Ensures text is visible on the map

#colormap_df = cm.linear.YlOrRd_09.scale(1, third_highest_df)
#colormap_df.caption = "Country Incident Counts"

colormap_df.text_color = "black"

# Define color scales for both airports and countries

# Continuous color map based on the selected metric
#colormap = linear.YlOrRd_09.scale(1, third_highest)
#colormap.caption = 'Incident Counts'

#colormap_df = linear.YlOrRd_09.scale(1, third_highest_df)
#colormap_df.caption = 'Incident Counts'

# Colormap with the appropriate scale
#colormap_df_country = linear.Reds_05.scale(1, third_highest_df).to_step(n=5)
#colormap_df_country = linear.Reds_05.scale(1, 20).to_step(n=5)


proper_name_mapping = {
    "dominican rep.": "dominican republic",
    "falkland is.": "falkland islands",
    "afghanistan": "afghanistan",
    "bhutan": "bhutan",
    "n. cyprus": "north cyprus",
    "korea": "south korea",
    "lao pdr": "laos",
    "myanmar": "myanmar",
    "mongolia": "mongolia",
    "palestine": "palestinian territories",
    "dem. rep. korea": "north korea",
    "syria": "syria",
    "timor-leste": "east timor",
    "yemen": "yemen",
    "central african rep.": "central african republic",
    "côte d'ivoire": "ivory coast",
    "dem. rep. congo": "congo (kinshasa)",
    "congo": "congo (brazzaville)",
    "eq. guinea": "equatorial guinea",
    "w. sahara": "western sahara",
    "senegal": "senegal",
    "s. sudan": "south sudan",
    "somaliland": "somalia",
    "swaziland": "eswatini",
    "bosnia and herz.": "bosnia and herzegovina",
    "czech rep.": "czech republic",
    "kosovo": "kosovo",
    "new caledonia": "new caledonia",
    "solomon is.": "solomon islands",
    "vanuatu": "vanuatu",
}

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_selectize(
            "metric", "IWT Information",
            choices=["Overall Incidents", "Transit", "Origin", "Destination", "Seizure"],
            selected="Overall Incidents"
        ),
        ui.input_selectize(
            "loc2", "Location Granularity",
            choices=["Countries", "Airport"],
            selected="Countries"
        ),
        ui.input_dark_mode(mode="dark"),
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
    @reactive.Effect
    def _():
        # Map the selected metric to the corresponding column in the dataframe
        metric_mapping = {
            "Overall Incidents": "incident_counts",
            "Transit": "transit_count",
            "Origin": "origin_count",
            "Destination": "destination_count",
            "Seizure": "seizure_count"
        }
        
        selected_metric = metric_mapping[input.metric()]
        print(f"Selected Metric is: {selected_metric}")

        active_marker = None 


        # Normalize data for the selected metric
        min_val = country_df[selected_metric].min()
        max_val = country_df[selected_metric].max()
        diff = max_val - min_val
        normalized_vals = (country_df[selected_metric] - min_val) / diff

        #mapping = dict(zip(country_df['country'].str.strip(), normalized_vals))
        mapping = dict(zip(country_df['country'], country_df[selected_metric]))


        for feature in geojson_data["features"]:
            country_name = feature["name"]
            if country_name not in mapping:
                if country_name in proper_name_mapping:
                    mapped_name = proper_name_mapping[country_name]
                    mapping[country_name] = mapping.get(mapped_name, 0)
                else:
                    mapping[country_name] = 0
                    print("Name is not in mapping: " + country_name)

        # Define a color scale based on the selected metric
        #colormap = linear.YlOrRd_09.scale(0, 1)
        #colormap.caption = f'{input.metric()}'

        # Find the third-highest value for the selected metric in the airport_features data
        sorted_values = sorted(df[selected_metric].dropna(), reverse=True)
        third_highest = sorted_values[2] if len(sorted_values) > 2 else max(sorted_values)

        # Create the color scale based on the selected metric
        colormap = cm.LinearColormap(
            colors=['yellow', 'orange', 'red', 'darkred'],
            vmin=1,
            vmax=third_highest,
            caption=f'{input.metric()}'
        )
        colormap.text_color = "black"


        # Find third-highest incident count in the country data
        sorted_values = sorted(country_df[selected_metric].dropna(), reverse=True)
        third_highest_df = sorted_values[2] if len(sorted_values) > 2 else max(sorted_values)
        print("Third Highest DF: " + str(third_highest_df))
        colormap_df = cm.LinearColormap(
            colors=['lightyellow', 'yellow', 'orange', 'red', 'darkred', 'brown'],
            vmin=1,
            #vmax=120,
            vmax=third_highest_df,
            caption=f'{input.metric()}'
        )
        colormap_df.text_color = "black"



         # Create a continuous color scale based on the selected metric
        #colormap = linear.YlOrRd_09.scale(1, third_highest)
        #colormap.caption = f'{input.metric()}'

        #colormap_df = linear.YlOrRd_09.scale(1, third_highest_df)
        #colormap_df.caption = f'{input.metric()}'

        # Create the initial map
        m = Map(center=(20, 0), zoom=2, basemap=basemaps.OpenStreetMap.Mapnik, scroll_wheel_zoom=True)

        # Add a tile layer with English labels and no wrapping
        tile_layer = TileLayer(
            url='https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
            attribution='&copy; <a href="https://carto.com/">Carto</a> contributors',
        )
        m.add(tile_layer)

        if input.loc2() == "Airport":
            print(f"Selected Loc is: {input.loc2()}")
            markers = []

            for _, airport in df.iterrows():
                if pd.notnull(airport['latitude']) and pd.notnull(airport['longitude']):
                    if airport[selected_metric] > 0:
                        color = colormap(airport[selected_metric])
                    else:
                        color = '#D3D3D3'  # Gray for zero incidents
                    
                    marker = CircleMarker(
                        location=(airport['latitude'], airport['longitude']),
                        radius=5,
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=1.0,
                        title=f"{airport['name']}\n{input.metric()}: {airport[selected_metric]}"
                    )
                    
                    # Add marker to the map
                    m.add(marker)
                    markers.append(marker)

                    # Create a hidden Marker with the same location
                    hidden_marker = Marker(
                        location=(airport['latitude'], airport['longitude']),
                        opacity=0.0,  # Make the marker invisible
                        title=f"{airport['name']}\n\nOverall Incidents: {airport['incident_counts']}\nTransit: {airport['transit_count']}\nOrigin: {airport['origin_count']}\nDestination: {airport['destination_count']}\nSeizure: {airport['seizure_count']}"
                    )
                    m.add(hidden_marker)
                    markers.append(hidden_marker)

            # Add airport colormap legend to the map
            #airport_legend = WidgetControl(widget=colormap, position='topright')
            #m.add_control(airport_legend)
            # Add airport colormap legend to the map
            #airport_legend_html = colormap._repr_html_()
            #airport_legend_widget = HTML(value=airport_legend_html)
            #airport_legend_control = WidgetControl(widget=airport_legend_widget, position='topright')
            #m.add_control(airport_legend_control)
            # Add a dummy invisible choropleth layer just for the color scale
            #colormap_temp = linear.YlOrRd_04
            dummy_layer = L.Choropleth(
                geo_data={},  # Empty geo_data
                choro_data={},  # No data, purely for color scale
                colormap=colormap,
                value_min=1,
                value_max=third_highest,
                style={'fillOpacity': 0},  # Make the layer invisible
            )
            #m.add(dummy_layer)

            # Add airport colormap legend to the map using ColormapControl
            colormap_control = L.ColormapControl(
                colormap=colormap,
                value_min=dummy_layer.value_min,
                value_max=dummy_layer.value_max,
                caption="Airport Incident Counts",
                position="topright"
            )
            m.add(dummy_layer)
            m.add(colormap_control)
            


        elif input.loc2() == "Countries":
            print(f"Selected Loc is: {input.loc2()}")
            markers = []

            def feature_color(feature):
                country_name = feature["properties"]["name"].lower()
                value = mapping.get(country_name, 0)
                color = '#D3D3D3' if value == 0 else colormap_df(value)
                return {
                    'color': 'black',
                    'fillColor': color,
                    'fillOpacity': 0.75,
                    'weight': 1
                }

            # Create a GeoJSON layer with style callback
            geo_json_layer = GeoJSON(
                data=geojson_data,
                style_callback=feature_color,
                hover_style={
                    'color': 'white',
                    'fillOpacity': 0.95
                }
            )

            def on_click(event, feature, **kwargs):
                nonlocal active_marker
                country_name = feature['properties']['name'].lower()

                if country_name in proper_name_mapping:
                    country_name = proper_name_mapping[country_name]

                print(f"Clicked on: {country_name}")

                country_data = country_df.loc[country_df['country'].str.strip().str.lower() == country_name]
                if country_data.empty:
                    print(f"No data found for country: {country_name}")
                    return
                
                coordinates = feature['geometry']['coordinates']
                if feature['geometry']['type'] == 'Polygon':
                    centroid = calculate_centroid(coordinates[0])
                elif feature['geometry']['type'] == 'MultiPolygon':
                    centroid = calculate_centroid(coordinates[0][0])

                print("Centroid:", centroid)

                # Remove the existing marker if any
                if active_marker and active_marker in m.layers:
                    m.remove_layer(active_marker)

                # Information for the marker title
                overall_incidents = country_df.loc[country_df['country'] == country_name, 'incident_counts'].values[0]
                transit = country_df.loc[country_df['country'] == country_name, 'transit_count'].values[0]
                origin = country_df.loc[country_df['country'] == country_name, 'origin_count'].values[0]
                destination = country_df.loc[country_df['country'] == country_name, 'destination_count'].values[0]
                seizure = country_df.loc[country_df['country'] == country_name, 'seizure_count'].values[0]

                title = (
                    f"{country_name.capitalize()}\n\n"
                    f"Overall Incidents: {overall_incidents}\n"
                    f"Transit: {transit}\n"
                    f"Origin: {origin}\n"
                    f"Destination: {destination}\n"
                    f"Seizure: {seizure}"
                )

                # Create and add the new marker
                active_marker = Marker(
                    location=centroid,
                    opacity=1.0,
                    title=title
                )
                m.add_layer(active_marker)

            def calculate_centroid(polygon):
                x, y = zip(*polygon)
                centroid_x = sum(x) / len(polygon)
                centroid_y = sum(y) / len(polygon)
                return (centroid_y, centroid_x)

            geo_json_layer = GeoJSON(
                data=geojson_data,
                style_callback=feature_color,
                hover_style={'color': 'white', 'fillOpacity': 0.95}
            )
            geo_json_layer.on_click(on_click)
            m.add_layer(geo_json_layer)


            # Add a dummy invisible choropleth layer just for the color scale
            dummy_layer_df = L.Choropleth(
                geo_data={},  # Use the same geo_data for proper min/max scaling
                choro_data={},  # Use the country data for scaling
                colormap=colormap_df,
                value_min=1,
                value_max=third_highest_df,
                key_on='id',
                style={'fillOpacity': 0},  # Make the layer invisible
            )
            m.add(dummy_layer_df)

        # Add country colormap legend to the map using ColormapControl
        colormap_control_df = L.ColormapControl(
            colormap=colormap_df,
            value_min=1,
            value_max=third_highest_df,
            caption="Country Incident Counts",
            position="topright"
        )
        m.add_control(colormap_control_df)


        # Render the map widget
        @output
        @render_widget
        def map_widget():
            return m

app = App(app_ui, server)


if __name__ == "__main__":
    logger.info("Starting the app")
    app.run()
