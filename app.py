import streamlit as st
import pandas as pd
import plotly.express as px
import ssl
import json

### LEHE STIIL JA SEADISTUSED ###
st.set_page_config(
    page_title="ERA Dashboard",
    layout="wide"
)

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

h1, h2, h3 {
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

px.defaults.template = "plotly_white"

st.markdown("""
<style>

.stTabs [data-baseweb="tab-list"] {
    display: flex;
    justify-content: space-between;
    width: 100%;
}

.stTabs [data-baseweb="tab"] {
    font-size: 16px;
    font-weight: 600;
}

</style>
""", unsafe_allow_html=True)

### TABIDE LOOMINE ###

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Ajaline analüüs",
    "Kaart",
    "Märksõnad",
    "ML analüüs",
    "Andmed"

])

with tab1:

  ### ANDMED ###
  ssl._create_default_https_context = ssl._create_unverified_context

  st.title("ERA Photo Archive Dashboard")

  df = pd.read_excel(
      "ERA_fotod_250426.xlsx",
      sheet_name="fotod_koordinaatidega"
  )

  df.columns = df.columns.str.strip()

  master = pd.read_excel(
      "ERA_fotod_250426.xlsx",
      sheet_name="fotod_master"
  )

  master.columns = master.columns.str.strip()

  df["PID"] = df["PID"].astype(str).str.strip()
  master["PID"] = master["PID"].astype(str).str.strip()

  master_small = master[["PID", "Aasta"]].drop_duplicates(subset=["PID"])

  df = df.drop(columns=["Aasta"], errors="ignore")

  df = df.merge(master_small, on="PID", how="left")

  df = df.drop_duplicates()

  df["Aasta"] = pd.to_numeric(df["Aasta"], errors="coerce")

  df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
  df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

  df["koordinaadid_leitud"] = (
      df["Latitude"].notna() &
      df["Longitude"].notna()
  )

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

#AASTA SIDEBAR
  year_min = int(df["Aasta"].dropna().min())
  year_max = int(df["Aasta"].dropna().max())

  year_range = st.sidebar.slider(
      "Aasta",
      year_min,
      year_max,
      (year_min, year_max),
      key="year_range"
  )

  df = df[
      (
          (df["Aasta"] >= year_range[0]) &
          (df["Aasta"] <= year_range[1])
      )
      |
      (df["Aasta"].isna())
  ]
#MÄRKSÕNADE SIDEBAR
  all_keywords = (
      master["ERA märksõnad (koondatud)"]
      .dropna()
      .astype(str)
      .str.split(",")
      .explode()
      .str.strip()
  )

  unique_keywords = sorted(all_keywords.unique())

  search_keyword = st.sidebar.text_input("Otsi märksõna")

  if search_keyword:
      filtered_keyword_options = [
          kw for kw in unique_keywords
          if search_keyword.lower() in kw.lower()
      ]
  else:
      filtered_keyword_options = unique_keywords

  selected_keywords = st.sidebar.multiselect(
      "Vali märksõnad",
      filtered_keyword_options
  )

# KIHELKOND SIDEBAR
  selected = st.sidebar.multiselect(
      "Kihelkond",
      sorted(df["Kihelkond"].dropna().astype(str).unique()),
      key="kihelkond_filter"
  )

  if selected:
      df = df[df["Kihelkond"].isin(selected)]

