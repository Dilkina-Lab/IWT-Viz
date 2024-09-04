import pandas as pd

# Load the airport data
df = pd.read_csv('airport_features.csv')


# Filter out airports with no incident counts
df_filtered = df[df['incident_counts'] > 0]

# Save the filtered data to a new CSV file
filtered_output_file = 'filtered_airport_features.csv'
df_filtered.to_csv(filtered_output_file, index=False)


# Group the data by country and sum the counts for each metric
country_aggregated = df.groupby('country').agg({
    'origin_count': 'sum',
    'transit_count': 'sum',
    'destination_count': 'sum',
    'seizure_count': 'sum',
    'incident_counts': 'sum'
}).reset_index()

# Calculate additional metrics if needed
# (e.g., total incidents per country or any custom metric)
# For example, you can add a metric that sums up all incidents:
country_aggregated['total_incidents'] = country_aggregated[
    ['origin_count', 'transit_count', 'destination_count', 'seizure_count']
].sum(axis=1)

# Save the aggregated data to a new CSV file
output_file = 'country_aggregated_data.csv'
country_aggregated.to_csv(output_file, index=False)

print(f"Aggregated data saved to {output_file}")
