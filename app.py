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

# LEHE STIIL JA SEADISTUSED

# Streamlit lehe üldised seaded
st.set_page_config(page_title="ERA Dashboard", layout="wide")

# põhikonteineri ja pealkirjade stiil
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

# Plotly vaikimisi teema
px.defaults.template = "plotly_white"

# sakkide visuaalne kujundus
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

# TABIDE LOOMINE

# rakenduse põhivaated
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Ajaline analüüs", "Kaart", "Märksõnad", "Isikud", "ML analüüs", "Andmed"]
)

# põhifail koordinaatidega fotode jaoks
df = pd.read_excel(
    "ERA_fotod_250426.xlsx",
    sheet_name="fotod_koordinaatidega"
)

# eemaldab veerunimedest liigsed tühikud
df.columns = df.columns.str.strip()

# mastertabel kõigi põhiandmetega
master = pd.read_excel(
    "ERA_fotod_250426.xlsx",
    sheet_name="fotod_master"
)

# eemaldab veerunimedest liigsed tühikud
master.columns = master.columns.str.strip()

# ML ANDMED

# CLIP mudeli tulemuste laadimine
ml_data = pd.read_excel(
    "era_clip_KOIK_pildid_sigmoid.xlsx"
)

# algsete ML andmete koopia
ml_raw = ml_data.copy()

# veerunimede puhastamine
ml_data.columns = (
    ml_data.columns
    .astype(str)
    .str.strip()
)

# veerunimede ühtlustamine
ml_data = ml_data.rename(columns={
    "true_clusters": "Märksõna kategooria",
    "top1_score": "pred_top1_score",
    "margin_top1_top2": "confidence_margin_top1_top2"
})

# uuendatud ML andmete koopia
ml_raw = ml_data.copy()

# CLIP METRICS

# ML mudeli kvaliteedinäitajate laadimine
try:

    ml_metrics = pd.read_excel(
        "era_clip_KOIK_pildid_sigmoid.xlsx",
        sheet_name="cluster_metrics"
    )

    # veerunimede puhastamine
    ml_metrics.columns = (
        ml_metrics.columns
        .astype(str)
        .str.strip()
    )

# kui metrics lehte ei leita, luuakse tühi tabel
except Exception:

    ml_metrics = pd.DataFrame()

# ML tabeli veerunimede puhastamine
ml_data.columns = (
    ml_data.columns
    .astype(str)
    .str.strip()
)

# PID väärtuste ühtlustamine merge jaoks
ml_data["PID"] = (
    ml_data["PID"]
    .astype(str)
    .str.strip()
)

# ainult vajalikud ML veerud

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

# kontrollitakse, millised vajalikud veerud on olemas
existing_ml_cols = [

    c for c in ml_columns
    if c in ml_data.columns

]

# alles jäetakse ainult vajalikud veerud ja eemaldatakse duplikaadid PID järgi
ml_data = (
    ml_data[existing_ml_cols]
    .drop_duplicates(subset=["PID"])
)

# MERGE

# PID väärtuste ühtlustamine enne tabelite ühendamist
df["PID"] = (
    df["PID"]
    .astype(str)
    .str.strip()
)

# ML andmete ühendamine põhiandmestikuga
df = df.merge(
    ml_data,
    on="PID",
    how="left"
)

# PID väärtuste puhastamine mõlemas tabelis
df["PID"] = df["PID"].astype(str).str.strip()
master["PID"] = master["PID"].astype(str).str.strip()

# master tabelist vajalike veergude valimine
master_small = master[
    [
        "PID",
        "Aasta",
        "Fotograaf (puhastatud)",
        "Žanr",
        "failinimi"
    ]
].drop_duplicates(subset=["PID"])

# fotograafi veeru ümbernimetamine
master_small = master_small.rename(
    columns={
        "Fotograaf (puhastatud)": "Fotograaf"
    }
)

# vanade veergude eemaldamine enne uut merge'i
df = df.drop(
    columns=[
        "Aasta",
        "Fotograaf",
        "Žanr",
        "failinimi"
    ],
    errors="ignore"
)

# master tabeli andmete ühendamine põhiandmestikuga
df = df.merge(
    master_small,
    on="PID",
    how="left"
)

# võimalike duplikaatide eemaldamine
df = df.drop_duplicates()

# aasta teisendamine numbriliseks väärtuseks
df["Aasta"] = (
    pd.to_numeric(df["Aasta"], errors="coerce")
    .apply(lambda x: int(x) if pd.notna(x) else None)
)

# koordinaatide teisendamine numbriliseks
df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

