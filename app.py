import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import ssl
import json
from collections import Counter
from itertools import combinations
import networkx as nx
from pyvis.network import Network
import tempfile

### LEHE STIIL JA SEADISTUSED ###
st.set_page_config(page_title="ERA Dashboard", layout="wide")

st.markdown(
    """
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

h1, h2, h3 {
    font-weight: 700;
}
</style>
""",
    unsafe_allow_html=True,
)

px.defaults.template = "plotly_white"

st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

### TABIDE LOOMINE ###

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Ajaline analüüs", "Kaart", "Märksõnad", "Isikud", "ML analüüs", "Andmed"]
)

df = pd.read_excel("ERA_fotod_250426.xlsx", sheet_name="fotod_koordinaatidega")

df.columns = df.columns.str.strip()

master = pd.read_excel("ERA_fotod_250426.xlsx", sheet_name="fotod_master")

master.columns = master.columns.str.strip()

# ML ANDMED

ml_data = pd.read_excel(
    "era_clip_KOIK_pildid_sigmoid.xlsx"
)

ml_raw = ml_data.copy()

ml_data.columns = (
    ml_data.columns
    .astype(str)
    .str.strip()
)

ml_data = ml_data.rename(columns={
    "true_clusters": "Märksõna kategooria",
    "top1_score": "pred_top1_score",
    "margin_top1_top2": "confidence_margin_top1_top2"
})

ml_raw = ml_data.copy()

ml_data["PID"] = (
    ml_data["PID"]
    .astype(str)
    .str.strip()
)

# ainult vajalikud veerud

ml_columns = [

    "PID",

    "Märksõna kategooria",

    "pred_top1",
    "pred_top2",
    "pred_top3",
    "pred_top4",
    "pred_top5",

    "pred_top1_score",

    "confidence_margin_top1_top2",

    "ML top3 koondskoor",

    "ML otsuse tugevus"

]

existing_ml_cols = [

    c for c in ml_columns
    if c in ml_data.columns

]

ml_data = (
    ml_data[existing_ml_cols]
    .drop_duplicates(subset=["PID"])
)

# MERGE

df["PID"] = (
    df["PID"]
    .astype(str)
    .str.strip()
)

df = df.merge(
    ml_data,
    on="PID",
    how="left"
)

df["PID"] = df["PID"].astype(str).str.strip()
master["PID"] = master["PID"].astype(str).str.strip()

master_small = master[
    [
        "PID",
        "Aasta",
        "Fotograaf (puhastatud)",
        "Žanr",
        "failinimi"
    ]
].drop_duplicates(subset=["PID"])

master_small = master_small.rename(
    columns={
        "Fotograaf (puhastatud)": "Fotograaf"
    }
)

df = df.drop(
    columns=[
        "Aasta",
        "Fotograaf",
        "Žanr",
        "failinimi"
    ],
    errors="ignore"
)

df = df.merge(
    master_small,
    on="PID",
    how="left"
)

df = df.drop_duplicates()

df["Aasta"] = pd.to_numeric(df["Aasta"], errors="coerce")

df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

df["koordinaadid_leitud"] = df["Latitude"].notna() & df["Longitude"].notna()

df["kaardi_piirkond"] = (
    df["Kihelkond"]
    .astype(str)
    .str.strip()
)


