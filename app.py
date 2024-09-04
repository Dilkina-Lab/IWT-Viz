import json
import math
from collections import defaultdict
import os
from rapidfuzz import process, fuzz
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import branca
import ipyleaflet as L
import requests
from IPython.core.display_functions import display
from ipyleaflet import Map, Marker, CircleMarker, basemaps, LayersControl, TileLayer, Popup, AwesomeIcon, GeoJSON, Choropleth, ColormapControl
from shared import BASEMAPS, CITIES
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_widget
import logging
import pandas as pd
import geopandas as gpd
import branca.colormap as cm
import ipywidgets as widgets
from matplotlib.colors import Normalize
import pickle
import branca.element
from IPython.display import Javascript
from geopy.distance import geodesic, great_circle

# Load airport and IWT data
df = pd.read_csv('filtered_airport_features.csv')
iwt_df = pd.read_csv('iwt_volume.csv')
country_df = pd.read_csv('country_aggregated_data.csv')
gdf = gpd.read_file('countries.geo.json')
country_names = gdf['name'].tolist()

# Define a path for the pickle file
pickle_file_path = 'No_IWT_map_state.pkl'

# Create a dictionary to map country names to their central coordinates
map_config = {row['name']: (row.geometry.centroid.y, row.geometry.centroid.x) for _, row in gdf.iterrows()}

# Ensure country names are correctly mapped
with open('custom.geo.json') as f:
    geojson_data = json.load(f)

for feature in geojson_data["features"]:
    feature["name"] = feature["properties"]["name"].lower()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

city_names = sorted(list(CITIES.keys()))

# Create colormaps for heatmaps
sorted_incidents = sorted(df['incident_counts'].dropna(), reverse=True)
third_highest = sorted_incidents[2] if len(sorted_incidents) > 2 else max(sorted_incidents)

sorted_values = sorted(country_df['incident_counts'].dropna(), reverse=True)
third_highest_df = sorted_values[2] if len(sorted_values) > 2 else max(sorted_values)

colormap_airport = cm.LinearColormap(
    colors=['yellow', 'orange', 'red', 'darkred'],
    vmin=1,
    vmax=third_highest,
    caption='Airport Incident Counts'
)
colormap_airport.text_color = "black"

