# ERA Photo Archive Dashboard

Interactive Digital Humanities dashboard for exploring the ERA  photo archive dataset.

## Features

- Interactive timeline analysis
- Historical parish (kihelkond) comparison
- Geographical visualization on an interactive map
- Keyword analysis
- ML-based keyword suggestions (CLIP prototype)
- Data quality overview
- Downloadable filtered dataset

## Technologies Used

- Python
- Streamlit
- Pandas
- Plotly
- GeoPandas

## Dataset

The project uses ERA photo archive metadata containing:
- photo descriptions
- locations
- parishes (kihelkonnad)
- years
- coordinates

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