with tab1:

    ### ANDMED ###
    ssl._create_default_https_context = ssl._create_unverified_context

    xlsx_path = "ERA_fotod_250426.xlsx"

    st.title("ERA Fotoarhiivi analüütiline juhtlaud")
    st.caption("Kultuuriandmete projekt · University of Tartu")

    st.markdown("""
    Käesolev interaktiivne juhtlaud võimaldab uurida Eesti Rahvaluule Arhiivi (ERA) fotoarhiivi ruumilisi, ajalisi ja temaatilisi mustreid.

    Rakendus põhineb arhiveeritud fotode metaandmetel ning võimaldab analüüsida:
    - fotode jaotust ajas ja piirkondades,
    - märksõnade ja kategooriate sagedust,
    - isikute ja fotograafide võrgustikke,
    - fotodel esinevaid seoseid ja mustreid.

    Juhtlauas kasutatakse ERA fotoarhiivi esimest 10 000 digiteeritud fotot.
    Kokku sisaldab ERA fotoarhiiv üle 88 000 foto.

    Juhtlaud on loodud kultuuriandmete projekti raames eesmärgiga pakkuda visuaalseid tööriistu kultuuripärandi andmete uurimiseks.
    """)

    st.markdown("---")
    #### SIDE BAR ###
    st.sidebar.header("Filtrid")

    # FILTRITE EEMALDAMINE
    if st.sidebar.button("Eemalda kõik filtrid"):
        st.session_state["year_range"] = (
            int(df["Aasta"].min()),
            int(df["Aasta"].max()),
        )
        st.session_state["kihelkond_filter"] = []
        st.session_state["asukoht_filter"] = []
        st.rerun()

    # AASTA SIDEBAR
    year_min = int(df["Aasta"].dropna().min())
    year_max = int(df["Aasta"].dropna().max())

    year_range = st.sidebar.slider(
        "Aasta", year_min, year_max, (year_min, year_max), key="year_range"
    )

    df = df[
        ((df["Aasta"] >= year_range[0]) & (df["Aasta"] <= year_range[1]))
        | (df["Aasta"].isna())
    ]

    # KIHELKOND SIDEBAR
    selected = st.sidebar.multiselect(
        "Kihelkond",
        sorted(df["Kihelkond"].dropna().astype(str).unique()),
        key="kihelkond_filter",
    )

    if selected:
        df = df[df["Kihelkond"].isin(selected)]

    # ASUKOHT SIDEBAR
    selected_places = st.sidebar.multiselect(
        "Täpne asukoht",
        sorted(df["Koht täpsemalt"].dropna().unique()),
        key="asukoht_filter",
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

    selected_photographers = st.sidebar.multiselect("Fotograaf", all_photographers)

    if selected_photographers:

        selected_pids = (
            master_filtered_photographers[
                master_filtered_photographers["Fotograaf (puhastatud)"].isin(
                    selected_photographers
                )
            ]["PID"]
            .astype(str)
            .str.strip()
        )

        df = df[df["PID"].astype(str).str.strip().isin(selected_pids)]

    # LAEN ISIKUD FOTOL TABELI

    people_df = pd.read_excel("ERA_fotod_250426.xlsx", sheet_name="isikud_fotol_pikk")

    people_df.columns = people_df.columns.str.strip()

    people_df["PID"] = people_df["PID"].astype(str).str.strip()

    # ISIK FOTOL SIDEBAR

    filtered_pids = df["PID"].astype(str).str.strip().unique()

    people_filtered = people_df[
        people_df["PID"].astype(str).str.strip().isin(filtered_pids)
    ].copy()

    all_people = sorted(people_filtered["Isik"].dropna().astype(str).unique())

    selected_people = st.sidebar.multiselect("Isik fotol", all_people)

    if selected_people:

        selected_pids = (
            people_filtered[people_filtered["Isik"].isin(selected_people)]["PID"]
            .astype(str)
            .str.strip()
        )

        df = df[df["PID"].astype(str).str.strip().isin(selected_pids)]

    # MÄRKSÕNADE LAADIMINE
    @st.cache_data
    def load_marksonad(xlsx_path):

        try:

            marksoned = pd.read_excel(xlsx_path, sheet_name="märksõnad_pikk")

        except Exception:

            return pd.DataFrame(columns=["PID", "Märksõna"])

        marksoned.columns = marksoned.columns.astype(str).str.strip()

        if "PID" not in marksoned.columns:
            marksoned["PID"] = pd.NA

        if "Märksõna" not in marksoned.columns:
            marksoned["Märksõna"] = pd.NA

        marksoned["PID"] = marksoned["PID"].fillna("").astype(str).str.strip()

        marksoned["Märksõna"] = marksoned["Märksõna"].fillna("").astype(str).str.strip()

        marksoned = marksoned[marksoned["Märksõna"] != ""]

        return marksoned

    # MÄRKSÕNADE KATEGOORIAD
    @st.cache_data
    def load_marksona_kategooriad():

        try:

            ml_df = pd.read_excel("ERA_märksõnad_ML.xlsx")

        except Exception:

            return pd.DataFrame(columns=["Märksõna", "Kategooria"])

        ml_df.columns = ml_df.columns.astype(str).str.strip()
        if "PID" not in ml_df.columns:
            ml_df["PID"] = pd.NA

        if "Märksõna" not in ml_df.columns:
            ml_df["Märksõna"] = pd.NA

        if "Märksõna2" not in ml_df.columns:
            ml_df["Märksõna2"] = pd.NA

        ml_df = ml_df.rename(columns={"Märksõna2": "Kategooria"})

        ml_df["PID"] = ml_df["PID"].fillna("").astype(str).str.strip()

        ml_df["Märksõna"] = ml_df["Märksõna"].fillna("").astype(str).str.strip()

        ml_df["Kategooria"] = ml_df["Kategooria"].fillna("").astype(str).str.strip()

        ml_df = ml_df[(ml_df["Märksõna"] != "") & (ml_df["Kategooria"] != "")]

        return ml_df

    # MÄRKSÕNADE VALIKUD

    def get_marksona_options(marksoned, current_df=None):

        if current_df is not None and "PID" in current_df.columns:

            current_pids = set(current_df["PID"].dropna().astype(str).unique())

            filtered_marksoned = marksoned[marksoned["PID"].isin(current_pids)]

        else:
            filtered_marksoned = marksoned

        options = (
            filtered_marksoned["Märksõna"]
            .dropna()
            .astype(str)
            .value_counts()
            .index.tolist()
        )

        return options

    # MÄRKSÕNADE FILTREERIMINE

    def filter_by_marksonad(fotod_df, marksoned_df, selected_marksonad, logic="OR"):

        if not selected_marksonad:
            return fotod_df

        if logic == "OR":

            matched_pids = set(
                marksoned_df[marksoned_df["Märksõna"].isin(selected_marksonad)]["PID"]
                .dropna()
                .astype(str)
                .unique()
            )

        else:

            matched_pids = None

            for keyword in selected_marksonad:

                keyword_pids = set(
                    marksoned_df[marksoned_df["Märksõna"] == keyword]["PID"]
                    .dropna()
                    .astype(str)
                    .unique()
                )

                if matched_pids is None:
                    matched_pids = keyword_pids
                else:
                    matched_pids = matched_pids & keyword_pids

            if matched_pids is None:
                matched_pids = set()

        filtered_df = fotod_df[fotod_df["PID"].astype(str).isin(matched_pids)]

        return filtered_df

    # MÄRKSÕNADE SIDEBAR

    st.sidebar.markdown("## Märksõnad")

    marksoned = load_marksonad(xlsx_path)

    marksona_kategooriad = load_marksona_kategooriad()

    # KATEGOORIA FILTER
    filtered_pids = set(df["PID"].dropna().astype(str).unique())

    filtered_categories_df = marksona_kategooriad[
        marksona_kategooriad["PID"].astype(str).isin(filtered_pids)
    ]

    all_categories = sorted(
        filtered_categories_df["Kategooria"].dropna().astype(str).unique()
    )

    selected_categories = st.sidebar.multiselect("Märksõna kategooria", all_categories)

    # MÄRKSÕNA VALIKUD

    marksona_options = get_marksona_options(marksoned, current_df=df)

    if selected_categories:

        allowed_keywords = (
            marksona_kategooriad[
                marksona_kategooriad["Kategooria"].isin(selected_categories)
            ]["Märksõna"]
            .dropna()
            .astype(str)
            .unique()
        )

        marksona_options = [x for x in marksona_options if x in allowed_keywords]

        matched_pids = (
            marksona_kategooriad[
                marksona_kategooriad["Kategooria"].isin(selected_categories)
            ]["PID"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
        )

        df = df[df["PID"].astype(str).str.strip().isin(matched_pids)]

    # MÄRKSÕNA FILTER

    selected_marksonad = st.sidebar.multiselect(
        "Vali märksõnad",
        options=marksona_options,
        max_selections=5,
        placeholder="Vali märksõnad",
    )

    if len(selected_marksonad) > 1:

        marksona_logic = st.sidebar.radio(
            "Märksõnade loogika", options=["OR", "AND"], horizontal=True
        )

    else:
        marksona_logic = "OR"

    df = filter_by_marksonad(
        fotod_df=df,
        marksoned_df=marksoned,
        selected_marksonad=selected_marksonad,
        logic=marksona_logic,
    )

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
            ),
        ),
        ("Koordinaatidega", f"{df['koordinaadid_leitud'].sum():,}"),
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

    # FOTODE JAOTUS AJAS
    st.markdown("### Fotode jaotus aastate lõikes")
    st.caption("Graafik näitab, kuidas fotode arv muutus aastate jooksul.")

    photos_by_year = df.groupby("Aasta").size().reset_index(name="Fotode arv")

    fig = px.area(photos_by_year, x="Aasta", y="Fotode arv", line_shape="spline")

    fig.update_traces(
        line=dict(color="#5B8FF9", width=3), fillcolor="rgba(91,143,249,0.18)"
    )

    fig.update_layout(
        height=520,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(title="Aasta", showgrid=False, zeroline=False),
        yaxis=dict(title="Fotode arv", gridcolor="rgba(0,0,0,0.06)", zeroline=False),
        hovermode="x unified",
    )

    with st.container():
        st.plotly_chart(fig, use_container_width=True)

    # KIHELKONNAD AJAS

    st.markdown("### Kihelkonnad ajas")
    st.caption("Fotode arvu muutus ajas valitud kihelkondades.")

    all_kih = sorted(
        df["Kihelkond"]
        .dropna()
        .astype(str)
        .unique()
    )

    top_kih = (
        df["Kihelkond"]
        .value_counts()
        .head(4)
        .index
        .tolist()
    )

    selected_kih = st.multiselect(
        "Vali kuni 4 kihelkonda",
        all_kih,
        default=top_kih,
        max_selections=4,
    )

    if selected_kih:

        timeline_df = (
            df[df["Kihelkond"].isin(selected_kih)]
            .groupby(["Aasta", "Kihelkond"])
            .size()
            .reset_index(name="Fotode arv")
        )

        fig_timeline = px.line(
            timeline_df,
            x="Aasta",
            y="Fotode arv",
            color="Kihelkond",
            line_shape="spline",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )

        fig_timeline.update_traces(
            line=dict(width=2),
        )

        fig_timeline.update_layout(
            paper_bgcolor="white",
            plot_bgcolor="white",
            height=500,
            margin=dict(l=20, r=20, t=30, b=20),
            hovermode="x unified",
            showlegend=True,
        )

    st.plotly_chart(
        fig_timeline,
        use_container_width=True
    )

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
        color_continuous_scale="Tealgrn",
    )

    fig_places.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        font=dict(size=14),
        coloraxis_showscale=False,
    )

    fig_places.update_traces(
        marker_line_width=0,
        hovertemplate="<b>%{x}</b><br>Fotode arv: %{y}<extra></extra>",
    )

    st.plotly_chart(fig_places, use_container_width=True)

    # FOTODE JAOTUS PIIRKONDADE JÄRGI
    st.markdown("---")
    st.subheader("Fotode jaotus piirkondade järgi")

    st.caption(
        "Diagramm näitab, millistes kihelkondades leidub kõige rohkem fotosid."
    )

    region_counts = (
        df["Kihelkond"]
        .value_counts()
        .head(10)
        .reset_index()
    )

    region_counts.columns = [
        "Kihelkond",
        "Fotode arv"
    ]

    region_counts = region_counts.sort_values(
        by="Fotode arv",
        ascending=True
    )

    fig_regions = px.bar(
        region_counts,
        x="Fotode arv",
        y="Kihelkond",
        orientation="h",
        text="Fotode arv",
        color="Fotode arv",
        color_continuous_scale=[
            "#D7EFE2",
            "#9AD7C3",
            "#52B69A",
            "#1B6F78"
        ],
    )

    fig_regions.update_traces(
        textposition="outside",
        marker_line_width=0,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Fotode arv: %{x}<extra></extra>"
        ),
    )

    fig_regions.update_layout(
        height=540,

        plot_bgcolor="white",
        paper_bgcolor="white",

        coloraxis_showscale=False,

        margin=dict(
            t=20,
            l=20,
            r=10,
            b=20
        ),

        xaxis_title="Fotode arv",
        yaxis_title="Kihelkond",

        font=dict(size=15),

        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.06)",
            zeroline=False,
        ),

        yaxis=dict(
            showgrid=False,
        ),
    )

    st.plotly_chart(
        fig_regions,
        use_container_width=True,
        config={"displayModeBar": False}
    )
