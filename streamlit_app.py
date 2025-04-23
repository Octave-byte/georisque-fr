import streamlit as st
import pandas as pd
import requests
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import folium
from streamlit_folium import st_folium

# --- Load INSEE reference file ---

@st.cache_data
def load_geo_df():
    df = pd.read_csv("data/insee_lat_lon.csv")
    df[['latitude', 'longitude']] = df['_geopoint'].str.split(",", expand=True).astype(float)
    df['code_commune_insee'] = df['code_commune_insee'].astype(str).str.zfill(5)
    return df

# --- GeoRisques API request ---
def get_georisques_risks(lat, lon, radius, cat):
    base_url = "https://georisques.gouv.fr/api/v1/gaspar/"
    latlon = f"{lon},{lat}"  # Required format: lon,lat
    url = f"{base_url}{cat}"
    params = {"latlon": latlon, "rayon": radius}
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()['data']
    return []

# --- Geocode address ---
def geocode_address(address):
    geolocator = Nominatim(user_agent="geo_risk_app", timeout=5)
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        st.warning("Geocoding service is currently unavailable or too slow. Please try again later.")
        return None, None

# --- UI ---
st.title("📍 Know Your Risk – GeoRisques Explorer")

address = st.text_input("Enter an address in France:")
radius = st.slider("Search radius (meters):", 100, 5000, 1000)

if address:
    lat, lon = geocode_address(address)
    if lat and lon:
        st.success(f"Found location: {lat}, {lon}")
        
        st.markdown("### Retrieving risks from GeoRisques...")
        data = get_georisques_risks(lat, lon, radius, 'catnat')

        if data:
            df_filtered = pd.DataFrame(data)[['code_insee', 'date_fin_evt', 'libelle_risque_jo']]
            df_filtered['code_insee'] = df_filtered['code_insee'].astype(str).str.zfill(5)
            df_geo = load_geo_df()

            df_merged = df_filtered.merge(
                df_geo,
                left_on="code_insee",
                right_on="code_commune_insee",
                how="left"
            )

            st.markdown("### Map of Historical Risks")

            # Create Folium map
            m = folium.Map(location=[lat, lon], zoom_start=12)

            # Add central point
            folium.Marker([lat, lon], popup="Your location", icon=folium.Icon(color='blue')).add_to(m)

            # Define color map
            risk_colors = {
                "Inondations et/ou Coulées de Boue": "darkred",
                "Mouvements de terrain": "orange",
                "Séisme": "green",
                "Feux de forêt": "purple",
                # add more if needed
            }

            for _, row in df_merged.iterrows():
                if pd.notnull(row['latitude']) and pd.notnull(row['longitude']):
                    color = risk_colors.get(row['libelle_risque_jo'], "gray")
                    popup = f"{row['libelle_risque_jo']}<br>{row['date_fin_evt']}"
                    folium.Marker(
                        [row['latitude'], row['longitude']],
                        popup=popup,
                        icon=folium.Icon(color=color)
                    ).add_to(m)

            st_data = st_folium(m, width=700, height=500)
            st.markdown("### 📋 List of Historical Catastrophes")
            st.dataframe(df_merged[['date_fin_evt', 'libelle_risque_jo']].sort_values('date_fin_evt'),use_container_width=True) 

        else:
            st.warning("No historical risk data found for this area.")
    else:
        st.error("Couldn't geocode the address. Please try again.")