#🧱 Étape 1 : charger tes données dans l’app

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import requests
import json

model = joblib.load("model_rf.pkl")

st.title("⛽ Smart Fuel")
st.write("Trouvez la station la moins chère autour de vous")


#####################################################################

# Chargement des données instantanées mises à jour toutes les 10 minutes

#####################################################################

  # mise à jour toutes les 10 min
  
  #  "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/exports/json"

@st.cache_data(ttl=600)
def load_api_data():
    url = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/prix-des-carburants-en-france-flux-instantane-v2/exports/json"    
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            # ✅ CAS 1 : dict avec "results"
            if isinstance(data, dict) and 'results' in data:
                return pd.json_normalize(data['results'])
            
            # ✅ CAS 2 : liste directe
            elif isinstance(data, list):
                return pd.json_normalize(data)
            
            else:
                st.error("Format API inconnu")
                return None
        
        else:
            st.error(f"Erreur API: {response.status_code}")
            return None
    
    except Exception as e:
        st.error(f"Erreur connexion API: {e}")
        return None

data_api = load_api_data()

# Chargement des données quotidiennes

#@st.cache_data
#def load_data():
    #return pd.read_csv("prix-carburants-quotidien.csv", sep = ";")

#data = load_data()

# choix des données 
#if data_api is not None:
    #data = data_api
#else:
    #st.error("Erreur API, utilisation des données locales")
    #data = load_data()

#source = st.radio("Source des données", ["Fichier local", "Temps réel API"])

#if source == "Temps réel API":
 #   data = data_api()
#else:
    #data = load_data()
    
 ##################################################################################
 
 # Etape 2 Gestion et nettoyage des colonnes
 
 ########################################################################################
 
df = data_api.copy()

def safe_parse(x):
    try:
        # si string → parser
        if isinstance(x, str):
            x = json.loads(x)
            
            # garder seulement les listes valides
        if isinstance(x, list):
            return x
        else:
            return None
               
    except:
        return None

    # 🔥 nettoyage

df.columns = (
    df.columns
      .str.strip()
      .str.lower()
      .str.replace(" ", "_")
)

df['prix'] = df['prix'].apply(safe_parse)

    # supprimer lignes invalides
df = df.dropna(subset=['prix'])

    # exploser
df = df.explode('prix')

    # 🔥 garder seulement les dicts
df = df[df['prix'].apply(lambda x: isinstance(x, dict))]

    # normaliser
prix_df = pd.json_normalize(df['prix'])

df = df.reset_index(drop=True)
prix_df = prix_df.reset_index(drop=True)

df = pd.concat([df, prix_df], axis=1)

    # renommer
df = df.rename(columns={
        '@nom': 'Carburant',
        '@valeur': 'Prix',
        '@maj': 'date'
    })

 # coordonnées
     
if 'geom.lat' in df.columns:
    df = df.rename(columns={'geom.lat': 'Latitude'})
    
if 'geom.lon' in df.columns:
    df = df.rename(columns={'geom.lon': 'Longitude'})

    # Conversion types
df['Prix'] = pd.to_numeric(df['Prix'], errors='coerce')
df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # Harmonisation des colonnes "ville et adresse"
    
df['adresse'] = df['adresse'].str.lower()
df['adresse'] = df['adresse'].str.title()
df["ville"] = df["ville"].str.lower() 
df["ville"] = df["ville"].str.title() 

     # Supprimer valeurs nulles importantes
df = df.dropna(subset=["Carburant",'Prix', 'Latitude', 'Longitude'])

data = df 

if 'geom' in data.columns:
    data[['Latitude', 'Longitude']] = data['geom'].str.split(',', expand=True)
    data['Latitude'] = data['Latitude'].str.strip().astype(float)
    data['Longitude'] = data['Longitude'].str.strip().astype(float)

#st.write(data[['date', 'Carburant', 'Prix', 'Latitude', 'Longitude' ]].head())    

# ⛽ Étape 3 : filtre carburant (INTERACTIF)

carburant = st.selectbox(
    "Choisissez un carburant",
    data['Carburant'].unique()
)

data = data[data['Carburant'] == carburant]

#####################################################################################################

# Etape intermédiaure KPI

####################################################################################################
st.write("KPI")

col1, col2, col3, col4, col5 = st.columns(5)

prix_moyen = data['Prix'].mean()
prix_min = data['Prix'].min()
prix_max = data['Prix'].max()
volatilite_prix = data['Prix'].std()
nb_stations = data['id'].nunique()

col1.metric("💰 Prix moyen", f"{prix_moyen:.2f} €")
col2.metric("📉 Prix min", f"{prix_min:.2f} €")
col3.metric("📈 Prix max", f"{prix_max:.2f} €")
col4.metric("📉 Volatilité des prix", f"{volatilite_prix:.2f} €")
col5.metric("⛽ Stations", nb_stations)

# 📍 Étape 4 : localisation utilisateur

st.sidebar.header("📍 Votre position")

user_lat = st.sidebar.number_input("Latitude", value=48.85)
user_lon = st.sidebar.number_input("Longitude", value=2.35)

rayon = st.sidebar.slider("Rayon (km)", 1, 50, 10)



# 📏 Étape 5 : fonction distance

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    c = 2*np.arcsin(np.sqrt(a))
    
    return R * c
    
 # 🎯 Étape 6 : calcul + filtre
  
data['distance_km'] = data.apply(
    lambda row: haversine(user_lat, user_lon, row['Latitude'], row['Longitude']),
    axis=1
)

stations_proches = data[data['distance_km'] <= rayon]

# 💰 Étape 7 : recommandation

stations_reco = stations_proches.sort_values('Prix').head(10)