# GEOJSONI LAADIMINE
@st.cache_data
def load_geojson(path):

    with open(path, "r", encoding="utf-8") as f:

        return json.load(f)


# GEOJSON - KIHELKONNA PIIRID
geojson_data = load_geojson(
    "kih1922_region.json"
)


# GEOJSONI KIHELKONDADE NIMEDE LUGEMINE
def extract_geojson_feature_names(
    geojson,
    prop_name="KIHELKOND"
):

    names = set()

    if not geojson or "features" not in geojson:
        return names

    for feature in geojson["features"]:

        props = feature.get("properties", {})

        val = props.get(prop_name)

        if val is not None and str(val).strip():

            names.add(
                str(val).strip()
            )

    return names

@st.cache_data
def get_centroids(_gj):

    result = {}

    if not _gj:
        return result

    for feat in _gj.get("features", []):

        name = feat.get(
            "properties",
            {}
        ).get("KIHELKOND", "")

        geom = feat.get("geometry", {})

        coords = []

        if geom.get("type") == "Polygon":

            coords = geom.get(
                "coordinates",
                [[]]
            )[0]

        elif geom.get("type") == "MultiPolygon":

            for poly in geom.get("coordinates", []):

                if poly and poly[0]:

                    coords.extend(poly[0])

        if coords and name:

            lons = [
                c[0]
                for c in coords
                if len(c) >= 2
            ]

            lats = [
                c[1]
                for c in coords
                if len(c) >= 2
            ]

            if lons and lats:

                result[name] = (
                    sum(lats) / len(lats),
                    sum(lons) / len(lons)
                )

    return result

def poly_rings(geom):

    if not geom or "type" not in geom:
        return []

    rings = []

    try:

        if (
            geom["type"] == "Polygon"
            and geom["coordinates"]
            and geom["coordinates"][0]
        ):

            rings.append(
                geom["coordinates"][0]
            )

        elif geom["type"] == "MultiPolygon":

            for poly in geom["coordinates"]:

                if poly and poly[0]:

                    rings.append(poly[0])

    except Exception:

        pass

    return rings


def add_borders(
    fig,
    geojson,
    color="black",
    width=1
):

    if not geojson or "features" not in geojson:

        return fig

    for feat in geojson["features"]:

        for coords in poly_rings(
            feat.get("geometry", {})
        ):

            if not coords or len(coords) < 2:

                continue

            try:

                lons = [
                    c[0]
                    for c in coords
                    if len(c) >= 2
                ]

                lats = [
                    c[1]
                    for c in coords
                    if len(c) >= 2
                ]

                fig.add_trace(
                    go.Scattermapbox(
                        lon=lons,
                        lat=lats,

                        mode="lines",

                        line=dict(
                            color=color,
                            width=width
                        ),

                        hoverinfo="skip",

                        showlegend=False
                    )
                )

            except Exception:

                continue

    return fig

def build_hover(row, cols):

    parts = []

    for c in cols:

        if c in row and pd.notna(row[c]):

            val = str(row[c]).strip()

            if val:

                parts.append(
                    f"<b>{c}:</b> {val}"
                )

    if parts:

        return "<br>".join(parts)

    return "—"

def clean_series(series):

    if series is None:

        return pd.Series(
            dtype="object"
        )

    s = (
        series
        .dropna()
        .astype(str)
        .str.strip()
    )

    return s[
        s != ""
    ]

