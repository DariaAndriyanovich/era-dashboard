import streamlit as st
import pandas as pd
import plotly.express as px
import ssl

    ### ANDMED ###
ssl._create_default_https_context = ssl._create_unverified_context

st.title("ERA Photo Archive Dashboard")

sheet_id = "1GykaR1SEL2AmzUuXZadVmiL3kpM_MEf2"
gid = "153293957"

url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
df = pd.read_csv(url)

df.columns = df.columns.str.strip()

df["Aasta"] = pd.to_numeric(df["Aasta"], errors="coerce")
df = df.dropna(subset=["Aasta"])
df["Aasta"] = df["Aasta"].astype(int)

    #### SIDE BAR ###
st.sidebar.header("Filtrid")

# FILTRITE EEMALDAMINE
if st.sidebar.button("Eemalda kõik filtrid"):
    st.session_state["year_range"] = (
        int(df["Aasta"].min()),
        int(df["Aasta"].max())
    )
    st.session_state["kihelkond_filter"] = []
    st.session_state["asukoht_filter"] = []
    st.rerun()

# AASTA SIDEBAR
year_range = st.sidebar.slider(
    "Aasta",
    int(df["Aasta"].min()),
    int(df["Aasta"].max()),
    (int(df["Aasta"].min()), int(df["Aasta"].max())),
    key="year_range"
)

df = df[(df["Aasta"] >= year_range[0]) & (df["Aasta"] <= year_range[1])]

# KIHELKOND SIDEBAR
selected = st.sidebar.multiselect(
    "Kihelkond",
    sorted(df["Kihelkond"].dropna().unique()),
    key="kihelkond_filter"
)

if selected:
    df = df[df["Kihelkond"].isin(selected)]

col1, col2, col3 = st.columns(3)

col1.metric("Fotode arv", len(df))
col2.metric("Kihelkondi", df["Kihelkond"].nunique())
col3.metric("Asukohti", df["Koht täpsemalt"].nunique())

# ASUKOHT SIDEBAR
selected_places = st.sidebar.multiselect(
    "Täpne asukoht",
    sorted(df["Koht täpsemalt"].dropna().unique()),
    key="asukoht_filter"
)

if selected_places:
    df = df[df["Koht täpsemalt"].isin(selected_places)]

    #### KUJUTATUD ANDMED ###

st.markdown("---")
# FOTODE JAOTUS AJAS
st.subheader("Fotode jaotus ajas")

timeline = df.groupby("Aasta").size().reset_index(name="count")
fig = px.line(timeline, x="Aasta", y="count")
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
# KIHELKONDADE JAOTUS
st.subheader("Kõige esindatumad kihelkonnad")

top = (
    df["Kihelkond"]
    .value_counts()
    .head(10)
    .reset_index()
)

top.columns = ["Kihelkond", "Arv"]

fig2 = px.bar(
    top,
    x="Kihelkond",
    y="Arv",
    color="Arv",
    color_continuous_scale="Blues"
)

fig2.update_layout(coloraxis_showscale=False)

st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")
# ASUKOHTADE JAOTUS
st.subheader("Kõige sagedasemad asukohad")

top_places = (        #
    df["Koht täpsemalt"]
    .dropna()
    .value_counts()
    .head(10)
    .reset_index()
)

top_places.columns = ["Täpne asukoht", "Fotode arv"]

fig3 = px.bar(
    top_places,
    x="Täpne asukoht",
    y="Fotode arv",
    color="Fotode arv",
    color_continuous_scale="Greens"
)

fig3.update_layout(coloraxis_showscale=False)

st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")

# ANDMETE TABEL CSV KUJUL
st.subheader("Andmed")

st.dataframe(df.head(20), use_container_width=True)

st.markdown("---")
# KAART v1
#st.header(" Fotode kaart")

#sheet_id = "1GykaR1SEL2AmzUuXZadVmiL3kpM_MEf2"
#gid_map = "895258900"

#url_map = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_map}"

#df_map = pd.read_csv(url_map)

#df_map.columns = df_map.columns.str.strip()

#map_data = df_map[["Latitude", "Longitude"]].dropna()

#map_data = map_data.rename(columns={
#    "Latitude": "lat",
#    "Longitude": "lon"
#})

#st.map(map_data)

# UUS KAART

st.header("Fotode kaart")


gid_map = "895258900"

url_map = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid_map}"
df_map = pd.read_csv(url_map)

df_map.columns = df_map.columns.str.strip()

df_map = df_map.dropna(subset=["Latitude", "Longitude"])

# KAART - AASTA FILTER
df_map = df_map[
    (df_map["Aasta"] >= year_range[0]) &
    (df_map["Aasta"] <= year_range[1])
]
# KAART - KIHELKOND FILTER
if selected:
    df_map = df_map[df_map["Kihelkond"].isin(selected)]

# KAART - ASUKOHT FILTER
if selected_places:
    df_map = df_map[df_map["Koht täpsemalt"].isin(selected_places)]

# KAART - ANDMED JA KUJUTUS
map_counts = (
    df_map
    .groupby(["Latitude", "Longitude", "Kihelkond", "Koht täpsemalt"])
    .size()
    .reset_index(name="count")
)

fig_map = px.scatter_mapbox(
    map_counts,
    lat="Latitude",
    lon="Longitude",
    size="count",
    hover_data={
        "Kihelkond": True,
        "Koht täpsemalt": True,
        "count": True,
        "Latitude": False,
        "Longitude": False,
    },
    labels={
        "Kihelkond": "Kihelkond",
        "Koht täpsemalt": "Täpne asukoht",
        "count": "Fotode arv",
    },
    zoom=6,
    height=500
)

fig_map.update_layout(
    mapbox_style="carto-darkmatter",
    margin={"r": 0, "t": 0, "l": 0, "b": 0}
)

st.plotly_chart(fig_map, use_container_width=True)

# KAART - KAARDISTATUD INFO TÄPSUSTUS
st.caption(f"Tabelis fotosid (kokku): {len(df)}")
st.caption(f"Kaardil fotosid (koordinaatidega): {len(df_map)}")
