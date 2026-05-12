import streamlit as st
import streamlit.components.v1 as components
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

tab1, tab2, tab3, tab4 = st.tabs([
    "Ajaline analüüs",
    "Kaart",
    "Märksõnad",
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

# KIHELKOND SIDEBAR
  selected = st.sidebar.multiselect(
      "Kihelkond",
      sorted(df["Kihelkond"].dropna().astype(str).unique()),
      key="kihelkond_filter"
  )

  if selected:
      df = df[df["Kihelkond"].isin(selected)]

# ASUKOHT SIDEBAR
  selected_places = st.sidebar.multiselect(
      "Täpne asukoht",
      sorted(df["Koht täpsemalt"].dropna().unique()),
      key="asukoht_filter"
  )

  if selected_places:
      df = df[df["Koht täpsemalt"].isin(selected_places)]

      #### KUJUTATUD ANDMED ###

# FOTOGRAAF SIDEBAR
  filtered_pids = df["PID"].astype(str).str.strip().unique()

  master_filtered_photographers = master[
      master["PID"].astype(str).str.strip().isin(filtered_pids)
  ].copy()

  all_photographers = sorted(
      master_filtered_photographers["Fotograaf (puhastatud)"]
      .dropna()
      .astype(str)
      .unique()
  )

  selected_photographers = st.sidebar.multiselect(
      "Fotograaf",
      all_photographers
  )

  if selected_photographers:

      selected_pids = master_filtered_photographers[
          master_filtered_photographers["Fotograaf (puhastatud)"]
          .isin(selected_photographers)
      ]["PID"].astype(str).str.strip()

      df = df[
          df["PID"].astype(str).str.strip().isin(selected_pids)
      ]

# LAEN ISIKUD FOTOL TABELI

  people_df = pd.read_excel(
      "ERA_fotod_250426.xlsx",
      sheet_name="isikud_fotol_pikk"
  )

  people_df.columns = people_df.columns.str.strip()

  people_df["PID"] = people_df["PID"].astype(str).str.strip()

# ISIK FOTOL SIDEBAR

  filtered_pids = df["PID"].astype(str).str.strip().unique()

  people_filtered = people_df[
      people_df["PID"].astype(str).str.strip().isin(filtered_pids)
  ].copy()

  all_people = sorted(
      people_filtered["Isik"]
      .dropna()
      .astype(str)
      .unique()
  )

  selected_people = st.sidebar.multiselect(
      "Isik fotol",
      all_people
  )

  if selected_people:

      selected_pids = people_filtered[
          people_filtered["Isik"]
          .isin(selected_people)
      ]["PID"].astype(str).str.strip()

      df = df[
          df["PID"].astype(str).str.strip().isin(selected_pids)
      ]


# MÄRKSÕNADE KATEGOORIAD

  keywords_df = pd.read_excel(
      "ERA_fotod_250426.xlsx",
      sheet_name="märksõnad_pikk"
  )

  keywords_df.columns = keywords_df.columns.str.strip()

  keywords_df["PID"] = (
      keywords_df["PID"]
      .astype(str)
      .str.strip()
  )

  filtered_pids = df["PID"].astype(str).str.strip()

  keywords_filtered = keywords_df[
      keywords_df["PID"].isin(filtered_pids)
  ].copy()

  # KATEGOORIAD

  all_categories = sorted(
      keywords_filtered["Märksõna"]
      .dropna()
      .astype(str)
      .unique()
  )

  selected_categories = st.sidebar.multiselect(
      "Märksõna kategooriad",
      all_categories
  )

  if selected_categories:

      keywords_filtered = keywords_filtered[
          keywords_filtered["Märksõna"]
          .isin(selected_categories)
      ]

  # MÄRKSÕNAD

  all_keywords = sorted(
      keywords_filtered["Märksõna"]
      .dropna()
      .astype(str)
      .unique()
  )

  selected_keywords = st.sidebar.multiselect(
      "Vali märksõnad",
      all_keywords
  )

  if selected_keywords:

      selected_pids = keywords_filtered[
          keywords_filtered["Märksõna"]
          .isin(selected_keywords)
      ]["PID"].astype(str).str.strip()

      df = df[
          df["PID"]
          .astype(str)
          .str.strip()
          .isin(selected_pids)
      ]
# KPI CARDS
  cards = [
      ("Fotode arv", f"{len(df):,}"),
      ("Kihelkondi", df["Kihelkond"].nunique()),
      ("Asukohti", df["Koht täpsemalt"].nunique()),

      (
          "Ajavahemik",
          (
              f"{int(df['Aasta'].dropna().min())}–{int(df['Aasta'].dropna().max())}"
              if not df["Aasta"].dropna().empty
              else "Puudub"
          )
      ),

      ("Koordinaatidega", f"{df['koordinaadid_leitud'].sum():,}")
  ]

  cards_html = """
  <div style="
      display:flex;
      gap:22px;
      flex-wrap:wrap;
      margin-top:25px;
  ">
  """

  for label, value in cards:

      cards_html += f"""
      <div style="
          flex:1;
          min-width:150px;
          background:white;
          padding:18px;
          border-radius:24px;
          box-shadow:0 4px 14px rgba(0,0,0,0.06);
          border:1px solid rgba(0,0,0,0.04);
          text-align:center;
      ">

          <div style="
              font-family: Inter, sans-serif;
              font-size:22px;
              margin-bottom:10px;
          ">
          </div>

          <div style="
              font-family: Inter, sans-serif;
              font-size:14px;
              color:#7a7a7a;
              margin-bottom:10px;
          ">
              {label}
          </div>

          <div style="
              font-family: Inter, sans-serif;
              font-size:25px;
              font-weight:600;
              color:#2b2b2b;
          ">
              {value}
          </div>

      </div>
      """

  cards_html += "</div>"

  components.html(cards_html, height=200, scrolling=False)

  st.markdown("---")

#FOTODE JAOTUS AJAS
  st.markdown("### Fotode jaotus aastate lõikes")
  st.caption("Graafik näitab, kuidas fotode arv muutus aastate jooksul.")

  photos_by_year = (
      df.groupby("Aasta")
      .size()
      .reset_index(name="Fotode arv")
  )

  fig = px.area(
      photos_by_year,
      x="Aasta",
      y="Fotode arv",
      line_shape="spline"
  )

  fig.update_traces(
      line=dict(color="#5B8FF9", width=3),
      fillcolor="rgba(91,143,249,0.18)"
  )

  fig.update_layout(
      height=520,
      paper_bgcolor="white",
      plot_bgcolor="white",

      margin=dict(l=20, r=20, t=20, b=20),

      xaxis=dict(
          title="Aasta",
          showgrid=False,
          zeroline=False
      ),

      yaxis=dict(
          title="Fotode arv",
          gridcolor="rgba(0,0,0,0.06)",
          zeroline=False
      ),

      hovermode="x unified",
  )

  with st.container():
    st.plotly_chart(fig, use_container_width=True)

  # KIHELKONNAD AJAS

  st.markdown("### Kihelkonnad ajas")
  st.caption("Graafik näitab erinevate kihelkondade fotode arvu muutumist ajas.")

  top_kih = df["Kihelkond"].value_counts().head(5).index

  timeline_df = (
      df[df["Kihelkond"].isin(top_kih)]
      .groupby(["Aasta", "Kihelkond"])
      .size()
      .reset_index(name="Fotode arv")
  )

  fig_timeline = px.line(
      timeline_df,
      x="Aasta",
      y="Fotode arv",
      color="Kihelkond",
      markers=True,
  )

  fig_timeline.update_layout(
      paper_bgcolor="white",
      plot_bgcolor="white",
      height=550,
      margin=dict(l=20, r=20, t=30, b=20),
      font=dict(size=14),
      hovermode="x unified",
      legend_title="Kihelkond"
  )

  fig_timeline.update_traces(
      line=dict(width=3),
      marker=dict(size=7),
  )

  st.plotly_chart(fig_timeline, use_container_width=True)

# KÕIGE SAGEDASEMAD ASUKOHAD

  st.markdown("### Kõige sagedasemad asukohad")
  st.caption("Top 10 kõige sagedamini esinevat täpset asukohta.")

  top_places = (
      df["Koht täpsemalt"]
      .dropna()
      .value_counts()
      .head(10)
      .reset_index(name="Fotode arv")
  )

  fig_places = px.bar(
      top_places,
      x="Koht täpsemalt",
      y="Fotode arv",
      color="Fotode arv",
      color_continuous_scale="Tealgrn"
  )

  fig_places.update_layout(
      paper_bgcolor="white",
      plot_bgcolor="white",
      height=500,
      margin=dict(l=20, r=20, t=30, b=20),
      font=dict(size=14),
      coloraxis_showscale=False,
  )

  fig_places.update_traces(
      marker_line_width=0,
      hovertemplate="<b>%{x}</b><br>Fotode arv: %{y}<extra></extra>"
  )

  st.plotly_chart(fig_places, use_container_width=True)
# Pie chart piirkondade / kihelkondade jaotuse visualiseerimiseks
  st.markdown("---")
  st.subheader("Fotode jaotus piirkondade järgi")

  piirkonnad = (
      df["Kihelkond"]
      .dropna()
      .value_counts()
      .head(8)
      .reset_index()
  )

  piirkonnad.columns = ["Kihelkond", "Fotode arv"]

  fig_pie = px.pie(
      piirkonnad,
      names="Kihelkond",
      values="Fotode arv",
      hole=0.45,
      color_discrete_sequence=px.colors.sequential.Tealgrn
  )

  fig_pie.update_layout(
      paper_bgcolor="white",
      plot_bgcolor="white",
      height=500,
      showlegend=True
  )

  st.plotly_chart(fig_pie, use_container_width=True)

  st.caption(
      "Diagramm näitab, millistes kihelkondades on kõige rohkem fotosid."
  )

#VÕRDLUS KIHELKONDADE VAHEL
  st.markdown("---")
  st.subheader("Võrdlus kahe kihelkonna vahel")

  valik = st.multiselect("Vali kuni 2 kihelkonda, et võrrelda nende fotode jaotust ajas.", df["Kihelkond"].unique())

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
  st.caption("Kaart näitab fotode geograafilist jaotust Eesti ajalooliste kihelkondade lõikes.")

  df_map = df.copy()

  df_map = df_map.dropna(
      subset=["Latitude", "Longitude"]
  )

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

# KÕIGE SAGEDAMASED 80 MÄRKSÕNA
  cards_html = """
  <div style="
      display:flex;
      flex-wrap:wrap;
      gap:14px;
      width:100%;
      justify-content:space-between;
      align-items:center;
      margin-top:25px;
      cursor:pointer;
      transition:0.2s ease;
  ">
  """

  max_count = keyword_counts.max()

  for word, count in keyword_counts.items():

      size = 14 + (count / max_count) * 16
      opacity = 0.45 + (count / max_count) * 0.45
      width = 140 + (count / max_count) * 260

      cards_html += f"""
      <div style="
          flex-grow:1;
          min-width:180px;
          max-width:{width}px;
          padding:18px 22px;
          border-radius:22px;
          background:linear-gradient(
                135deg,
                rgba(41,128,185,{opacity}),
                rgba(46,204,113,{opacity})
          );
          color:#F8FAFC;
          font-size:{size}px;
          font-weight:600;
          font-family:Inter,sans-serif;
          letter-spacing:-0.3px;
          text-align:center;
          transition:0.2s;
          box-shadow:0 2px 10px rgba(0,0,0,0.05);
      ">
          {word}
          <div style="
              font-size:12px;
              opacity:0.85;
              margin-top:6px;
          ">
              {count} fotot
          </div>
      </div>
      """

  cards_html += "</div>"

  components.html(cards_html, height=700, scrolling=True)

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
# MÄRKSÕNA AJAS
  st.markdown("---")
  st.subheader("Märksõna ajas")

  selected_word = st.selectbox(
      "Vali märksõna",
      keyword_counts.index
  )

  keyword_data = master_filtered[
      master_filtered["ERA märksõnad (koondatud)"]
      .str.contains(selected_word, case=False, na=False)
  ].copy()

  keyword_years = keyword_data.groupby("Aasta").size().reset_index(name="Fotode arv")

  fig_keyword_time = px.line(
      keyword_years,
      x="Aasta",
      y="Fotode arv",
      markers=True
  )

  fig_keyword_time.update_layout(
      plot_bgcolor="rgba(0,0,0,0)",
      paper_bgcolor="rgba(0,0,0,0)"
  )

  st.plotly_chart(
      fig_keyword_time,
      use_container_width=True,
      config={"displayModeBar": False}
  )
# MÄRKSÕNA SEOSED
  st.markdown("---")
  st.subheader("Seotud märksõnad")

  related_keywords = (
      keyword_data["ERA märksõnad (koondatud)"]
      .dropna()
      .astype(str)
      .str.split(",")
  )

  related_list = []

  for row in related_keywords:
      cleaned = [x.strip() for x in row]

      if selected_word in cleaned:
          related_list.extend(
              [x for x in cleaned if x != selected_word]
          )

  related_counts = (
      pd.Series(related_list)
      .value_counts()
      .head(10)
      .reset_index()
  )

  related_counts.columns = ["Märksõna", "Seose tugevus"]

  fig_related = px.bar(
      related_counts,
      x="Seose tugevus",
      y="Märksõna",
      orientation="h",
      color="Seose tugevus",
      color_continuous_scale="Tealgrn"
  )

  fig_related.update_layout(
      yaxis=dict(categoryorder="total ascending"),
      plot_bgcolor="rgba(0,0,0,0)",
      paper_bgcolor="rgba(0,0,0,0)",
      coloraxis_showscale=False
  )

  st.plotly_chart(
      fig_related,
      use_container_width=True,
      config={"displayModeBar": False}
  )

with tab4:
# ANDMETE TABEL CSV KUJUL
  st.markdown("### Näidis andmestikust")
  st.caption("Valik ERA fotoarhiivi andmestikust.")

  show_cols = [
    "PID",
    "Sisu kirjeldus",
    "Koht täpsemalt",
    "Kihelkond",
    "Aasta"
  ]

  df_show = df[show_cols].rename(columns={
    "PID": "Foto ID",
    "Sisu kirjeldus": "Kirjeldus",
    "Koht täpsemalt": "Asukoht",
    "Kihelkond": "Kihelkond",
    "Aasta": "Aasta"
  })

  st.caption("Esimesed 100 rida ERA fotoarhiivi andmestikust.")

  st.dataframe(
      df[show_cols].head(100),
      use_container_width=True,
      height=350
  )

# ANDMETE KVALITEET
  st.markdown("---")
  st.subheader("Andmete kvaliteet")

  total = len(df)
  with_coords = len(df_map)

  col1, col2, col3 = st.columns(3)

  col1.metric("Kõik fotod", f"{total:,}")
  col2.metric("Koordinaatidega fotod", f"{with_coords:,}")
  col3.metric("Puuduvad koordinaadid", f"{total - with_coords:,}")

  percent = round((with_coords / total) * 100, 1)

  st.markdown(
      f"Kaardil kuvatakse **{percent}%** kõikidest fotodest."
  )

  if percent < 50:
      st.warning(
          "Suur osa andmetest ei sisalda koordinaate."
      )
  else:
      st.success(
          "Andmestik sobib hästi kaardipõhiseks analüüsiks."
      )

  st.caption(
      "Koordinaatide olemasolu võimaldab kasutada ruumilist ja kaardipõhist analüüsi."
  )

#TOP FOTOGRAAFID
  st.markdown("---")
  st.subheader("Kõige sagedasemad fotograafid")

  top_fotograafid = (
      df["Sisu kirjeldus"]
      .dropna()
      .value_counts()
      .head(10)
      .reset_index()
  )

  top_fotograafid.columns = ["Fotograaf", "Fotode arv"]

  fig_foto = px.bar(
      top_fotograafid,
      x="Fotode arv",
      y="Fotograaf",
      orientation="h",
      color="Fotode arv",
      color_continuous_scale="Tealgrn",
  )

  fig_foto.update_layout(
      height=500,
      yaxis=dict(categoryorder="total ascending"),
      paper_bgcolor="white",
      plot_bgcolor="white"
  )

  st.plotly_chart(fig_foto, use_container_width=True)

  st.info(
      "Enamik fotosid pärineb Setumaa ja Lõuna-Eesti piirkondadest. "
      "Andmestikus domineerivad 1950.–1960. aastate fotod."
  )

# PUUDUVAD ANDMED
  st.markdown("---")
  st.subheader("Puuduvad andmed")
  st.caption(
    "Tabel näitab, millistes veergudes esineb kõige rohkem puuduvaid väärtusi."
  )

  missing = df.isnull().sum().reset_index()
  missing.columns = ["Veerg", "Puuduvaid väärtusi"]

  missing = missing[missing["Puuduvaid väärtusi"] > 0]
  missing = missing.sort_values("Puuduvaid väärtusi", ascending=False)

  st.dataframe(missing)
# Filtreeritud andmestiku allalaadimise nupp
  st.markdown("---")

  csv = df.to_csv(index=False).encode("utf-8")

  st.download_button(
      label="Laadi filtreeritud andmestik alla (CSV)",
      data=csv,
      file_name="ERA_fotoarhiiv_filtreeritud.csv",
      mime="text/csv"
  )

  st.caption(
      "Alla laaditakse hetkel filtritega kuvatud andmestik."
  )
st.markdown("---")
st.caption(
    "ERA Photo Archive Dashboard • Digital Humanities Project • University of Tartu"
)