def clean_df(df_in):

    out = df_in.copy()

    for col in out.select_dtypes(
        include="object"
    ).columns:

        out[col] = (
            out[col]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return out

#KAART
with tab2:

    st.markdown(
        "Kaart visualiseerib fotokogu ruumilisi mustreid ajalooliste kihelkondade lõikes."
    )

    geojson = load_geojson("kih1922_region.json")

    centroids = get_centroids(geojson) if geojson else {}

    geo_names = {
        str(x).strip()
        for x in centroids.keys()
    }

    # SESSION STATE
    if "kaart_vaade" not in st.session_state:
        st.session_state["kaart_vaade"] = "overview"

    if "valitud_kihelkond" not in st.session_state:
        st.session_state["valitud_kihelkond"] = None

    # OVERVIEW
    if st.session_state["kaart_vaade"] == "overview":

        if not geojson:

            st.warning("GeoJSON faili ei leitud.")

        elif "kaardi_piirkond" not in df.columns:

            st.warning("Veerg 'kaardi_piirkond' puudub.")

        else:

            # FILTREERITUD ANDMED
            src = df[
                df["kaardi_piirkond"].notna()
            ].copy()

            src = src[
                ~src["kaardi_piirkond"]
                .astype(str)
                .str.lower()
                .isin([
                    "teadmata",
                    "välismaa",
                    "välismaa,",
                    "nan",
                    "none",
                    "null",
                    "<na>"
                ])
            ]

            # NORMALISEERI NIMED
            src["kaardi_piirkond"] = (
                src["kaardi_piirkond"]
                .astype(str)
                .str.strip()
            )

            # FOTODE ARV PIIRKONNA KOHTA
            counts = (
                src
                .groupby("kaardi_piirkond")
                .size()
                .reset_index(name="Fotode arv")
            )

            # AINULT GEOJSONIS OLEVAD
            geo_c = counts[
                counts["kaardi_piirkond"]
                .isin(geo_names)
            ].copy()

            # DEBUG
            # st.write(geo_c.head())
            # st.write(len(geo_c))

            if geo_c.empty:

                st.warning(
                    "GeoJSON ja dataframe piirkonnanimed ei kattu."
                )

            else:

                # KAART
                fig = px.choropleth_mapbox(

                    geo_c,

                    geojson=geojson,

                    locations="kaardi_piirkond",

                    featureidkey="properties.KIHELKOND",

                    color="Fotode arv",

                    color_continuous_scale=[
                        "#d9f0ff",
                        "#a6dcef",
                        "#7dcfb6",
                        "#5b8ff9",
                        "#5a189a"
                    ],

                    hover_name="kaardi_piirkond",

                    hover_data={
                        "Fotode arv": True
                    },

                    custom_data=[
                        "kaardi_piirkond"
                    ],

                    mapbox_style="open-street-map",

                    zoom=6.2,

                    center={
                        "lat": 58.7,
                        "lon": 25.0
                    },

                    opacity=0.68
                )

                # PIIRID
                fig = add_borders(
                    fig,
                    geojson,
                    color="rgba(40,40,40,0.55)",
                    width=0.8
                )

                fig.update_layout(

                    height=700,

                    margin={
                        "r": 0,
                        "t": 10,
                        "l": 0,
                        "b": 0
                    },

                    clickmode="event+select",

                    coloraxis_colorbar=dict(
                        title="Fotode arv"
                    )
                )

                # STREAMLIT SELECT API
                event = st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="main_kaart",
                    on_select="rerun",
                    selection_mode="points"
                )

                # KLIKITUD PIIRKOND
                try:

                    points = (
                        event.get("selection", {})
                        .get("points", [])
                    )

                    if points:

                        p = points[0]

                        selected = (
                            (p.get("customdata") or [None])[0]
                            or p.get("location")
                        )

                        if selected:

                            st.session_state[
                                "valitud_kihelkond"
                            ] = str(selected)

                            st.session_state[
                                "kaart_vaade"
                            ] = "detail"

                            st.rerun()

                except Exception:
                    pass

    # DETAIL VIEW
    else:

        val = st.session_state["valitud_kihelkond"]

        if not val:

            st.session_state["kaart_vaade"] = "overview"

            st.rerun()

        # TAGASI NUPP
        if st.button("← Tagasi üldkaardile"):

            st.session_state["kaart_vaade"] = "overview"

            st.session_state["valitud_kihelkond"] = None

            st.rerun()

        st.subheader(f" {val}")

        # FILTER
        det = df[
            df["kaardi_piirkond"]
            .astype(str)
            .str.strip()
            == val
        ].copy()

        ok = (
            det["Latitude"].notna()
            &
            det["Longitude"].notna()
        )

        # KPI
        k1, k2, k3, k4 = st.columns(4)

        k1.metric(
            "Fotosid",
            len(det)
        )

        k2.metric(
            "Koordinaatidega",
            int(ok.sum())
        )

        k3.metric(
            "Ajavahemik",

            (
                f"{int(det['Aasta'].min())}"
                f"–"
                f"{int(det['Aasta'].max())}"
            )

            if (
                "Aasta" in det.columns
                and det["Aasta"].notna().any()
            )

            else "?"
        )

        k4.metric(
            "Fotograafe",

            clean_series(
                det["Fotograaf"]
            ).nunique()

            if "Fotograaf" in det.columns
            else "?"
        )

        # KOORDINAATIDEGA FOTOD
        pts = det[ok].copy()

        pts = pts.rename(
            columns={
                "Latitude": "_lat",
                "Longitude": "_lon"
            }
        )

        if not pts.empty:

            center = centroids.get(
                val,
                (
                    pts["_lat"].median(),
                    pts["_lon"].median()
                )
            )

            # HOVER
            hover_cols = [
                c for c in [
                    "Aasta",
                    "Fotograaf",
                    "Žanr",
                    "Koht täpsemalt"
                ]

                if c in pts.columns
            ]

            pts["_hover"] = pts.apply(
                lambda r: build_hover(r, hover_cols),
                axis=1
            )

            title_col = (
                "Sisu kirjeldus"
                if "Sisu kirjeldus" in pts.columns
                else None
            )

            # DETAILKAART
            fig_d = go.Figure(

                go.Scattermapbox(

                    lat=pts["_lat"],

                    lon=pts["_lon"],

                    mode="markers",

                    marker=dict(
                        size=10,
                        opacity=0.85,
                        color="#e63946"
                    ),

                    customdata=(
                        pts[[title_col]].fillna("")
                        if title_col
                        else None
                    ),

                    text=pts["_hover"],

                    hovertemplate=(

                        "<b>%{customdata[0]}</b><br>"
                        "%{text}<extra></extra>"

                        if title_col

                        else "%{text}<extra></extra>"
                    )
                )
            )

            # PIIR
            kihel_feat = [

                f for f in geojson["features"]

                if (
                    f.get("properties", {})
                    .get("KIHELKOND")
                    == val
                )
            ]

            if kihel_feat:

                for ring in poly_rings(

                    kihel_feat[0]
                    .get("geometry", {})
                ):

                    lons = [
                        c[0]
                        for c in ring
                        if len(c) >= 2
                    ]

                    lats = [
                        c[1]
                        for c in ring
                        if len(c) >= 2
                    ]

                    fig_d.add_trace(

                        go.Scattermapbox(

                            lon=lons,

                            lat=lats,

                            mode="lines",

                            line=dict(
                                color="rgba(20,20,20,0.9)",
                                width=2
                            ),

                            hoverinfo="skip",

                            showlegend=False
                        )
                    )

            fig_d.update_layout(

                mapbox=dict(

                    style="open-street-map",

                    zoom=10,

                    center={
                        "lat": center[0],
                        "lon": center[1]
                    }
                ),

                height=500,

                margin={
                    "r": 0,
                    "t": 10,
                    "l": 0,
                    "b": 0
                },

                showlegend=False
            )

            st.plotly_chart(
                fig_d,
                use_container_width=True
            )

        else:

            st.info(
                "Sellel piirkonnal koordinaatidega fotosid ei ole."
            )

        # TABLID
        col1, col2 = st.columns(2)

        # FOTOGRAAFID
        with col1:

            if "Fotograaf" in det.columns:

                ft = (
                    clean_series(det["Fotograaf"])
                    .value_counts()
                    .head(8)
                    .reset_index()
                )

                ft.columns = [
                    "Fotograaf",
                    "Arv"
                ]

                if not ft.empty:

                    st.markdown("### Fotograafid")

                    st.dataframe(
                        ft,
                        hide_index=True,
                        use_container_width=True
                    )

        # MÄRKSÕNAD
        with col2:

            if (
                not marksoned.empty
                and "Märksõna" in marksoned.columns
            ):

                ms_d = (

                    clean_series(

                        marksoned[
                            marksoned["PID"]
                            .isin(det["PID"])
                        ]["Märksõna"]

                    )

                    .value_counts()

                    .head(8)

                    .reset_index()
                )

                ms_d.columns = [
                    "Märksõna",
                    "Arv"
                ]

                if not ms_d.empty:

                    st.markdown("### Top märksõnad")

                    st.dataframe(
                        ms_d,
                        hide_index=True,
                        use_container_width=True
                    )

        # TABEL
        with st.expander(
            "Vaata kõiki fotosid sellest piirkonnast"
        ):

            d_cols = [

                c for c in [

                    "PID",
                    "Aasta",
                    "Fotograaf",
                    "Žanr",
                    "Sisu kirjeldus",
                    "Koht täpsemalt",
                    "failinimi"

                ]

                if c in det.columns
            ]

            st.dataframe(
                clean_df(det[d_cols]).head(500),
                use_container_width=True,
                hide_index=True
            )