#KPI
  k1, k2, k3, k4, k5 = st.columns(5)

  k1.metric(
      " Fotode arv",
      f"{len(df):,}"
  )

  k2.metric(
      " Kihelkondi",
      df["Kihelkond"].nunique()
  )

  k3.metric(
      " Asukohti",
      df["Koht täpsemalt"].nunique()
  )

  k4.metric(
      " Ajavahemik",
      f"{int(df['Aasta'].min())}–{int(df['Aasta'].max())}"
  )

  k5.metric(
      " Koordinaatidega",
      f"{df['koordinaadid_leitud'].sum():,}"
  )

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

  #KIHELKONDADE JAOTUS AJAS
  st.markdown("---")
  st.subheader("Kihelkonnad ajas")

  top_kihelkonnad_time = (
      df["Kihelkond"]
      .dropna()
      .value_counts()
      .head(5)
      .index
  )

  df_time = df[df["Kihelkond"].isin(top_kihelkonnad_time)]

  df_time_grouped = (
      df_time
      .groupby(["Aasta", "Kihelkond"])
      .size()
      .reset_index(name="Fotode arv")
  )

  fig_time = px.line(
      df_time_grouped,
      x="Aasta",
      y="Fotode arv",
      color="Kihelkond",
      markers=True
  )

  st.plotly_chart(fig_time, use_container_width=True)

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


  #VÕRDLUS KIHELKONDADE VAHEL
  st.markdown("---")
  st.subheader("Võrdlus kahe kihelkonna vahel")

  valik = st.multiselect("Vali kuni 2 kihelkonda", df["Kihelkond"].unique())

  if len(valik) == 2:
      df_compare = df[df["Kihelkond"].isin(valik)]

      comp = (
          df_compare.groupby(["Aasta", "Kihelkond"])
          .size()
          .reset_index(name="Arv")
      )

      fig = px.line(comp, x="Aasta", y="Arv", color="Kihelkond")
      st.plotly_chart(fig)

# GEOJSON - KIHELKONNA PIIRID
with open("data/areas.geojson", "r", encoding="utf-8") as f:
    geojson_data = json.load(f)

with tab2:
  # UUS KAART
  st.header("Fotode kaart")

  df_map = pd.read_excel(
      "ERA_fotod_250426.xlsx",
      sheet_name="fotod_koordinaatidega"
  )
  df_map.columns = df_map.columns.str.strip()

  df_map = df_map.dropna(subset=["Latitude", "Longitude"])

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
  # KIHELKONDADE KOKKUVÕTE POLÜGOONIDE JAOKS
  polygon_counts = (
      df_map
      .groupby("Kihelkond")
      .size()
      .reset_index(name="Fotode arv")
  )

  fig_map = px.choropleth_mapbox(
      polygon_counts,
      geojson=geojson_data,
      locations="Kihelkond",
      featureidkey="properties.KIHELKOND",
      color="Fotode arv",
      color_continuous_scale="Viridis",
      mapbox_style="carto-positron",
      zoom=6.4,
      center={"lat": 58.7, "lon": 25.0},
      opacity=0.5,
      height=650,
      hover_name="Kihelkond",
      hover_data={"Fotode arv": True}
  )

  fig_points = px.scatter_mapbox(
      map_counts,
      lat="Latitude",
      lon="Longitude",
      size="count",
      hover_name="Kihelkond",
      hover_data={
          "Koht täpsemalt": True,
          "count": False,
          "Latitude": False,
          "Longitude": False,
      },
      custom_data=["Koht täpsemalt", "count"],
      size_max=20,
      color_discrete_sequence=["#EDF85B"]
  )

  for trace in fig_points.data:
      trace.hovertemplate = (
        "<b>%{hovertext}</b><br>"
        "Asukoht: %{customdata[0]}<br>"
        "Fotode arv: %{customdata[1]}<extra></extra>"
      )

      fig_map.add_trace(trace)

  fig_map.update_traces(marker=dict(opacity=0.55), selector=dict(type="scattermapbox"))

  fig_map.update_layout(
      mapbox_style="carto-positron",
      margin={"r": 0, "t": 0, "l": 0, "b": 0},
      coloraxis_colorbar=dict(
            title="",
            thickness=12,
            len=0.5
      )
  )

  st.plotly_chart(fig_map, use_container_width=True)

  # KAART - KAARDISTATUD INFO TÄPSUSTUS
  st.caption(f"Tabelis fotosid (kokku): {len(df)}")
  st.caption(f"Kaardil fotosid (koordinaatidega): {len(df_map)}")