st.subheader("🏆 Stations recommandées")

st.dataframe(
    stations_reco[['adresse', 'ville', 'Prix', 'distance_km']]
)

# 🗺️ Étape 8 : carte (WAOUH effect)

st.subheader("📍 Carte des stations")

st.map(
    stations_reco.rename(columns={
        'Latitude': 'lat',
        'Longitude': 'lon'
    })[['lat', 'lon']]
)


#####################################################################

# Machine Learning 

#######################################################################

# 🧠 1) Intégration du modèle ML (prix “demain”) dans l'app
# 🔧 Création des features

data['jour_semaine'] = data['date'].dt.dayofweek
data['mois'] = data['date'].dt.month
data['jour'] = data['date'].dt.day
data["prix_jour_avant"] = data.groupby("id")["Prix"].shift(1)

#  features pour les stations proches 
stations_proches['jour_semaine'] = data['date'].dt.dayofweek
stations_proches['mois'] = data['date'].dt.month
stations_proches['jour'] = data['date'].dt.day
stations_proches["prix_jour_avant"] = stations_proches.groupby("id")["Prix"].shift(1)

# 🔮 Prédiction

features = ['jour_semaine', 'mois', 'jour', 'prix_jour_avant']

data['prix_predit'] = model.predict(data[features])

#  prédiction pour les stations proches 

stations_proches['prix_predit'] = model.predict(stations_proches[features])

# 📊 Affichage

st.subheader("🔮 Prix prédit")

st.dataframe(
   stations_proches[['adresse', 'ville', 'Prix', 'prix_predit', 'distance_km']]
)

# 💡 2) Score intelligent 

# 🧮 Score simple

stations_proches['score'] = (
    stations_proches['Prix'] * 0.6 +
    stations_proches['distance_km'] * 0.4
)

# 🚀 Version avancée (🔥)

stations_proches['score'] = (
    stations_proches['prix_predit'] * 0.5 +
    stations_proches['Prix'] * 0.3 +
    stations_proches['distance_km'] * 0.2
)


# 🎯 Recommandation finale

stations_reco = stations_proches.sort_values('score').head(10)

# 🎨 3) Amélioration UX

# 🎯 Ajout des KPIs en haut

col1, col2, col3 = st.columns(3)

col1.metric("💰 Prix moyen", round(stations_proches['Prix'].mean(), 2))
col2.metric("📍 Stations trouvées", len(stations_proches))
col3.metric("🚗 Distance moyenne", round(stations_proches['distance_km'].mean(), 2))

# 🎛️ Ajout d'un filtre de prix

prix_max = st.slider("Prix max (€)", 1.0, 3.0, 2.0)

stations_proches = stations_proches[stations_proches['Prix'] <= prix_max]

# 📊 Graphique
import plotly.express as px

fig = px.scatter(
    stations_proches,
    x="distance_km",
    y="Prix",
    color="prix_predit",
    title="Prix actuel vs prédit"
)

st.plotly_chart(fig)
 
# 🎯 Message intelligent

best = stations_reco.iloc[0]

st.success(
    f"🏆 Meilleure option : {best['ville']} à {round(best['Prix'],2)}€ "
    f"à {round(best['distance_km'],1)} km"
)

# Géolocalisation Automatique

from streamlit_js_eval import get_geolocation

st.sidebar.header("📍 Votre position")

location = get_geolocation()

if location:
    user_lat = location['coords']['latitude']
    user_lon = location['coords']['longitude']
    
    st.sidebar.success("Position détectée ✅")
    st.sidebar.write(f"Lat: {user_lat:.4f}, Lon: {user_lon:.4f}")
else:
    st.sidebar.warning("Autorisez la géolocalisation")
    user_lat = st.sidebar.number_input("Latitude", value=48.85)
    user_lon = st.sidebar.number_input("Longitude", value=2.35)

# 🗺️ Carte interactive avancée

import folium
from streamlit_folium import st_folium

# centre carte
map_center = [user_lat, user_lon]

m = folium.Map(location=map_center, zoom_start=12)

# point utilisateur
folium.Marker(
    [user_lat, user_lon],
    tooltip="Vous êtes ici",
    icon=folium.Icon(color="blue")
).add_to(m)

# Couleur sélon le prix 

def get_color(price):
    if price < 1.8:
        return "green"
    elif price < 2:
        return "orange"
    else:
        return "red"
        
#icon=folium.Icon(color=get_color(row['Prix'])) 

# stations
for _, row in stations_reco.iterrows():
    folium.Marker(
        [row['Latitude'], row['Longitude']],
        popup=f"{row['Carburant']} : {row['Prix']}€",
        icon=folium.Icon(color=get_color(row['Prix']))     
        #icon=folium.Icon(color="green")
    ).add_to(m)

st_folium(m, width=700, height=500)


# 🎨 Mise en page

st.set_page_config(layout="wide")

# 📊 Organisation en colonnes

#col1, col2 = st.columns([1, 2])

#with col1:
 #   st.write("Filtres / KPI")

#with col2:
 #   st.write("Carte")
    
   # 📊 KPI stylés
   
#col1, col2, col3 = st.columns(3)

#col1.metric("💰 Prix moyen", f"{prix_moyen:.2f}€")
#col2.metric("📍 Stations", len(stations_proches))
#col3.metric("🚗 Distance moyenne", f"{stations_proches['distance_km'].mean():.1f} km")

# 🎯 UX 

#st.markdown("## ⛽ Recommandation intelligente")

#st.success("🏆 Meilleure station trouvée")

#st.write(stations_proches[['Prix', 'prix_predit', 'distance_km', 'score']].head())