with tab3:
    # MÄRKSÕNAD
    st.header("Fotokogu temaatiline analüüs")
    st.caption("Ülevaade ERA fotoarhiivi märksõnadest ja kategooriatest.")

    filtered_pids = df["PID"].astype(str).str.strip().unique()

    keywords_series = (
        marksoned[marksoned["PID"].isin(filtered_pids)]["Märksõna"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    if selected_marksonad:

        keywords = keywords_series[keywords_series.isin(selected_marksonad)]

    elif selected_categories:

        allowed_words = marksona_kategooriad[
            marksona_kategooriad["Kategooria"].isin(selected_categories)
        ]["Märksõna"].unique()

        keywords = keywords_series[keywords_series.isin(allowed_words)]

    else:

        keywords = keywords_series

    keyword_counts = keywords.value_counts().head(80)

    # KPI
    k1, k2, k3 = st.columns(3)

    k1.metric("Märksõnu kokku", f"{len(keywords):,}")

    k2.metric("Unikaalseid märksõnu", f"{keywords.nunique():,}")

    k3.metric(
        "Kõige sagedasem", keyword_counts.index[0] if not keyword_counts.empty else "-"
    )

    if keywords.empty:
        st.warning("Valitud filtritega sobivaid märksõnu ei leitud.")
        st.stop()

# TOP KATEGOORIAD
    st.markdown("---")
    st.subheader("Kõige sagedasemad kategooriad")

    st.caption(
        "Diagramm näitab, millised märksõnade kategooriad esinevad fotoarhiivis kõige sagedamini."
    )

    filtered_pids = df["PID"].astype(str).str.strip().unique()

    filtered_categories = marksona_kategooriad[
        marksona_kategooriad["PID"].astype(str).isin(filtered_pids)
    ]

    category_counts = (
        filtered_categories["Kategooria"]
        .value_counts()
        .head(8)
        .reset_index()
    )

    category_counts.columns = ["Kategooria", "Fotode arv"]

    category_counts = category_counts.sort_values(
        by="Fotode arv",
        ascending=True
    )

    fig_categories = px.bar(
        category_counts,
        x="Fotode arv",
        y="Kategooria",
        orientation="h",
        text="Fotode arv",
        color="Fotode arv",
        color_continuous_scale=[
            "#A8E6CF",
            "#6FD3B3",
            "#3DB7A3",
            "#2A7F9E"
        ],
    )

    fig_categories.update_traces(
        textposition="outside",
        marker_line_width=0,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Fotode arv: %{x}<extra></extra>"
        ),
    )

    fig_categories.update_layout(
        height=520,

        plot_bgcolor="white",
        paper_bgcolor="white",

        coloraxis_showscale=False,

        margin=dict(t=20, l=20, r=40, b=20),

        xaxis_title="Fotode arv",
        yaxis_title="Kategooria",

        font=dict(size=15),

        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.06)",
            zeroline=False,
        ),

        yaxis=dict(
            showgrid=False,
        ),
    )

    st.plotly_chart(
        fig_categories,
        use_container_width=True,
        config={"displayModeBar": False},
    )
    # KÕIGE SAGEDAMASED 80 MÄRKSÕNA
    st.markdown("---")
    st.subheader("Kõige sagedasemad märksõnad")
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

    # MÄRKSÕNA AJAS

    st.markdown("---")
    st.subheader("Märksõna ajas")
    st.caption(
        "Graafik näitab, kuidas valitud märksõna kasutus fotoarhiivis ajas muutus."
    )

    selected_word = st.selectbox("Vali märksõna", keyword_counts.index)

    selected_word_pids = (
        marksoned[marksoned["Märksõna"] == selected_word]["PID"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    keyword_data = df[df["PID"].astype(str).str.strip().isin(selected_word_pids)].copy()

    keyword_data = keyword_data[keyword_data["Aasta"].notna()]

    keyword_years = keyword_data.groupby("Aasta").size().reset_index(name="Fotode arv")

    if keyword_years["Aasta"].nunique() > 1:

        fig_keyword_time = px.line(
            keyword_years, x="Aasta", y="Fotode arv", markers=True
        )

        fig_keyword_time.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
        )

        st.plotly_chart(
            fig_keyword_time, use_container_width=True, config={"displayModeBar": False}
        )

    else:

        st.info("Ajatelje kuvamiseks on vaja rohkem erinevaid aastaid.")

    # MÄRKSÕNA SEOSED
    st.markdown("---")
    st.subheader("Seotud märksõnad")

    st.caption(
        "Diagramm näitab märksõnu, mis esinevad kõige sagedamini koos valitud märksõnaga."
    )

    selected_pids = set(
        marksoned[
            marksoned["Märksõna"] == selected_word
        ]["PID"].astype(str)
    )

    related_df = marksoned[
        marksoned["PID"].astype(str).isin(selected_pids)
    ]

    related_counts = (
        related_df[
            related_df["Märksõna"] != selected_word
        ]["Märksõna"]
        .value_counts()
        .head(10)
        .reset_index()
    )

    related_counts.columns = [
        "Märksõna",
        "Seose tugevus"
    ]

    related_counts = related_counts.sort_values(
        by="Seose tugevus",
        ascending=True
    )

    fig_related = px.bar(
        related_counts,
        x="Seose tugevus",
        y="Märksõna",
        orientation="h",
        text="Seose tugevus",
        color="Seose tugevus",
        color_continuous_scale=[
            "#A8E6CF",
            "#6FD3B3",
            "#3DB7A3",
            "#2A7F9E"
        ],
    )

    fig_related.update_traces(
        textposition="outside",
        marker_line_width=0,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Seose tugevus: %{x}<extra></extra>"
        ),
    )

    fig_related.update_layout(
        height=520,

        plot_bgcolor="white",
        paper_bgcolor="white",

        coloraxis_showscale=False,

        margin=dict(
            t=20,
            l=20,
            r=10,
            b=20
        ),

        xaxis_title="Seose tugevus",
        yaxis_title="Märksõna",

        font=dict(size=15),

        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(0,0,0,0.06)",
            zeroline=False,
        ),

        yaxis=dict(
            showgrid=False,
        ),
    )

    st.plotly_chart(
        fig_related,
        use_container_width=True,
        config={"displayModeBar": False}
    )