with tab3:
  #MÄRKSÕNAD
  st.header("Kõige sagedasemad märksõnad")
  st.caption("ERA fotoarhiivi enim kasutatud märksõnad")

  filtered_pids = df["PID"].astype(str).str.strip().unique()

  master_filtered = master[
      master["PID"].astype(str).str.strip().isin(filtered_pids)
  ].copy()

  keywords_series = (
        master_filtered["ERA märksõnad (koondatud)"]
        .dropna()
        .astype(str)
        .str.split(",")
        .explode()
        .str.strip()
    )

  if selected_keywords:
      keywords = keywords_series[keywords_series.isin(selected_keywords)]
  elif search_keyword:
      keywords = keywords_series[
          keywords_series.str.contains(search_keyword, case=False, na=False)
      ]
  else:
      keywords = keywords_series

  keyword_counts = keywords.value_counts().head(80)

#KPI
  k1, k2, k3 = st.columns(3)

  k1.metric(
      "Märksõnu kokku",
      f"{len(keywords):,}"
  )

  k2.metric(
      "Unikaalseid märksõnu",
      f"{keywords.nunique():,}"
  )

  k3.metric(
      "Kõige sagedasem",
      keyword_counts.index[0] if not keyword_counts.empty else "-"
  )

  if keywords.empty:
      st.warning("Valitud filtritega sobivaid märksõnu ei leitud.")
      st.stop()

#BUBBLE CHART
  bubble_df = keyword_counts.reset_index()
  bubble_df.columns = ["keyword", "count"]

  fig_bubble = px.scatter(
      bubble_df,
      x="keyword",
      y="count",
      size="count",
      color="count",
      hover_name="keyword",
      size_max=70,
      height=700,
      color_continuous_scale="Teal"
  )

  fig_bubble.update_layout(
      xaxis_title="Märksõna",
      yaxis_title="Fotode arv",
      showlegend=False
  )

  st.plotly_chart(fig_bubble, use_container_width=True)
#TOP 15
  st.markdown("---")
  st.markdown("### TOP 15 märksõna")

  top15 = keyword_counts.head(15).reset_index()
  top15.columns = ["Märksõna", "Fotode arv"]

  fig_top = px.bar(
      top15,
      x="Fotode arv",
      y="Märksõna",
      orientation="h",
      color="Fotode arv",
      color_continuous_scale="Tealgrn"
  )
  fig_top.update_traces(marker_line_width=0)

  fig_top.update_layout(
      yaxis=dict(categoryorder="total ascending"),
      plot_bgcolor="rgba(0,0,0,0)",
      paper_bgcolor="rgba(0,0,0,0)",
      coloraxis_showscale=False
  )

  st.plotly_chart(
      fig_top,
      use_container_width=True,
      config={"displayModeBar": False}
  )

  st.caption(
      f"Kõige sagedasem märksõna on '{keyword_counts.index[0]}', "
      f"mida esineb {keyword_counts.iloc[0]} korda."
  )
with tab5:
  # ANDMETE TABEL CSV KUJUL
  st.markdown("---")
  st.subheader("Andmed")

  st.dataframe(df.head(20), use_container_width=True)

  # ANDMETE KVALITEET
  st.markdown("---")
  st.subheader("Andmete kvaliteet")

  total = len(df)
  with_coords = len(df_map)

  col1, col2, col3 = st.columns(3)

  col1.metric("Kõik fotod", total)
  col2.metric("Koordinaatidega fotod", with_coords)
  col3.metric("Puuduvad koordinaadid", total - with_coords)

  percent = round((with_coords / total) * 100, 1)

  st.markdown(f"Kaardil kuvatakse **{percent}%** kõikidest fotodest.")

  if percent < 50:
      st.warning(" Suur osa andmetest ei sisalda koordinaate.")
  else:
      st.success(" Andmestik sobib hästi kaardipõhiseks analüüsiks.")

  # PUUDUVAD ANDMED
  st.markdown("---")
  st.subheader("Puuduvad andmed")

  missing = df.isnull().sum().reset_index()
  missing.columns = ["Veerg", "Puuduvaid väärtusi"]

  missing = missing[missing["Puuduvaid väärtusi"] > 0]
  missing = missing.sort_values("Puuduvaid väärtusi", ascending=False)

  st.dataframe(missing)