# kontroll, kas fotol on olemas mõlemad koordinaadid
df["koordinaadid_leitud"] = (
    df["Latitude"].notna()
    &
    df["Longitude"].notna()
)

# kaardi jaoks piirkonnanime puhastamine
df["kaardi_piirkond"] = (
    df["Kihelkond"]
    .astype(str)
    .str.strip()
)

# LAEN ISIKUD FOTOL TABELI

# fotodel olevate isikute tabeli laadimine
people_df = pd.read_excel(
    "ERA_fotod_250426.xlsx",
    sheet_name="isikud_fotol_pikk"
)

# veerunimede puhastamine
people_df.columns = people_df.columns.str.strip()

# PID väärtuste ühtlustamine
people_df["PID"] = (
    people_df["PID"]
    .astype(str)
    .str.strip()
)


with tab1:

    #ANDMED

    # SSL kontrolli lõdvendamine failide laadimiseks
    ssl._create_default_https_context = ssl._create_unverified_context

    # Exceli faili asukoht
    xlsx_path = "ERA_fotod_250426.xlsx"

    # avalehe pealkiri
    st.title("ERA Fotoarhiivi analüütiline juhtlaud")

    # projekti lühikirjeldus
    st.caption("Kultuuriandmete projekt · University of Tartu")

    # dashboardi sissejuhatav kirjeldus
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

    # eraldusjoon
    st.markdown("---")

    # SIDE BAR

    # filtrite ploki pealkiri
    st.sidebar.header("Filtrid")

    # FILTRITE EEMALDAMINE

    # nupp kõikide aktiivsete filtrite lähtestamiseks
    if st.sidebar.button("Eemalda kõik filtrid"):

        # taastab kogu aastavahemiku
        st.session_state["year_range"] = (
            int(df["Aasta"].min()),
            int(df["Aasta"].max()),
        )

        # eemaldab kihelkonna filtri
        st.session_state["kihelkond_filter"] = []

        # eemaldab asukoha filtri
        st.session_state["asukoht_filter"] = []

        # laeb rakenduse uuesti
        st.rerun()

    # AASTA SIDEBAR

    # minimaalse ja maksimaalse aasta leidmine
    year_min = int(df["Aasta"].dropna().min())
    year_max = int(df["Aasta"].dropna().max())

    # aastavahemiku slider sidebaris
    year_range = st.sidebar.slider(
        "Aasta",
        year_min,
        year_max,
        (year_min, year_max),
        key="year_range"
    )

    # andmete filtreerimine valitud aastavahemiku järgi
    df = df[
        (
            (df["Aasta"] >= year_range[0])
            &
            (df["Aasta"] <= year_range[1])
        )
        |
        (df["Aasta"].isna())
    ]

    # KIHELKOND SIDEBAR

    # kihelkondade valik sidebaris
    selected = st.sidebar.multiselect(
        "Kihelkond",

        # unikaalsete kihelkondade nimekiri
        sorted(
            df["Kihelkond"]
            .dropna()
            .astype(str)
            .unique()
        ),

        key="kihelkond_filter",
    )

    # andmete filtreerimine valitud kihelkondade järgi
    if selected:

        df = df[
            df["Kihelkond"].isin(selected)
        ]

    # ASUKOHT SIDEBAR

    # asulate valik sidebaris
    selected_places = st.sidebar.multiselect(
        "Asula",

        # unikaalsete asulate nimekiri
        sorted(
            df["asula"]
            .dropna()
            .astype(str)
            .unique()
        ),

        key="asukoht_filter",
    )

    # andmete filtreerimine valitud asulate järgi
    if selected_places:

        df = df[
            df["asula"].isin(selected_places)
        ]

    #### KUJUTATUD ANDMED ###

    # FOTOGRAAF SIDEBAR

    # hetkel filtreeritud PID väärtused
    filtered_pids = (
        df["PID"]
        .astype(str)
        .str.strip()
        .unique()
    )

    # ainult nende fotodega seotud isikute tabel
    people_filtered_photographers = people_df[
        people_df["PID"]
        .astype(str)
        .str.strip()
        .isin(filtered_pids)
    ].copy()

    # kõik unikaalsed fotograafid
    all_photographers = sorted(
        people_filtered_photographers["Fotograaf"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
    )

    # fotograafi valik sidebaris
    selected_photographers = st.sidebar.multiselect(
        "Fotograaf",
        all_photographers
    )

    # filtreerimine valitud fotograafide järgi
    if selected_photographers:

        # leitakse kõik valitud fotograafidega seotud PID-id
        selected_pids = (
            people_filtered_photographers[
                people_filtered_photographers["Fotograaf"].isin(
                    selected_photographers
                )
            ]["PID"]
            .astype(str)
            .str.strip()
        )

        # jäetakse alles ainult valitud fotograafide fotod
        df = df[
            df["PID"]
            .astype(str)
            .str.strip()
            .isin(selected_pids)
        ]

    # ISIK FOTOL SIDEBAR

    # hetkel filtreeritud PID väärtused
    filtered_pids = (
        df["PID"]
        .astype(str)
        .str.strip()
        .unique()
    )

    # ainult filtreeritud fotodega seotud isikud
    people_filtered = people_df[
        people_df["PID"]
        .astype(str)
        .str.strip()
        .isin(filtered_pids)
    ].copy()

    # kõik unikaalsed isikud
    all_people = sorted(
        people_filtered["Isik"]
        .dropna()
        .astype(str)
        .unique()
    )

    # isikute valik sidebaris
    selected_people = st.sidebar.multiselect(
        "Isik fotol",
        all_people
    )

    # filtreerimine valitud isikute järgi
    if selected_people:

        # leitakse kõik valitud isikutega seotud PID-id
        selected_pids = (
            people_filtered[
                people_filtered["Isik"].isin(selected_people)
            ]["PID"]
            .astype(str)
            .str.strip()
        )

        # jäetakse alles ainult valitud isikutega fotod
        df = df[
            df["PID"]
            .astype(str)
            .str.strip()
            .isin(selected_pids)
        ]

    # MÄRKSÕNADE LAADIMINE

    # funktsioon märksõnade tabeli laadimiseks
    @st.cache_data
    def load_marksonad(xlsx_path):

        try:

            # märksõnade tabeli laadimine Excelist
            marksoned = pd.read_excel(
                xlsx_path,
                sheet_name="märksõnad_pikk"
            )

        # kui tabelit ei leita, tagastatakse tühi dataframe
        except Exception:

            return pd.DataFrame(
                columns=["PID", "Märksõna"]
            )

        # veerunimede puhastamine
        marksoned.columns = (
            marksoned.columns
            .astype(str)
            .str.strip()
        )

        # puuduv PID veerg luuakse vajadusel
        if "PID" not in marksoned.columns:

            marksoned["PID"] = pd.NA

        # puuduv märksõna veerg luuakse vajadusel
        if "Märksõna" not in marksoned.columns:

            marksoned["Märksõna"] = pd.NA

        # PID väärtuste puhastamine
        marksoned["PID"] = (
            marksoned["PID"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # märksõnade puhastamine
        marksoned["Märksõna"] = (
            marksoned["Märksõna"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # eemaldatakse tühjad märksõnad
        marksoned = marksoned[
            marksoned["Märksõna"] != ""
        ]

        # tagastatakse puhastatud märksõnade tabel
        return marksoned

    # MÄRKSÕNADE KATEGOORIAD

    # funktsioon märksõnade kategooriate laadimiseks
    @st.cache_data
    def load_marksona_kategooriad():

        try:

            # ML märksõnade faili laadimine
            ml_df = pd.read_excel(
                "ERA_märksõnad_ML.xlsx"
            )

        # kui faili ei leita, tagastatakse tühi dataframe
        except Exception:

            return pd.DataFrame(
                columns=["Märksõna", "Kategooria"]
            )

        # veerunimede puhastamine
        ml_df.columns = (
            ml_df.columns
            .astype(str)
            .str.strip()
        )

        # puuduv PID veerg luuakse vajadusel
        if "PID" not in ml_df.columns:

            ml_df["PID"] = pd.NA

        # puuduv märksõna veerg luuakse vajadusel
        if "Märksõna" not in ml_df.columns:

            ml_df["Märksõna"] = pd.NA

        # puuduv kategooria veerg luuakse vajadusel
        if "Märksõna2" not in ml_df.columns:

            ml_df["Märksõna2"] = pd.NA

        # kategooria veeru ümbernimetamine
        ml_df = ml_df.rename(
            columns={
                "Märksõna2": "Kategooria"
            }
        )

        # PID väärtuste puhastamine
        ml_df["PID"] = (
            ml_df["PID"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # märksõnade puhastamine
        ml_df["Märksõna"] = (
            ml_df["Märksõna"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # kategooriate puhastamine
        ml_df["Kategooria"] = (
            ml_df["Kategooria"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        # eemaldatakse tühjad märksõnad ja kategooriad
        ml_df = ml_df[
            (ml_df["Märksõna"] != "")
            &
            (ml_df["Kategooria"] != "")
        ]

        # tagastatakse puhastatud kategooriate tabel
        return ml_df

    # MÄRKSÕNADE VALIKUD

    # funktsioon sidebari märksõnade valikute loomiseks
    def get_marksona_options(marksoned, current_df=None):

        # kontrollitakse, kas olemas on filtreeritud dataframe
        if current_df is not None and "PID" in current_df.columns:

            # hetkel aktiivsete PID väärtuste kogumine
            current_pids = set(
                current_df["PID"]
                .dropna()
                .astype(str)
                .unique()
            )

            # märksõnade filtreerimine aktiivsete PID-ide järgi
            filtered_marksoned = marksoned[
                marksoned["PID"].isin(current_pids)
            ]

        else:

            # kasutatakse kogu märksõnade tabelit
            filtered_marksoned = marksoned

        # märksõnade nimekirja loomine sageduse järgi
        options = (
            filtered_marksoned["Märksõna"]
            .dropna()
            .astype(str)
            .value_counts()
            .index
            .tolist()
        )

        # tagastatakse märksõnade valikud
        return options


    # MÄRKSÕNADE FILTREERIMINE

    # funktsioon fotode filtreerimiseks märksõnade järgi
    def filter_by_marksonad(
        fotod_df,
        marksoned_df,
        selected_marksonad,
        logic="OR"
    ):

        # kui märksõnu ei valitud, tagastatakse kogu dataframe
        if not selected_marksonad:

            return fotod_df

        # OR loogika:
        # foto peab sisaldama vähemalt ühte valitud märksõna
        if logic == "OR":

            matched_pids = set(

                marksoned_df[
                    marksoned_df["Märksõna"]
                    .isin(selected_marksonad)
                ]["PID"]

                .dropna()
                .astype(str)
                .unique()
            )

        # AND loogika:
        # foto peab sisaldama kõiki valitud märksõnu
        else:

            matched_pids = None

            # vaadatakse iga märksõna eraldi
            for keyword in selected_marksonad:

                # leitakse kõik PID-id,
                # kus see märksõna esineb
                keyword_pids = set(

                    marksoned_df[
                        marksoned_df["Märksõna"] == keyword
                    ]["PID"]

                    .dropna()
                    .astype(str)
                    .unique()
                )

                # esimese märksõna PID-id
                if matched_pids is None:

                    matched_pids = keyword_pids

                # leitakse ühised PID-id
                else:

                    matched_pids = (
                        matched_pids
                        &
                        keyword_pids
                    )

            # kui vasteid ei leitud
            if matched_pids is None:

                matched_pids = set()

        # jäetakse alles ainult sobivad fotod
        filtered_df = fotod_df[
            fotod_df["PID"]
            .astype(str)
            .isin(matched_pids)
        ]

        # tagastatakse filtreeritud dataframe
        return filtered_df

    # MÄRKSÕNADE SIDEBAR

    # märksõnade filtri pealkiri sidebaris
    st.sidebar.markdown("## Märksõnad")

    # märksõnade tabeli laadimine
    marksoned = load_marksonad(xlsx_path)

    # märksõnade kategooriate tabeli laadimine
    marksona_kategooriad = load_marksona_kategooriad()

    # KATEGOORIA FILTER

    # hetkel filtreeritud PID väärtuste kogumine
    filtered_pids = set(
        df["PID"]
        .dropna()
        .astype(str)
        .unique()
    )

    # ainult aktiivsete fotodega seotud kategooriad
    filtered_categories_df = marksona_kategooriad[
        marksona_kategooriad["PID"]
        .astype(str)
        .isin(filtered_pids)
    ]

    # kõik unikaalsed märksõna kategooriad
    all_categories = sorted(
        filtered_categories_df["Kategooria"]
        .dropna()
        .astype(str)
        .unique()
    )

    # kategooriate valik sidebaris
    selected_categories = st.sidebar.multiselect(
        "Märksõna kategooria",
        all_categories
    )

        # MÄRKSÕNA VALIKUD

    # märksõnade valikute loomine aktiivsete filtrite põhjal
    marksona_options = get_marksona_options(
        marksoned,
        current_df=df
    )

    # kui kategooriad on valitud
    if selected_categories:

        # leitakse kõik märksõnad,
        # mis kuuluvad valitud kategooriatesse
        allowed_keywords = (

            marksona_kategooriad[
                marksona_kategooriad["Kategooria"]
                .isin(selected_categories)
            ]["Märksõna"]

            .dropna()
            .astype(str)
            .unique()
        )

        # jäetakse alles ainult sobivad märksõnad
        marksona_options = [
            x for x in marksona_options
            if x in allowed_keywords
        ]

        # leitakse kõik PID-id,
        # mis sisaldavad valitud kategooriaid
        matched_pids = (

            marksona_kategooriad[
                marksona_kategooriad["Kategooria"]
                .isin(selected_categories)
            ]["PID"]

            .dropna()
            .astype(str)
            .str.strip()
            .unique()
        )

        # filtreeritakse andmestik valitud kategooriate järgi
        df = df[
            df["PID"]
            .astype(str)
            .str.strip()
            .isin(matched_pids)
        ]

    # MÄRKSÕNA FILTER

    # märksõnade valik sidebaris
    selected_marksonad = st.sidebar.multiselect(
        "Vali märksõnad",

        # võimalikud märksõnade valikud
        options=marksona_options,

        # maksimaalselt 5 märksõna
        max_selections=5,

        placeholder="Vali märksõnad",
    )

    # kui valitud on rohkem kui üks märksõna
    if len(selected_marksonad) > 1:

        # kasutaja saab valida OR või AND loogika
        marksona_logic = st.sidebar.radio(
            "Märksõnade loogika",
            options=["OR", "AND"],
            horizontal=True
        )

    else:

        # ühe märksõna puhul kasutatakse automaatselt OR loogikat
        marksona_logic = "OR"

    # andmete filtreerimine märksõnade järgi
    df = filter_by_marksonad(

        fotod_df=df,

        marksoned_df=marksoned,

        selected_marksonad=selected_marksonad,

        logic=marksona_logic,
    )

    # KPI CARDS

    # dashboardi põhinäitajate loomine
    cards = [

        # fotode koguarv
        ("Fotode arv", f"{len(df):,}"),

        # unikaalsete kihelkondade arv
        ("Kihelkondi", df["Kihelkond"].nunique()),

        # unikaalsete asukohtade arv
        ("Asukohti", df["Koht täpsemalt"].nunique()),

        # andmestiku ajavahemik
        (
            "Ajavahemik",

            (
                f"{int(df['Aasta'].dropna().min())}"
                f"–"
                f"{int(df['Aasta'].dropna().max())}"

                if not df["Aasta"].dropna().empty

                else "Puudub"
            ),
        ),

        # koordinaatidega fotode arv
        (
            "Koordinaatidega",
            f"{df['koordinaadid_leitud'].sum():,}"
        ),
    ]

    # KPI kaartide HTML konteiner
    cards_html = """
    <div style="
        display:flex;
        gap:22px;
        flex-wrap:wrap;
        margin-top:25px;
    ">
    """

    # iga KPI kaardi loomine
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

            <!-- KPI nimetus -->
            <div style="
                font-family: Inter, sans-serif;
                font-size:14px;
                color:#7a7a7a;
                margin-bottom:10px;
            ">
                {label}
            </div>

            <!-- KPI väärtus -->
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

    # HTML konteineri sulgemine
    cards_html += "</div>"

    # KPI kaartide kuvamine Streamlitis
    components.html(
        cards_html,
        height=200,
        scrolling=False
    )

    # eraldusjoon
    st.markdown("---")

        # FOTODE JAOTUS AJAS

    # sektsiooni pealkiri
    st.markdown("### Fotode jaotus aastate lõikes")

    # sektsiooni kirjeldus
    st.caption(
        "Graafik näitab, kuidas fotode arv muutus aastate jooksul."
    )

    # fotode grupeerimine aastate järgi
    photos_by_year = (
        df
        .groupby("Aasta")
        .size()
        .reset_index(name="Fotode arv")
    )

    # pinddiagrammi loomine
    fig = px.area(

        photos_by_year,

        x="Aasta",

        y="Fotode arv",

        # sujuv joon
        line_shape="spline"
    )

    # joone ja täitevärvi kujundus
    fig.update_traces(

        line=dict(
            color="#5B8FF9",
            width=3
        ),

        fillcolor="rgba(91,143,249,0.18)"
    )

    # graafiku üldine kujundus
    fig.update_layout(

        height=520,

        paper_bgcolor="white",
        plot_bgcolor="white",

        margin=dict(
            l=20,
            r=20,
            t=20,
            b=20
        ),

        # x-telje seadistused
        xaxis=dict(
            title="Aasta",
            showgrid=False,
            zeroline=False
        ),

        # y-telje seadistused
        yaxis=dict(
            title="Fotode arv",
            gridcolor="rgba(0,0,0,0.06)",
            zeroline=False
        ),

        # ühine hover aastate lõikes
        hovermode="x unified",
    )

    # graafiku kuvamine konteineris
    with st.container():

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # KIHELKONDADE AJALINE ANALÜÜS

    # sektsiooni pealkiri
    st.markdown("### Kihelkonnad ajas")

    # sektsiooni kirjeldus
    st.caption(
        "Fotode arvu muutus ajas valitud kihelkondades."
    )

    # kõik olemasolevad kihelkonnad valiku jaoks
    all_kih = sorted(

        df["Kihelkond"]

        .dropna()

        .astype(str)

        .unique()
    )

    # vaikimisi kuvatavad top 4 kihelkonda
    top_kih = (

        df["Kihelkond"]

        .value_counts()

        .head(4)

        .index

        .tolist()
    )

    # kihelkondade valik kasutajale
    selected_kih = st.multiselect(

        "Vali kuni 4 kihelkonda",

        all_kih,

        default=top_kih,

        max_selections=4,
    )

    # kontroll, kas vähemalt üks kihelkond on valitud
    if selected_kih:

        # andmete filtreerimine valitud kihelkondade järgi
        timeline_df = (

            df[
                df["Kihelkond"].isin(selected_kih)
            ]

            .groupby([
                "Aasta",
                "Kihelkond"
            ])

            .size()

            .reset_index(name="Fotode arv")
        )

        # joondiagrammi loomine
        fig_timeline = px.line(

            timeline_df,

            x="Aasta",

            y="Fotode arv",

            color="Kihelkond",

            # sujuvad jooned
            line_shape="spline",

            # värvipalett
            color_discrete_sequence=px.colors.qualitative.Set2,
        )

        # joonte kujundus
        fig_timeline.update_traces(

            line=dict(width=2),
        )

        # graafiku üldine kujundus
        fig_timeline.update_layout(

            paper_bgcolor="white",

            plot_bgcolor="white",

            height=500,

            margin=dict(
                l=20,
                r=20,
                t=30,
                b=20
            ),

            # hover info kogu x-telje lõikes
            hovermode="x unified",

            # legendi kuvamine
            showlegend=True,
        )

    # graafiku kuvamine
    st.plotly_chart(

        fig_timeline,

        use_container_width=True
    )

        # KÕIGE SAGEDASEMATE ASUKOHTADE ANALÜÜS

    # sektsiooni pealkiri
    st.markdown("### Kõige sagedasemad asukohad")

    # sektsiooni kirjeldus
    st.caption(
        "Top 10 kõige sagedamini esinevat täpset asukohta."
    )

    # top 10 kõige sagedasemat asukohta
    top_places = (

        df["Koht täpsemalt"]

        .dropna()

        .value_counts()

        .head(10)

        .reset_index(name="Fotode arv")
    )

    # tulpdiagrammi loomine
    fig_places = px.bar(

        top_places,

        x="Koht täpsemalt",

        y="Fotode arv",

        # värv sõltub fotode arvust
        color="Fotode arv",

        # värviskeem
        color_continuous_scale="Tealgrn",
    )

    # graafiku üldine kujundus
    fig_places.update_layout(

        paper_bgcolor="white",

        plot_bgcolor="white",

        height=350,

        margin=dict(
            l=20,
            r=20,
            t=30,
            b=20
        ),

        # fondi suurus
        font=dict(size=14),

        # peida värviskaala
        coloraxis_showscale=False,
    )

    # tulpade ja hoveri kujundus
    fig_places.update_traces(

        # eemaldab tulpade äärejooned
        marker_line_width=0,

        # hover info
        hovertemplate=
            "<b>%{x}</b><br>"
            "Fotode arv: %{y}"
            "<extra></extra>",
    )

    # graafiku kuvamine
    st.plotly_chart(
        fig_places,
        use_container_width=True
    )

        # FOTODE JAOTUS PIIRKONDADE JÄRGI

    # eraldusjoon sektsioonide vahel
    st.markdown("---")

    # sektsiooni pealkiri
    st.subheader("Fotode jaotus piirkondade järgi")

    # sektsiooni kirjeldus
    st.caption(
        "Diagramm näitab, millistes kihelkondades leidub kõige rohkem fotosid."
    )

    # top 10 kõige sagedasemat kihelkonda
    region_counts = (

        df["Kihelkond"]

        .value_counts()

        .head(10)

        .reset_index()
    )

    # veergude nimede ümbernimetamine
    region_counts.columns = [
        "Kihelkond",
        "Fotode arv"
    ]

    # sorteerimine väiksemast suuremani
    region_counts = region_counts.sort_values(

        by="Fotode arv",

        ascending=True
    )

    # horisontaalse tulpdiagrammi loomine
    fig_regions = px.bar(

        region_counts,

        x="Fotode arv",

        y="Kihelkond",

        # horisontaalne diagramm
        orientation="h",

        # tekst tulpade peale
        text="Fotode arv",

        # värv sõltub fotode arvust
        color="Fotode arv",

        # värviskeem
        color_continuous_scale=[
            "#D7EFE2",
            "#9AD7C3",
            "#52B69A",
            "#1B6F78"
        ],
    )

    # tulpade kujundus
    fig_regions.update_traces(

        # tekst väljaspool tulpa
        textposition="outside",

        # eemaldab tulpade äärejooned
        marker_line_width=0,

        # hover info
        hovertemplate=(

            "<b>%{y}</b><br>"

            "Fotode arv: %{x}"

            "<extra></extra>"
        ),
    )

    # graafiku üldine kujundus
    fig_regions.update_layout(

        height=540,

        plot_bgcolor="white",

        paper_bgcolor="white",

        # peida värviskaala
        coloraxis_showscale=False,

        margin=dict(
            t=20,
            l=20,
            r=10,
            b=20
        ),

        # telgede pealkirjad
        xaxis_title="Fotode arv",

        yaxis_title="Kihelkond",

        # fondi suurus
        font=dict(size=15),

        # x-telje seadistused
        xaxis=dict(

            showgrid=True,

            gridcolor="rgba(0,0,0,0.06)",

            zeroline=False,
        ),

        # y-telje seadistused
        yaxis=dict(
            showgrid=False,
        ),
    )

    # graafiku kuvamine
    st.plotly_chart(

        fig_regions,

        use_container_width=True,

        # peida plotly tööriistariba
        config={
            "displayModeBar": False
        }
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

            if c == "Aasta":

                val = str(int(float(row[c])))

            else:

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

    geo_names.update({
        "Kihnu",
        "Tartu",
        "Setumaa",
        "Petserimaa",
        "Pärnu",
        "Valga"
    })

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

            src["kaardi_piirkond"] = (
                src["kaardi_piirkond"]
                .replace({
                    "Tartu linn": "Tartu",
                    "Tallinna linn": "Tallinn",
                    "Petseri": "Petserimaa"
                })
            )

            src = src[
                ~src["kaardi_piirkond"]
                .str.match(r"^-?\d+(\.\d+)?$", na=False)
            ]
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

            missing_regions = sorted(
                set(counts["kaardi_piirkond"]) - set(geo_names)
            )

            st.write(missing_regions)

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

                # ERALDI PUNKTID PUUDUVATELE PIIRKONDADELE

                special_coords = {

                    "Kihnu": (58.138, 24.024),

                    "Tartu": (58.378, 26.729),

                    "Setumaa": (57.95, 27.55),

                    "Petserimaa": (57.80, 27.55),

                    "Pärnu": (58.385, 24.497),

                    "Valga": (57.777, 26.047)
                }

                special_regions = (
                    src[
                        src["kaardi_piirkond"]
                        .isin(special_coords.keys())
                    ]
                    .groupby("kaardi_piirkond")
                    .size()
                    .reset_index(name="Fotode arv")
                )

                special_regions["lat"] = (
                    special_regions["kaardi_piirkond"]
                    .map(lambda x: special_coords[x][0])
                )

                special_regions["lon"] = (
                    special_regions["kaardi_piirkond"]
                    .map(lambda x: special_coords[x][1])
                )

                fig.add_trace(
                    go.Scattermapbox(

                        lat=special_regions["lat"],
                        lon=special_regions["lon"],

                        mode="markers+text",

                        marker=dict(
                            size=35,
                            color="rgba(0,128,128,0.5)"
                        ),

                        text=special_regions["kaardi_piirkond"],
                        textposition="top center",

                        customdata=[
                            [row["kaardi_piirkond"], row["Fotode arv"]]
                            for _, row in special_regions.iterrows()
                        ],

                        hovertemplate=
                            "kaardi_piirkond=%{customdata[0]}<br>"
                            "Fotode arv=%{customdata[1]}"
                            "<extra></extra>",

                        name="Eraldi kuvatud piirkonnad"
                    )
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

        detail_df = df.copy()

        detail_df["kaardi_piirkond"] = (
            detail_df["kaardi_piirkond"]
            .astype(str)
            .str.strip()
            .replace({
                "Tartu linn": "Tartu",
                "Tallinna linn": "Tallinn",
                "Petseri": "Petserimaa"
            })
        )

        # FILTER
        det = detail_df[
            detail_df["kaardi_piirkond"]
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

        # FOTOGRAAFIDE ARV

        det_pids = (
            det["PID"]
            .astype(str)
            .str.strip()
            .unique()
        )

        det_photographers = people_df[
            people_df["PID"]
            .astype(str)
            .str.strip()
            .isin(det_pids)
        ]

        photographer_count = (
            det_photographers["Fotograaf"]
            .dropna()
            .astype(str)
            .str.strip()
            .nunique()
        )

        k4.metric(
            "Fotograafe",
            photographer_count
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

          det_pids = (
              det["PID"]
              .astype(str)
              .str.strip()
              .unique()
          )

          det_photographers = people_df[
              people_df["PID"]
              .astype(str)
              .str.strip()
              .isin(det_pids)
          ]

          ft = (

              det_photographers

              .dropna(subset=["Fotograaf", "PID"])

              .assign(
                  Fotograaf=lambda x:
                  x["Fotograaf"]
                  .astype(str)
                  .str.strip()
              )

              .groupby("Fotograaf")["PID"]

              .nunique()

              .sort_values(ascending=False)

              .head(8)

              .reset_index(name="Arv")
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

            net.options = {
                "layout": {
                  "improvedLayout": True
                },

              "nodes": {
                  "font": {
                      "size": 6
                  }
              },

              "edges": {
                "smooth": False
              },

              "physics": {
                "enabled": True,
                "stabilization": {
                  "enabled": True,
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
                  "hover": True,
                  "navigationButtons": True,
                  "keyboard": True,
                  "hoverConnectedEdges": True,
                  "selectConnectedEdges":True
              }
            }

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
        )

        clip_pid = clip_pid[
            ~clip_pid.isin([
                "",
                "nan",
                "None",
                "none",
                "NULL",
                "null",
                "<NA>"
            ])
        ].count()

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

            manual_col = "Märksõna kategooria"

        else:

            graph_df = ml_df.copy()

            manual_col = "Märksõna kategooria"

        # TOP KATEGOORIAD
        col1, col2 = st.columns(2)

        # OLEMASOLEVAD KATEGOORIAD
        with col1:

            st.subheader("Olemasolevad kategooriad")
            if manual_col in graph_df.columns:
                existing = split_cats(
                    graph_df[manual_col]
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

        if manual_col in graph_df.columns:

            eval_df = graph_df[
                graph_df["pred_top1"].notna()
                &
                graph_df[manual_col].notna()
            ].copy()

        else:

            eval_df = pd.DataFrame()

        if not eval_df.empty:

            eval_df["top1_match"] = eval_df.apply(

                lambda r: cat_match(
                    r,
                    manual_col,
                    ["pred_top1"]
                ),

                axis=1
            )

            eval_df["top3_match"] = eval_df.apply(

                lambda r: cat_match(
                    r,
                    manual_col,
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
                    manual_col,
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
            heat[manual_col]
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

        # ══════════════════ CLIP KVALITEET KATEGOORIATE KAUPA ═══════════════════════

    if not ml_metrics.empty:

        st.subheader(" CLIP mudeli kvaliteet kategooriate kaupa")

        st.markdown("""
    See graafik näitab, milliste märksõnakategooriate puhul töötab CLIP mudel paremini.
    Mida kõrgem väärtus, seda täpsemalt suutis mudel vastavat kategooriat ennustada.
    """)

        mtr = ml_metrics.copy()

        mtr.columns = (
            mtr.columns
            .astype(str)
            .str.strip()
        )

        mc2 = next(
            (
                c for c in [
                    "f1_top3",
                    "top3_f1",
                    "hit_any_top3",
                    "top3_hit_rate"
                ]
                if c in mtr.columns
            ),
            None
        )

        cc3 = next(
            (
                c for c in [
                    "cluster",
                    "kategooria",
                    "Märksõna kategooria"
                ]
                if c in mtr.columns
            ),
            None
        )

        if mc2 and cc3:

            mtr[mc2] = pd.to_numeric(
                mtr[mc2],
                errors="coerce"
            )

            fig = px.bar(

                mtr.dropna(subset=[mc2]).sort_values(mc2),

                x=mc2,
                y=cc3,

                orientation="h",

                title="Milliste kategooriate puhul CLIP paremini töötab?"
            )

            fig.update_layout(
                height=550
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

# ═════════════════════════════════════════════════════════════════════════════

        # TABEL
        st.subheader("ML tulemuste tabel")

        search_ml = st.text_input(
            "🔍 Otsi ML tabelist"
        )

        show_ml = graph_df.copy()

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
                        manual_col,
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