with tab4:
    st.header("Isikute analüüs")
    st.caption("Fotodel kujutatud isikute sagedus ja seosed.")

    filtered_pids = df["PID"].astype(str).str.strip().unique()

    isikud_filtered = people_df[
        people_df["PID"].astype(str).str.strip().isin(filtered_pids)
    ].copy()

    if isikud_filtered.empty:

        st.warning("Valitud filtritega isikuid ei leitud.")

    else:
        # KPI
        k1, k2, k3, k4 = st.columns(4)

        k1.metric("Unikaalseid isikuid", isikud_filtered["Isik"].dropna().nunique())

        k2.metric("Isikukirjeid kokku", len(isikud_filtered))

        k3.metric("Fotodel kokku", len(isikud_filtered["PID"].dropna().unique()))
        top_person = isikud_filtered["Isik"].value_counts()

        if not top_person.empty:

            top_name = top_person.index[0]
            top_count = top_person.iloc[0]

            top_display = f"{top_name} ({top_count})"

        else:

            top_display = "-"

        k4.metric("Kõige sagedasem isik", top_display)

        # TOP ISIKUD + ISIKUPAARID
        st.markdown("---")
        col1, col2 = st.columns(2)

        # TOP ISIKUD
        with col1:

            st.subheader("Kõige sagedasemad isikud")
            st.caption(
                "Diagramm kuvab isikud, kes esinevad andmestikus kõige sagedamini."
            )
            top_isik_n = st.slider(
                "Näita top N isikut", 5, 20, 10, key="top_isikud_slider"
            )

            top_people = (
                isikud_filtered["Isik"].value_counts().head(top_isik_n).reset_index()
            )

            top_people.columns = ["Isik", "Fotode arv"]

            fig_people = px.bar(
                top_people,
                x="Fotode arv",
                y="Isik",
                orientation="h",
                color="Fotode arv",
                color_continuous_scale="Tealgrn",
            )

            fig_people.update_layout(
                yaxis=dict(categoryorder="total ascending"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
                height=450,
            )

            st.plotly_chart(
                fig_people, use_container_width=True, config={"displayModeBar": False}
            )

        # TOP ISIKUPAARID

        with col2:

            st.subheader("Koos esinevad isikupaarid")
            st.caption(
                "Diagramm näitab, millised isikupaarid esinevad fotodel kõige sagedamini koos."
            )
            top_pair_n = st.slider(
                "Näita top N isikupaari", 5, 15, 10, key="top_isikupaarid_slider"
            )

            pair_counter = Counter()

            grouped_people = isikud_filtered.groupby("PID")["Isik"].apply(
                lambda x: sorted(set(x.dropna().astype(str)))
            )

            for people in grouped_people:

                if len(people) >= 2:

                    for pair in combinations(people, 2):

                        pair_counter[pair] += 1

            pair_data = [
                {"Isikupaar": f"{a} + {b}", "Koosesinemised": count}
                for (a, b), count in pair_counter.most_common(top_pair_n)
            ]

            pair_df = pd.DataFrame(pair_data)

            if pair_df.empty:

                st.info("Koosesinevaid isikupaare ei leitud.")

            else:

                fig_pairs = px.bar(
                    pair_df,
                    x="Koosesinemised",
                    y="Isikupaar",
                    orientation="h",
                    color="Koosesinemised",
                    color_continuous_scale="Tealgrn",
                )

                fig_pairs.update_layout(
                    yaxis=dict(categoryorder="total ascending"),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    coloraxis_showscale=False,
                    height=450,
                )

                st.plotly_chart(
                    fig_pairs,
                    use_container_width=True,
                    config={"displayModeBar": False},
                )

        # ISIKU OTSING

        st.markdown("---")
        st.subheader("Isiku otsing")
        st.caption(
            "Tabel kuvab kõik valitud isikuga seotud fotod ja nende metaandmed."
        )
        selected_person = st.selectbox(
            "Vali isik", sorted(isikud_filtered["Isik"].dropna().astype(str).unique())
        )
        st.caption(
            "Tabel kuvab kõik valitud isikuga seotud fotod ja nende metaandmed."
        )
        person_pids = (
            isikud_filtered[isikud_filtered["Isik"] == selected_person]["PID"]
            .astype(str)
            .str.strip()
            .unique()
        )

        person_df = df[df["PID"].astype(str).str.strip().isin(person_pids)]

        st.metric("Fotode arv", len(person_df))

        show_cols = ["PID", "Aasta", "Kihelkond", "Koht täpsemalt", "Sisu kirjeldus"]

        existing_cols = [c for c in show_cols if c in person_df.columns]

        st.dataframe(person_df[existing_cols].head(100), use_container_width=True)

        # ISIKUD AJAS
        st.markdown("---")
        st.subheader("Isik ajas")
        st.caption(
            "Graafik näitab valitud isiku esinemist fotodel aastate lõikes."
        )
        person_years = (
            person_df[person_df["Aasta"].notna()]
            .groupby("Aasta")
            .size()
            .reset_index(name="Fotode arv")
        )

        if person_years["Aasta"].nunique() > 1:

            fig_person_time = px.line(
                person_years, x="Aasta", y="Fotode arv", markers=True
            )

            fig_person_time.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=250
            )

            st.plotly_chart(
                fig_person_time,
                use_container_width=True,
                config={"displayModeBar": False},
            )

        else:

            st.info("Ajatelje kuvamiseks " "pole piisavalt erinevaid aastaid.")

        # KOOS ESINEVAD ISIKUD
        st.markdown("---")
        st.subheader("Koos esinevad isikud")
        st.caption(
            "Diagramm näitab, millised isikud esinevad fotodel kõige sagedamini koos teiste isikutega."
        )
        related_people = isikud_filtered[
            isikud_filtered["PID"].astype(str).isin(person_pids)
        ].copy()

        related_people["Isik"] = related_people["Isik"].astype(str).str.strip()

        related_counts = (
            related_people[related_people["Isik"] != selected_person]["Isik"]
            .value_counts()
            .head(15)
            .reset_index()
        )

        related_counts.columns = ["Isik", "Koosesinemised"]

        if related_counts.empty:

            st.info("Selle isikuga seotud teisi inimesi ei leitud.")

        else:

            fig_related_people = px.bar(
                related_counts,
                x="Koosesinemised",
                y="Isik",
                orientation="h",
                color="Koosesinemised",
                color_continuous_scale="Tealgrn",
            )

            fig_related_people.update_layout(
                yaxis=dict(categoryorder="total ascending"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False,
                height=450,
            )

            st.plotly_chart(
                fig_related_people,
                use_container_width=True,
                config={"displayModeBar": False},
            )

        # VÕRGUSTIK

        st.markdown("---")
        st.subheader("Isikute ja fotograafide võrgustikud")

        st.caption(
            "Võrgustik näitab andmestikus nähtavaid "
            "koosesinemisi: kes on samal fotol või "
            "kes on märgitud fotograafi ja pildil oleva isikuna."
        )

        # VÕRGUSTIKU TÜÜP

        network_type = st.radio(
            "Vali võrgustiku tüüp",
            ["Isik–isik: kes on koos pildil", "Fotograaf–isik: kes keda pildistas"],
        )

        # FILTRID

        min_edges = st.slider("Minimaalne seoste arv", 1, 10, 2)

        max_edges = st.slider("Maksimaalne kuvatavate seoste arv", 20, 250, 50)

        # ANDMED

        network_df = isikud_filtered.copy()

        network_df["Isik"] = network_df["Isik"].astype(str).str.strip()

        network_df["Fotograaf"] = network_df["Fotograaf"].astype(str).str.strip()



        G = nx.Graph()

        # ISIK-ISIK VÕRGUSTIK

        if network_type == "Isik–isik: kes on koos pildil":

            grouped_people = network_df.groupby("PID")["Isik"].apply(
                lambda x: sorted(set(x.dropna()))
            )

            pair_counter = {}

            for people in grouped_people:

                if len(people) >= 2:

                    for pair in combinations(people, 2):

                        if pair not in pair_counter:

                            pair_counter[pair] = 0

                        pair_counter[pair] += 1

            sorted_pairs = sorted(
                pair_counter.items(), key=lambda x: x[1], reverse=True
            )

            sorted_pairs = [pair for pair in sorted_pairs if pair[1] >= min_edges][
                :max_edges
            ]

            for (a, b), count in sorted_pairs:

                G.add_node(a, group="isik")

                G.add_node(b, group="isik")

                G.add_edge(a, b, weight=count)

        # FOTOGRAAF-ISIK VÕRGUSTIK

        else:

            edge_counts = (
                network_df.dropna(subset=["Fotograaf", "Isik"])
                .groupby(["Fotograaf", "Isik"])
                .size()
                .reset_index(name="Kordused")
            )

            edge_counts = edge_counts[edge_counts["Kordused"] >= min_edges]

            edge_counts = edge_counts.sort_values("Kordused", ascending=False).head(
                max_edges
            )

            for _, row in edge_counts.iterrows():

                fotograaf = row["Fotograaf"]
                isik = row["Isik"]
                kaal = row["Kordused"]

                G.add_node(fotograaf, group="fotograaf")

                G.add_node(isik, group="isik")

                G.add_edge(fotograaf, isik, weight=kaal)

        # TÜHI VÕRGUSTIK

        if len(G.nodes()) == 0:

            st.info("Valitud filtritega võrgustikku ei leitud.")

        # PYVIS
        else:
            net = Network(
                height="900px", width="100%", bgcolor="#ffffff", font_color="black"
            )

            # SÕLMED
            for node in G.nodes():

                group = G.nodes[node].get("group")

                if group == "fotograaf":

                    net.add_node(node, label=node, color="#199890", size=10)

                else:

                    net.add_node(node, label=node, color="#90d287", size=6)

            # SERVAD

            for source, target, data in G.edges(data=True):

                if source in net.get_nodes() and target in net.get_nodes():

                    net.add_edge(
                        source,
                        target,
                        value=data["weight"],
                        color={
                            "color": "rgba(120,120,120,0.25)",
                            "highlight": "#ff4d4d",
                        },
                    )

            # OPTIONS

            net.set_options("""
            {
              "layout": {
                "improvedLayout": true
              },

              "nodes": {
                "font": {
                "size": 6
                }
              },

              "edges": {
                "smooth": false
              },

              "physics": {
                "enabled": true,
                "stabilization": {
                  "enabled": true,
                  "iterations": 150
                  },

                "barnesHut": {
                  "gravitationalConstant": -5000,
                  "centralGravity": 0.25,
                  "springLength": 70,
                  "springConstant": 0.04,
                  "damping": 0.8
                }
              },

              "interaction": {
                  "hover": true,
                  "navigationButtons": true,
                  "keyboard": true,
                  "hoverConnectedEdges": true,
                  "selectConnectedEdges": true
              }
            }
            """)

            html = net.generate_html()

            components.html(html, height=950)
# ML ABIFUNKTSIOONID

def split_cats(series):

    if series is None:

        return pd.Series(dtype="object")

    return (
        series
        .dropna()
        .astype(str)
        .str.replace(";", ",", regex=False)
        .str.replace("|", ",", regex=False)
        .str.split(",")
        .explode()
        .astype(str)
        .str.strip()
    )


def cat_match(row, manual_col, pred_cols):

    manual = set()

    if pd.notna(row.get(manual_col)):

        manual = {

            x.strip().lower()

            for x in str(row[manual_col])
            .replace(";", ",")
            .replace("|", ",")
            .split(",")

            if x.strip()
        }

    preds = set()

    for col in pred_cols:

        if pd.notna(row.get(col)):

            preds.add(
                str(row[col]).strip().lower()
            )

    return len(manual & preds) > 0


def safe_contains(series, text):

    return (
        series
        .fillna("")
        .astype(str)
        .str.contains(
            text,
            case=False,
            na=False
        )
    )

with tab5:

    st.header(" ML märksõnade analüüs")

    st.markdown("""
    Kaks vaadet: põhifotodega seotud CLIP tulemused (PID olemas) ja kõik CLIP sh `image_only`.
    """)

    st.image(
        "clip_yhe_pildi_selgitus.png",
        use_container_width=True
    )

    st.caption(
        "Näide: CLIP pildi ja tekstikategooriate sobivuse hindamine"
    )

    ml_df = df.copy()

    if "pred_top1" not in ml_df.columns:

        st.warning("ML andmeid ei leitud.")

    else:

        # KPI
        st.markdown("---")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Fotosid filtris",
            f"{len(df):,}"
        )

        clip_total = len(ml_raw)

        clip_pid = (
            ml_raw["PID"]
            .astype(str)
            .str.strip()
            .str.lower()
            .ne("nan")
            .sum()
        )

        image_only = clip_total - clip_pid

        c2.metric(
            "CLIP kokku",
            f"{clip_total:,}"
        )

        c3.metric(
            "CLIP + PID",
            f"{clip_pid:,}"
        )

        c4.metric(
            "Image-only",
            f"{image_only:,}"
        )

        st.markdown("""
        `image_only` : pilt leiti kaustast, aga PID-i ei saanud külge panna.
        """)

        st.markdown("---")

        view_mode = st.radio(
            "Vali ML-vaade",
            [
                "Põhifotodega seotud CLIP",
                "Kõik CLIP, sh image-only"
            ],
            horizontal=True
        )

        if view_mode == "Kõik CLIP, sh image-only":

            graph_df = ml_raw.copy()

        else:

            graph_df = ml_df.copy()

        # TOP KATEGOORIAD
        col1, col2 = st.columns(2)

        # OLEMASOLEVAD KATEGOORIAD
        with col1:

            st.subheader("Olemasolevad kategooriad")

            existing = split_cats(
                graph_df["Märksõna kategooria"]
            ).value_counts().head(20)

            if not existing.empty:

                fig_existing = px.bar(

                    x=existing.values,

                    y=existing.index,

                    orientation="h",

                    labels={
                        "x": "Fotode arv",
                        "y": "Kategooria"
                    },

                    color=existing.values,

                    color_continuous_scale=[
                        "#d9f0ff",
                        "#a6dcef",
                        "#5b8ff9",
                        "#3f37c9"
                    ]
                )

                fig_existing.update_layout(
                    yaxis={"autorange": "reversed"},
                    coloraxis_showscale=False,
                    height=550,
                    paper_bgcolor="white",
                    plot_bgcolor="white"
                )

                st.plotly_chart(
                    fig_existing,
                    use_container_width=True
                )

        # CLIP TOP1
        with col2:

            st.subheader("CLIP top1 kategooriad")

            clip_top = (
                graph_df["pred_top1"]
                .dropna()
                .astype(str)
                .value_counts()
                .head(20)
            )

            if not clip_top.empty:

                fig_clip = px.bar(

                    x=clip_top.values,

                    y=clip_top.index,

                    orientation="h",

                    labels={
                        "x": "Fotode arv",
                        "y": "CLIP kategooria"
                    },

                    color=clip_top.values,

                    color_continuous_scale=[
                        "#f3d1ff",
                        "#d8a8ff",
                        "#c77dff",
                        "#7b2cbf"
                    ]
                )

                fig_clip.update_layout(
                    yaxis={"autorange": "reversed"},
                    coloraxis_showscale=False,
                    height=550,
                    paper_bgcolor="white",
                    plot_bgcolor="white"
                )

                st.plotly_chart(
                    fig_clip,
                    use_container_width=True
                )

        st.markdown("---")

        # KATTUVUS
        st.subheader("ML ja olemasolevate kategooriate kattuvus")

        eval_df = ml_df[
            ml_df["pred_top1"].notna()
            &
            ml_df["Märksõna kategooria"].notna()
        ].copy()

        if not eval_df.empty:

            eval_df["top1_match"] = eval_df.apply(

                lambda r: cat_match(
                    r,
                    "Märksõna kategooria",
                    ["pred_top1"]
                ),

                axis=1
            )

            eval_df["top3_match"] = eval_df.apply(

                lambda r: cat_match(
                    r,
                    "Märksõna kategooria",
                    [
                        "pred_top1",
                        "pred_top2",
                        "pred_top3"
                    ]
                ),

                axis=1
            )

            eval_df["top5_match"] = eval_df.apply(

                lambda r: cat_match(
                    r,
                    "Märksõna kategooria",
                    [
                        "pred_top1",
                        "pred_top2",
                        "pred_top3",
                        "pred_top4",
                        "pred_top5"
                    ]
                ),

                axis=1
            )

            m1, m2, m3 = st.columns(3)

            m1.metric(
                "Top1 kattuvus",
                f"{eval_df['top1_match'].mean() * 100:.1f}%"
            )

            m2.metric(
                "Top3 kattuvus",
                f"{eval_df['top3_match'].mean() * 100:.1f}%"
            )

            m3.metric(
                "Top5 kattuvus",
                f"{eval_df['top5_match'].mean() * 100:.1f}%"
            )

        st.markdown("---")

        # HEATMAP
        st.subheader("Kategooriate kattuvus")

        heat = eval_df.copy()

        heat["manual"] = (
            heat["Märksõna kategooria"]
            .astype(str)
            .str.replace(";", ",", regex=False)
            .str.replace("|", ",", regex=False)
            .str.split(",")
        )

        pairs = heat.explode("manual")

        pairs["manual"] = (
            pairs["manual"]
            .astype(str)
            .str.strip()
        )

        pairs = pairs[
            pairs["manual"] != ""
        ]

        mat = (
            pairs
            .groupby(["manual", "pred_top1"])
            .size()
            .reset_index(name="arv")
        )

        if not mat.empty:

            fig_heat = px.density_heatmap(

                mat,

                x="pred_top1",

                y="manual",

                z="arv",

                color_continuous_scale="Purples",

                labels={
                    "pred_top1": "CLIP top1",
                    "manual": "Olemasolev kategooria",
                    "arv": "Fotode arv"
                }
            )

            fig_heat.update_layout(
                height=650,
                paper_bgcolor="white",
                plot_bgcolor="white"
            )

            st.plotly_chart(
                fig_heat,
                use_container_width=True
            )

        st.markdown("---")

        # TABEL
        st.subheader("ML tulemuste tabel")

        search_ml = st.text_input(
            "🔍 Otsi ML tabelist"
        )

        show_ml = ml_df.copy()

        if search_ml:

            mask = pd.Series(
                False,
                index=show_ml.index
            )

            searchable_cols = [

                "Sisu kirjeldus",
                "Fotograaf",
                "pred_top1",
                "pred_top2",
                "pred_top3",
                "Märksõna kategooria"

            ]

            for col in searchable_cols:

                if col in show_ml.columns:

                    mask |= safe_contains(
                        show_ml[col],
                        search_ml
                    )

            show_ml = show_ml[mask]

        if st.checkbox(
            "Näita ainult ridu, kus top3 ei kattu"
        ):

            show_ml = show_ml[
                ~show_ml.apply(
                    lambda r: cat_match(
                        r,
                        "Märksõna kategooria",
                        [
                            "pred_top1",
                            "pred_top2",
                            "pred_top3"
                        ]
                    ),
                    axis=1
                )
            ]

        ml_cols = [

            c for c in [

                "PID",
                "Fotograaf",
                "Märksõna kategooria",
                "pred_top1",
                "pred_top2",
                "pred_top3",
                "pred_top1_score",
                "confidence_margin_top1_top2",
                "ML top3 koondskoor",
                "ML otsuse tugevus",
                "Sisu kirjeldus",
                "failinimi"

            ]

            if c in show_ml.columns
        ]

        st.markdown(
            f"Näidatakse **{len(show_ml):,}** rida"
        )

        st.dataframe(
            show_ml[ml_cols].head(1000),
            use_container_width=True,
            hide_index=True,
            height=650
        )

        # CSV
        csv_ml = (
            show_ml[ml_cols]
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(
            "⬇️ Lae ML tabel CSV-na",
            data=csv_ml,
            file_name="era_ml_tulemused.csv",
            mime="text/csv"
        )

# ANDMETABELI LISAVEERUD

df_table = df.copy()

df_table["PID"] = df_table["PID"].astype(str).str.strip()

if "Fotograaf (puhastatud)" in master.columns:
    photographers = (
        master[["PID", "Fotograaf (puhastatud)"]]
        .dropna()
        .drop_duplicates()
        .groupby("PID")["Fotograaf (puhastatud)"]
        .apply(lambda x: ", ".join(sorted(set(x.astype(str)))))
        .reset_index()
        .rename(columns={"Fotograaf (puhastatud)": "Fotograaf"})
    )

    df_table = df_table.drop(columns=["Fotograaf"], errors="ignore")
    df_table = df_table.merge(photographers, on="PID", how="left")

if "Žanr" in master.columns:
    genres = master[["PID", "Žanr"]].drop_duplicates("PID")

    df_table = df_table.drop(columns=["Žanr"], errors="ignore")
    df_table = df_table.merge(genres, on="PID", how="left")

if "failinimi" in master.columns:
    filenames = master[["PID", "failinimi"]].drop_duplicates("PID")

    df_table = df_table.drop(columns=["failinimi"], errors="ignore")
    df_table = df_table.merge(filenames, on="PID", how="left")

if not people_df.empty and "Isik" in people_df.columns:
    people_table = (
        people_df[["PID", "Isik"]]
        .dropna()
        .drop_duplicates()
        .groupby("PID")["Isik"]
        .apply(lambda x: ", ".join(sorted(set(x.astype(str)))))
        .reset_index()
        .rename(columns={"Isik": "Isik pildil"})
    )

    df_table = df_table.drop(columns=["Isik pildil"], errors="ignore")
    df_table = df_table.merge(people_table, on="PID", how="left")

if not marksoned.empty and "Märksõna" in marksoned.columns:
    keywords_table = (
        marksoned[["PID", "Märksõna"]]
        .dropna()
        .drop_duplicates()
        .groupby("PID")["Märksõna"]
        .apply(lambda x: ", ".join(sorted(set(x.astype(str)))))
        .reset_index()
        .rename(columns={"Märksõna": "ERA märksõnad"})
    )

    df_table = df_table.drop(columns=["ERA märksõnad"], errors="ignore")
    df_table = df_table.merge(keywords_table, on="PID", how="left")

if not marksona_kategooriad.empty and "Kategooria" in marksona_kategooriad.columns:
    categories_table = (
        marksona_kategooriad[["PID", "Kategooria"]]
        .dropna()
        .drop_duplicates()
        .groupby("PID")["Kategooria"]
        .apply(lambda x: ", ".join(sorted(set(x.astype(str)))))
        .reset_index()
        .rename(columns={"Kategooria": "Märksõna kategooria"})
    )

    df_table = df_table.drop(columns=["Märksõna kategooria"], errors="ignore")
    df_table = df_table.merge(categories_table, on="PID", how="left")

with tab6:
  #ANDMETABEL
    st.subheader("Andmetabel")
    st.caption(
        "Interaktiivne tabel võimaldab filtreeritud ERA fotoandmestikku uurida, "
        "otsida ja eksportida CSV-formaadis."
    )

    column_mapping = {
      "PID": "PID",
      "Aasta": "Aasta",
      "Kihelkond": "Kihelkond",
      "Koht täpsemalt": "Koht täpsemalt",
      "Fotograaf": "Fotograaf",
      "Isik pildil": "Isik pildil",
      "Žanr": "Žanr",
      "Sisu kirjeldus": "Sisu kirjeldus",
      "ERA märksõnad": "ERA märksõnad",
      "Märksõna kategooria": "Märksõna kategooria",
      "pred_top1": "pred_top1",
      "failinimi": "failinimi",
      "Latitude": "Latitude",
      "Longitude": "Longitude",
    }

    available_columns = {
        label: real_col
        for label, real_col in column_mapping.items()
        if real_col in df_table.columns
    }

    selected_labels = st.multiselect(
        "Vali kuvatavad veerud",
        list(available_columns.keys()),
        default=list(available_columns.keys()),
    )

    selected_columns = [
        available_columns[label]
        for label in selected_labels
    ]

    search_query = st.text_input(
        " Otsi (kirjeldus, kihelkond, fotograaf, märksõna)"
    )

    table_df = df_table.copy()

    if search_query:

        mask = pd.Series(False, index=table_df.index)

        searchable_columns = [
            "Sisu kirjeldus",
            "Kihelkond",
            "Koht täpsemalt",
            "Fotograaf",
            "Isik pildil",
            "ERA märksõnad",
            "Märksõna kategooria",
            "pred_top1",
        ]

        for col in searchable_columns:

            if col in table_df.columns:

                mask |= safe_contains(
                    table_df[col],
                    search_query
                )

        table_df = table_df[mask]

    display_df = table_df[selected_columns].copy()

    display_df.columns = selected_labels

    display_df = display_df.fillna("—")

    display_df = display_df.replace(
        ["None", "none", "nan", "NaN", ""],
        "—"
    )

    st.markdown(
        f"Näidatakse **{len(display_df):,}** rida"
    )

    st.dataframe(
        display_df.head(500),
        use_container_width=True,
        hide_index=True,
        height=550,
    )

    if len(display_df) > 500:

        st.caption(
            "Tabelis kuvatakse esimesed 500 rida. "
            "Täpsemaks vaateks kasuta filtreid või otsingut."
        )

    # CSV ALLALAADIMINE

    csv = display_df.to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="Laadi filtreeritud andmestik alla (CSV)",
        data=csv,
        file_name="era_filtreeritud_andmestik.csv",
        mime="text/csv",
    )

    st.caption(
        "Alla laaditakse hetkel filtrite ja otsinguga kuvatud andmestik."
    )

  # ANDMETE KVALITEET
    st.markdown("---")

    st.subheader("Andmete kvaliteet")

    total = len(df)

    with_coords = len(
        df[
            df["Latitude"].notna()
            &
            df["Longitude"].notna()
        ]
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Kõik fotod",
        f"{total:,}"
    )

    col2.metric(
        "Koordinaatidega fotod",
        f"{with_coords:,}"
    )

    col3.metric(
        "Puuduvad koordinaadid",
        f"{total - with_coords:,}"
    )

    percent = round(
        (with_coords / total) * 100,
        1
    ) if total > 0 else 0

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
        "Koordinaatide olemasolu võimaldab kasutada "
        "ruumilist ja kaardipõhist analüüsi."
    )

    # TOP FOTOGRAAFID
    st.markdown("---")
    st.subheader("Kõige sagedasemad fotograafid")

    top_fotograafid = (
        df_table["Fotograaf"]
        .dropna()
        .astype(str)
        .str.split(", ")
        .explode()
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
        plot_bgcolor="white",
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

    st.dataframe(
      missing,
      use_container_width=True,
      hide_index=True,
      height=350
    )


st.markdown("---")
st.caption(
    "ERA Photo Archive Dashboard • Digital Humanities Project • University of Tartu"
)
