import streamlit as st
import pandas as pd
import plotly.express as px
import ssl

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

st.sidebar.header("Filtrid")

year_range = st.sidebar.slider(
    "Aasta",
    int(df["Aasta"].min()),
    int(df["Aasta"].max()),
    (int(df["Aasta"].min()), int(df["Aasta"].max()))
)

df = df[(df["Aasta"] >= year_range[0]) & (df["Aasta"] <= year_range[1])]

selected = st.sidebar.multiselect(
    "Kihelkond",
    sorted(df["Kihelkond"].dropna().unique())
)

if selected:
    df = df[df["Kihelkond"].isin(selected)]

st.subheader("Fotode jaotus ajas")

timeline = df.groupby("Aasta").size().reset_index(name="count")
fig = px.line(timeline, x="Aasta", y="count")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Top kihelkonnad")

top = df["Kihelkond"].value_counts().head(10).reset_index()
top.columns = ["Kihelkond", "Arv"]
fig2 = px.bar(top, x="Kihelkond", y="Arv")
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Andmed")

st.dataframe(df.head(20), use_container_width=True)