colormap_country = cm.LinearColormap(
    colors=['lightyellow', 'yellow', 'orange', 'red', 'darkred', 'brown'],
    vmin=1,
    vmax=third_highest_df,
    caption='Country Incident Counts'
)
colormap_country.text_color = "black"

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
        ui.HTML('''
                    <style>
                    .info-bubble {
                        display: inline-block;
                        margin-right: 5px;
                        cursor: pointer;
                    }
                    .iwt-info-container,
                    .granularity-info-container,
                    .checkbox-info-container {
                        display: flex;
                        align-items: center;
                    }
                    .dropdown-info-container {
                        display: flex;
                        align-items: center;
                        margin-left: 0px; /* Adjust this value to fine-tune alignment */
                    }
                    .checkbox-info-container label {
                        margin-left: 20px;
                    }
                    </style>
                    <script>
                    function showInfo() {
                        alert(`Overall Incidents: Represents the total number of illegal wildlife trade cases across all locations and activities.
Transit: Refers to locations where wildlife is transported through but is neither the origin nor the final destination.
Origin: Identifies where illegal wildlife is sourced, often involving regions where poaching or harvesting occurs.
Destination: Highlights the final locations where illegally traded wildlife products are delivered and sold.
Seizure: Tracks instances where illegal wildlife or products are intercepted by authorities during transportation.`);
                    }
                    function showGranularityInfo() {
                        alert(`Countries: View IWT information aggregated at the country level, allowing for a broad overview of how illegal wildlife trade impacts different regions globally. This option highlights trends and patterns across entire nations.
Airports: View IWT information by individual airports, providing a detailed look at specific entry and exit points within countries. This granularity is ideal for analyzing trafficking routes and pinpointing key transit hubs.`);
                    }
                    function showIWTActivityInfo() {
                        alert(`Displays airport routes between countries, summing up all IWT activity records along each route. This provides a cumulative view of the total illegal wildlife trade activity occurring between specific country pairs.`);
                    }
                    function showNoIWTActivityInfo() {
                        alert(`Displays airport routes between countries where no IWT activity has been detected, summing up all relevant records along each route. This provides a cumulative view of the routes without any identified illegal wildlife trade activity between country pairs.`);
                    }
                    function showAirportIWTInfo() {
                        alert(`Displays all airport routes within the selected country, highlighting both routes with IWT volume and those without. This view allows for a detailed analysis of internal trafficking activity between airports in the chosen country.`);
                    }
                    </script>
                '''),
        ui.div(
            {"class": "iwt-info-container"},
            ui.HTML('<span class="info-bubble" onclick="showInfo()">ⓘ</span>'),
            ui.input_selectize(
                "metric", "IWT Information",
                choices=["Overall Incidents", "Transit", "Origin", "Destination", "Seizure"],
                selected="Overall Incidents"
            )
        ),
        ui.div(
            {"class": "granularity-info-container"},
            ui.HTML('<span class="info-bubble" onclick="showGranularityInfo()">ⓘ</span>'),
            ui.input_selectize(
                "loc2", "Location Granularity",
                choices=["Countries", "Airport"],
                selected="Countries"
            )
        ),
        ui.div(
            {"class": "checkbox-info-container"},
            ui.HTML('<span class="info-bubble" onclick="showIWTActivityInfo()">ⓘ</span>'),
            ui.input_checkbox("IWTcheckbox", "Show Flight Paths - IWT Activity", False)
        ),
        ui.div(
            {"class": "checkbox-info-container"},
            ui.HTML('<span class="info-bubble" onclick="showNoIWTActivityInfo()">ⓘ</span>'),
            ui.input_checkbox("NoIWTcheckbox", "Show Flight Paths - No IWT Activity", False)
        ),
        ui.div(
            {"class": "dropdown-info-container"},
            ui.HTML('<span class="info-bubble" onclick="showAirportIWTInfo()">ⓘ</span>'),
            ui.input_selectize(
                "country_search",
                ui.HTML("Show Flight Paths - <br>Airport-Based"),
                choices=country_names,
                selected=None,
                options={
                    'create': False,  # Prevents users from creating new entries
                    'placeholder': 'Type to search...',
                    'maxItems': 1  # Only allow one selection
                }
            )
        ),
        # Conditional panel that is displayed only when a country is selected
        ui.panel_conditional(
            "input.country_search != null && input.country_search != ''",
            ui.output_ui("airport_based_routing")
        ),
        ui.panel_conditional(
            "input.loc2 == 'Countries'",
            ui.output_ui("country_heat_map")
        ),
        ui.panel_conditional(
            "input.loc2 == 'Airport'",
            ui.output_ui("airport_markers")
        ),
        ui.panel_conditional(
            "input.checkbox == true",
            ui.output_ui("flight_paths")
        ),
        ui.input_dark_mode(),
        ),
    ui.card(
        ui.card_header("Map"),
        output_widget("map_widget")
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
    m.add(tile_layer)

    # Initialize the lines list
    hidden_markers_dict = {}
    lines = []
    route_markers = []
    lines_info = []
    draggable_markers = []
    # Initialize the draggable marker outside the loop
    draggable_marker = Marker(
        location=(0, 0),
        draggable=True,
        opacity=0,
        rise_on_hover=True,
        z_index_offset=10000
    )
    draggable_markers.append(draggable_marker)
    # Create a regular marker at the same spot with reduced opacity
    # Create and add a regular marker
    regular_marker = CircleMarker(
        location=(0, 0),
        opacity=0,
        rise_on_hover=True,
        z_index_offset=10000  # Increase the z-index offset
    )

    def update_tooltip(content):
        # Implement custom tooltip display logic here
        # For this example, we'll just print the tooltip
        # print(content)
        # print(regular_marker)
        regular_marker.title = content

    def get_closest_match(name, choices, cache):
        if name in cache:
            return cache[name]
        match = process.extractOne(name, choices)
        result = match[0] if match else None
        cache[name] = result
        return result

    def haversine(lat1, lon1, lat2, lon2):
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
            math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return 6371000 * c  # Radius of Earth in meters

    def distance_point_to_segment(point, segment):
        lat1, lon1 = segment[0]
        lat2, lon2 = segment[1]
        lat, lon = point
    # Event handler for map interactions
    def handle_map_interaction(event, **kwargs):
        event_type = kwargs.get('type')
        if event_type == 'mousemove':
            hover_coords = kwargs.get('coordinates')
            if draggable_marker.location != hover_coords:
                draggable_marker.location = hover_coords
                draggable_marker.opacity = 1

                closest_tooltip = None
                min_distance = float('inf')

                # Check which line is closest and update the tooltip text
                for line, tooltip in lines_info:
                    for segment in zip(line.locations[:-1], line.locations[1:]):
                        distance = distance_point_to_segment(hover_coords, segment)
                        if distance < min_distance:
                            min_distance = distance
                            closest_tooltip = tooltip

                if closest_tooltip:
                    update_tooltip(closest_tooltip)

        elif event_type == 'mouseout':
            draggable_marker.opacity = 0
            update_tooltip('')  # Clear the tooltip text

    def handle_map_hover(**kwargs):
        if kwargs.get('type') == 'mousemove':
            hover_coords = kwargs.get('coordinates')
            regular_marker.location = hover_coords
            regular_marker.opacity = 1

            closest_tooltip = None
            min_distance = float('inf')

            # Check which line is closest and update the marker's title accordingly
            for line, tooltip in lines_info:
                for segment in zip(line.locations[:-1], line.locations[1:]):
                    distance = distance_point_to_segment(hover_coords, segment)
                    if distance < min_distance:
                        min_distance = distance
                        closest_tooltip = tooltip

            if closest_tooltip:
                regular_marker.title = closest_tooltip

    def handle_map_leave(**kwargs):
        if kwargs.get('type') == 'mouseout':
            regular_marker.opacity = 0

    # Function to remove interaction handlers
    # Function to remove interaction handlers
    def remove_map_callbacks(map_obj):
        if hasattr(map_obj, 'on_interaction'):
            # Remove the specific interaction callback or clear all
            map_obj.on_interaction(None)


    def render_base_map():
        
        metric_mapping = {
            "Overall Incidents": "incident_counts",
            "Transit": "transit_count",
            "Origin": "origin_count",
            "Destination": "destination_count",
            "Seizure": "seizure_count"
        }
        print("Rendering base map...")
        
        selected_metric = metric_mapping.get(input.metric(), "incident_counts")
        print(f"Selected Metric is: {selected_metric}")

        active_marker = None


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

        # Recalculate colormap and mapping
        sorted_values = sorted(df[selected_metric].dropna(), reverse=True)
        third_highest = sorted_values[2] if len(sorted_values) > 2 else max(sorted_values)
        colormap = cm.LinearColormap(
            colors=['yellow', 'orange', 'red', 'darkred'],
            vmin=1,
            vmax=third_highest,
            caption=f'{input.metric()}'
        )
        colormap.text_color = "black"

        sorted_values = sorted(country_df[selected_metric].dropna(), reverse=True)
        third_highest_df = sorted_values[2] if len(sorted_values) > 2 else max(sorted_values)
        colormap_df = cm.LinearColormap(
            colors=['lightyellow', 'yellow', 'orange', 'red', 'darkred', 'brown'],
            vmin=1,
            vmax=third_highest_df,
            caption=f'{input.metric()}'
        )
        colormap_df.text_color = "black"

        # m = Map(center=(20, 0), zoom=2, basemap=basemaps.OpenStreetMap.Mapnik, scroll_wheel_zoom=True)

        # # Add a tile layer with English labels and no wrapping
        # tile_layer = TileLayer(
        #     url='https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
        #     attribution='&copy; <a href="https://carto.com/">Carto</a> contributors',
        # )
        # m.add(tile_layer)

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

    def reset_map():
        base_layer = m.layers[0]
        layers_to_remove = m.layers[1:]
        for layer in layers_to_remove:
            m.remove(layer)


            # # Add a dummy invisible choropleth layer just for the color scale
            # dummy_layer_df = L.Choropleth(
            #     geo_data=gdf.__geo_interface__,  # Use the same geo_data for proper min/max scaling
            #     choro_data=mapping,  # Use the country data for scaling
            #     colormap=colormap_df,
            #     value_min=1,
            #     value_max=third_highest_df,
            #     key_on='properties.name',
            #     style={'fillOpacity': 0},  # Make the layer invisible
            # )
            # m.add(dummy_layer_df)

            # # Add country colormap legend to the map using ColormapControl
            # colormap_control_df = ColormapControl(
            #     colormap=colormap_df,
            #     value_min=1,
            #     value_max=third_highest_df,
            #     caption="Country Incident Counts",
            #     position="topright"
            # )
            # m.add_control(colormap_control_df)

    @reactive.Effect
    def flight_paths_IWT():
        reset_map()
        if input.IWTcheckbox():
            # Attach the event handlers to the map
            hidden_markers_dict.clear()

            iata_to_country = dict(zip(df['IATA'], df['country']))
            iwt_df['Source_Country'] = iwt_df['Source'].map(iata_to_country)
            iwt_df['Target_Country'] = iwt_df['Target'].map(iata_to_country)
            iwt_df_filtered = iwt_df[iwt_df['Source_Country'] != iwt_df['Target_Country']]
            route_sums = iwt_df_filtered.groupby(['Source_Country', 'Target_Country']).agg(
                {'IWT_Volume': 'sum'}).reset_index()
            cache = {}

            for _, row in route_sums.iterrows():
                if row['IWT_Volume'] > 0:
                    source_country = get_closest_match(row['Source_Country'], map_config.keys(), cache)
                    target_country = get_closest_match(row['Target_Country'], map_config.keys(), cache)
                    if source_country and target_country:
                        source_coords = map_config.get(source_country)
                        target_coords = map_config.get(target_country)
                        color = 'red'
                        if source_coords and target_coords:
                            arrow = L.Polyline(
                                locations=[source_coords, target_coords],
                                color=color,
                                weight=1,
                                opacity=0.6
                            )
                            m.add(arrow)
                            tooltip = f"{source_country} -> {target_country} [{row['IWT_Volume']}]"
                                # print(tooltip)

                            if source_country in hidden_markers_dict:
                                # print("Marker exists at", source_coords)
                                hidden_marker = hidden_markers_dict[source_country]
                                final_tooltip = hidden_marker.title + f"\n" + tooltip
                                hidden_marker.title = final_tooltip
                            else:
                                # source_coords
                                source_hidden_marker = Marker(
                                    location=source_coords,
                                    opacity=0.5,  # Make the marker invisible,
                                    draggable=False,
                                    title=tooltip
                                )
                                m.add(source_hidden_marker)
                                hidden_markers_dict[source_country] = source_hidden_marker


                                # if regular_marker not in m.layers:
                                #     m.add(regular_marker)
                                #
                                # route_markers.append(circle_marker)
                                # route_markers.append(regular_marker)
                                lines.append(arrow)

                                m.on_interaction(handle_map_hover)
                                m.on_interaction(handle_map_leave)
        render_base_map()  # Ensure the base map is rendered after flight paths

    @reactive.Effect
    def flight_paths_no_IWT():
        reset_map()  # Clear previous layers
        base_layer = m.layers[0]
        layers_to_remove = m.layers[1:]
        for layer in layers_to_remove:
            m.remove(layer)

        if input.NoIWTcheckbox():
            # Attach the event handlers to the map
            m.on_interaction(handle_map_interaction)
            # Create a dictionary to map IATA codes to countries from the df dataframe
            iata_to_country = dict(zip(df['IATA'], df['country']))

            # Map the 'Source' IATA code to the corresponding country
            iwt_df['Source_Country'] = iwt_df['Source'].map(iata_to_country)

            # Map the 'Target' IATA code to the corresponding country
            iwt_df['Target_Country'] = iwt_df['Target'].map(iata_to_country)

            # Filter out rows where Source and Target countries are the same
            iwt_df_filtered = iwt_df[iwt_df['Source_Country'] != iwt_df['Target_Country']]

            # Group by 'Source_Country' and 'Target_Country' to sum the 'IWT_Volume' for each route
            route_sums = iwt_df_filtered.groupby(['Source_Country', 'Target_Country']).agg(
                {'IWT_Volume': 'sum'}).reset_index()

            # Create a dictionary to map (Source, Target) pairs to their rows in route_sums
            route_dict = {(row['Source_Country'], row['Target_Country']): row for _, row in route_sums.iterrows()}

            # Create a cache dictionary
            cache = {}

            # Process no IWT
            batch_size = 100
            for start in range(0, len(route_sums), batch_size):
                batch = route_sums.iloc[start:start + batch_size]
                for _, row in batch.iterrows():
                    #no IWT
                    if row['IWT_Volume'] == 0:
                        source_country = get_closest_match(row['Source_Country'], map_config.keys(), cache)
                        target_country = get_closest_match(row['Target_Country'], map_config.keys(), cache)
                        # print(source_country)
                        # print(target_country)
                        if source_country and target_country:
                            source_coords = map_config.get(source_country)
                            target_coords = map_config.get(target_country)

                            # Draw arrow for records with IWT_Volume > 0
                            color = 'gray'
                            if source_coords and target_coords:
                                arrow = L.Polyline(
                                    locations=[source_coords, target_coords],
                                    color=color,
                                    weight=1,
                                    opacity=0.3
                                )
                                # Store the line and its tooltip
                                m.add(arrow)

                                lines.append(arrow)

                                m.on_interaction(handle_map_hover)
                                m.on_interaction(handle_map_leave)

        render_base_map()  # Ensure the base map is rendered after no-flight paths

    @reactive.Effect
    def airport_based_routing():
        reset_map()  # Clear previous layers
        base_layer = m.layers[0]
        layers_to_remove = m.layers[1:]
        for layer in layers_to_remove:
            m.remove(layer)
        selected_country = input.country_search()

        # Step 1: Map IATA codes to countries using the existing `df` DataFrame
        iata_to_country = dict(zip(df['IATA'], df['country']))

        # Step 2: Filter for routes where both airports are in the same country
        same_country_routes = iwt_df[
            iwt_df.apply(
                lambda row: iata_to_country.get(row['Source'], "") == iata_to_country.get(row['Target'], ""),
                axis=1
            )
        ]

        route_cache = {}
        # Dictionary to store tooltips for each airport (so they don’t get mixed up)
        airport_tooltips = {}

        batch_size = 100
        for start in range(0, len(same_country_routes), batch_size):
            batch = same_country_routes.iloc[start:start + batch_size]
            for _, row in batch.iterrows():
                if row['IWT_Volume'] > 0 or row['IWT_Volume'] == 0:
                    source_country_match = get_closest_match(
                        iata_to_country.get(row['Source'], ""), map_config.keys(), route_cache
                    )
                    target_country_match = get_closest_match(
                        iata_to_country.get(row['Target'], ""), map_config.keys(), route_cache
                    )
                    df['IATA'] = df['IATA'].str.strip().str.upper()

                    if source_country_match == selected_country and target_country_match == selected_country:
                        source_code = row['Source']
                        target_code = row['Target']

                        source_coords = df.loc[df['IATA'] == source_code, ['latitude', 'longitude']]
                        target_coords = df.loc[df['IATA'] == target_code, ['latitude', 'longitude']]

                        if not source_coords.empty and not target_coords.empty:
                            source_coords = (source_coords['latitude'].values[0], source_coords['longitude'].values[0])
                            target_coords = (target_coords['latitude'].values[0], target_coords['longitude'].values[0])

                            color = 'red' if row['IWT_Volume'] > 0 else 'gray'
                            arrow = L.Polyline(
                                locations=[source_coords, target_coords],
                                color=color,
                                weight=3 if row['IWT_Volume'] > 0 else 1,
                                opacity=0.6
                            )
                            m.add(arrow)

                            if source_code not in airport_tooltips:
                                airport_tooltips[source_code] = []

                            airport_tooltips[source_code].append(
                                f"{source_code} -> {target_code} [{row['IWT_Volume']}]"
                            )

                            source_marker_tooltip = "\n".join(airport_tooltips[source_code])

                            source_marker = Marker(
                                location=source_coords,
                                opacity=0.5,
                                draggable=False,
                                title=source_marker_tooltip
                            )
                            m.add(source_marker)

                elif row['IWT_Volume'] == 0:
                    # Get the country match for both the source and target airports
                    source_country_match = get_closest_match(
                        iata_to_country.get(row['Source'], ""), map_config.keys(), route_cache
                    )
                    target_country_match = get_closest_match(
                        iata_to_country.get(row['Target'], ""), map_config.keys(), route_cache
                    )
                    df['IATA'] = df['IATA'].str.strip().str.upper()
                    # Check if both airports match the selected country
                    if source_country_match == selected_country and target_country_match == selected_country:
                        # Process the row if it matches the selected country
                        # print(f"Matching route: {row['Source']} -> {row['Target']} with IWT_Volume: {row['IWT_Volume']}")
                        source_code = row['Source']
                        target_code = row['Target']
                        print(f"source_code: {source_code}")
                        print(f"target_code: {target_code}")
                        # Initialize the coordinates to None
                        source_coords = None
                        target_coords = None

                        # Perform the lookup using .loc[]
                        source_coords = (df.loc[df['IATA'] == source_code, 'latitude'].values[0],
                                         df.loc[df['IATA'] == source_code, 'longitude'].values[0])
                        target_coords = (df.loc[df['IATA'] == target_code, 'latitude'].values[0],
                                         df.loc[df['IATA'] == target_code, 'longitude'].values[0])
                        print(f"source_coords: {source_coords}")
                        print(f"target_coords: {target_coords}")
                        if isinstance(source_coords, tuple) and isinstance(target_coords, tuple) and len(
                                source_coords) == 2 and len(target_coords) == 2:
                            print("Coordinates are valid")

                        if source_coords and target_coords:
                            # Draw the line for this route
                            color = 'gray'
                            arrow = L.Polyline(
                                locations=[source_coords, target_coords],
                                color=color,
                                weight=1,
                                opacity=0.6
                            )
                            m.add(arrow)

                            # Ensure the marker for the source airport is updated with relevant tooltips
                            if source_code not in airport_tooltips:
                                airport_tooltips[source_code] = []

                            # Add the route to the tooltip for the source airport
                            airport_tooltips[source_code].append(
                                f"{source_code} -> {target_code} [{row['IWT_Volume']}]")

                            # Update the marker for the source airport
                            source_marker_tooltip = "\n".join(airport_tooltips[source_code])

                            # Add or update the marker with the new tooltip
                            source_marker = Marker(
                                location=source_coords,
                                opacity=0.5,
                                draggable=False,
                                title=source_marker_tooltip
                            )
                            m.add(source_marker)
        render_base_map()  # Ensure the base map is rendered after routing paths

    @output
    @render_widget
    def map_widget():
        return m

app = App(app_ui, server)

if __name__ == "__main__":
    logger.info("Starting the app")
    app.run()

