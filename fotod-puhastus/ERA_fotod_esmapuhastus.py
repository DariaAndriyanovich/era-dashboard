# ERA fotode andmestiku esmane puhastus ja tabeliteks jagamine
# ------------------------------------------------------------
# See skript koondab algsed MF_*.csv failid üheks tööfailiks,
# teeb esmaste väljade korrastuse, harutab märksõnad eraldi veergudeks,
# tuletab failinime ning loob lõpuks analüüsiks mugavad tabelid:
# 1) fotod_master
# 2) isikud_fotol_pikk
# 3) märksõnad_pikk
#
# Märkus: asukohtade osa on siin teadlikult lihtsamaks tehtud.
# Täpsem kohanimede, isikunimede ja märksõnade puhastus toimus hiljem käsitsi OpenRefine'is.

from __future__ import annotations

import csv
import io
import os
import re
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

try:
    from google.colab import files
    COLAB = True
except Exception:
    COLAB = False


# ─────────────────────────────────────────────────────────────
# 1. Seadistused
# ─────────────────────────────────────────────────────────────

# Kui töötad Colabis, jäta INPUT_DIR tühjaks ja lae failid üles files.upload() kaudu.
# Kui töötad lokaalselt, pane siia kaust, kus MF_*.csv failid asuvad.
INPUT_DIR = Path(".")
OUTPUT_DIR = Path(".")
OUTPUT_DIR.mkdir(exist_ok=True)

MERGED_CSV = OUTPUT_DIR / "MF_loplik.csv"
OUTPUT_XLSX = OUTPUT_DIR / "ERA_fotod_esmapuhastus.xlsx"

# Claude API sammu ei käivitata vaikimisi. Kui seda oli vaja kasutada, sea True ja lisa võti keskkonnamuutujasse ANTHROPIC_API_KEY.
ENABLE_CLAUDE_ASSIST = False
ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"


# ─────────────────────────────────────────────────────────────
# 2. Üldised abifunktsioonid
# ─────────────────────────────────────────────────────────────

NULL_VALS = {"", "nan", "none", "null", "<na>", "nat", "teadmata"}

def clean_text(value) -> str:
    """Ühtlustab tühikud ja eemaldab tehnilised tühiväärtused."""
    if pd.isna(value):
        return ""
    text = str(value).replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return "" if text.lower() in NULL_VALS else text

def unique_nonempty(values) -> list[str]:
    """Tagastab unikaalsed mittetühjad väärtused algses järjekorras."""
    seen, out = set(), []
    for v in values:
        t = clean_text(v)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out

def viide_to_failinimi(viide) -> str:
    """Tuletab viitest pildifaili nime, nt 'Foto 123' -> 'mf_00123.jpg'."""
    match = re.search(r"Foto\s+(\d+)", str(viide))
    return f"mf_{int(match.group(1)):05d}.jpg" if match else ""

def split_multi_value(value) -> list[str]:
    """Jagab semikooloni, püstkriipsu või komaga eraldatud väärtused listiks."""
    text = clean_text(value)
    if not text:
        return []
    return [p.strip() for p in re.split(r"[;|,]", text) if p.strip()]


# ─────────────────────────────────────────────────────────────
# 3. CSV-failide laadimine
# ─────────────────────────────────────────────────────────────

def load_original_csvs() -> dict[str, bytes]:
    """Laeb algsed MF_*.csv failid kas Colabi üleslaadimisest või lokaalsest kaustast."""
    if COLAB:
        uploaded = files.upload()
        return {name: content for name, content in uploaded.items() if name.lower().endswith(".csv")}

    csv_files = sorted(INPUT_DIR.glob("MF_*.csv"))
    if not csv_files:
        raise FileNotFoundError("Ei leidnud lokaalsest kaustast ühtegi MF_*.csv faili.")
    return {p.name: p.read_bytes() for p in csv_files}


# ─────────────────────────────────────────────────────────────
# 4. Algsete CSV-de ühendamine üheks tabeliks
# ─────────────────────────────────────────────────────────────

def read_semicolon_csv(content: bytes) -> tuple[list[str], list[list[str]]]:
    """Loeb semikooloniga CSV sisu; utf-8-sig eemaldab vajadusel BOM-märgi."""
    text = content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    if not rows:
        return [], []
    return rows[0], rows[1:]

def merge_csvs(uploaded: dict[str, bytes]) -> list[dict]:
    """
    Ühendab eri CSV-d üheks pikaks listiks.
    Kui ühes failis kordub sama veerunimi, säilitatakse kõik väärtused listina.
    """
    all_rows = []
    all_headers = []

    for filename, content in sorted(uploaded.items()):
        header, rows = read_semicolon_csv(content)
        if not header:
            continue

        for col in header:
            if col not in all_headers:
                all_headers.append(col)

        for row in rows:
            if not any(clean_text(x) for x in row):
                continue

            row_dict = {"_source_file": filename}
            for i, val in enumerate(row):
                if i >= len(header):
                    continue
                col = header[i]
                if col in row_dict:
                    if not isinstance(row_dict[col], list):
                        row_dict[col] = [row_dict[col]]
                    row_dict[col].append(val)
                else:
                    row_dict[col] = val

            all_rows.append(row_dict)

        print(f"{filename}: {len(rows)} rida, {len(header)} veergu")

    print(f"Kokku ühendatud ridu: {len(all_rows)}")
    return all_rows


# ─────────────────────────────────────────────────────────────
# 5. ERA märksõnade lahtiharutamine
# ─────────────────────────────────────────────────────────────

def parse_era_keywords(row_dict: dict, keyword_col: str = "ERA märksõna") -> list[str]:
    """
    Harutab algse 'ERA märksõna' veeru üksikuteks märksõnadeks.
    Algandmetes võis üks lahter sisaldada mitut kirjet kujul 'Märksõna: ...'.
    """
    raw = row_dict.get(keyword_col, "")
    cells = raw if isinstance(raw, list) else [raw]

    keywords = []
    for cell in cells:
        text = clean_text(cell)
        if not text:
            continue

        # Tüüpiline muster: "... Märksõna: sõna, Märksõna: teine sõna"
        parts = re.split(r",?\s*Märksõna\s*:\s*", text)
        for part in parts:
            value = clean_text(part)
            if value and not value.lower().startswith("märksõna"):
                keywords.append(value)

    return unique_nonempty(keywords)


# ─────────────────────────────────────────────────────────────
# 6. Ühendatud CSV salvestamine
# ─────────────────────────────────────────────────────────────

def write_merged_csv(all_rows: list[dict], output_csv: Path) -> pd.DataFrame:
    """
    Teeb ühendatud tabeli DataFrame'iks, lisab märksõna veerud ja failinime.
    Väljund on endiselt lai tabel, mis sobib edasiseks käsipuhastuseks.
    """
    if not all_rows:
        raise ValueError("Ühtegi rida ei leitud.")

    # Kõik veerud algses järjekorras + tehniline allikafaili veerg.
    headers = []
    for row in all_rows:
        for col in row.keys():
            if col not in headers:
                headers.append(col)

    # Märksõnade arv määrab, mitu ERA märksõna N veergu luua.
    keyword_lists = [parse_era_keywords(r) for r in all_rows]
    max_kw = max((len(x) for x in keyword_lists), default=0)
    keyword_cols = [f"ERA märksõna {i}" for i in range(1, max_kw + 1)]

    base_headers = [h for h in headers if h != "ERA märksõna"]
    final_headers = base_headers + keyword_cols + ["failinimi"]

    output_rows = []
    for row_dict, keywords in zip(all_rows, keyword_lists):
        out = {}

        for col in base_headers:
            value = row_dict.get(col, "")
            if isinstance(value, list):
                out[col] = "; ".join(unique_nonempty(value))
            else:
                out[col] = clean_text(value)

        for i, col in enumerate(keyword_cols):
            out[col] = keywords[i] if i < len(keywords) else ""

        viide = row_dict.get("Viide", "")
        if isinstance(viide, list):
            viide = viide[0] if viide else ""
        out["failinimi"] = viide_to_failinimi(viide)

        output_rows.append(out)

    df = pd.DataFrame(output_rows, columns=final_headers)
    df.to_csv(output_csv, sep=";", index=False, encoding="utf-8-sig")
    print(f"Salvestatud ühendatud CSV: {output_csv}")
    return df


# ─────────────────────────────────────────────────────────────
# 7. Claude API abisamm — vajadusel isikute/fotograafide vihjete leidmiseks
# ─────────────────────────────────────────────────────────────

def claude_analyze_lisanimi(lisanimi: str, existing_photographers: list[str], existing_persons: list[str]) -> dict:
    """
    Valikuline abisamm: Claude API abil saab 'Lisanimi' tekstist pakkuda isikuid, rolle ja fotograafe.
    Seda ei käivitata vaikimisi ning API võtit ei tohi koodi sisse kirjutada.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("Puudub ANTHROPIC_API_KEY keskkonnamuutuja.")

    prompt = f"""
Analüüsi ERA foto kirjelduse lisanimetust ja tagasta ainult JSON.

Lisanimi: {lisanimi}
Olemasolevad fotograafid: {existing_photographers}
Olemasolevad isikud pildil: {existing_persons}

Tagasta JSON kujul:
{{
  "isik_pildil_ai": [],
  "roll_ai": [],
  "fotograaf_ai": []
}}
"""

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))

    text = data["content"][0]["text"]
    return json.loads(text)

def maybe_add_claude_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Kui ENABLE_CLAUDE_ASSIST=True, lisatakse AI abiveerud.
    Praktikas kasutati seda ainult abistava tööriistana, mitte lõpliku tõena.
    """
    if not ENABLE_CLAUDE_ASSIST:
        return df

    df = df.copy()
    for col in ["Isik pildil (AI)", "Roll (AI)", "Fotograaf (AI)"]:
        if col not in df.columns:
            df[col] = ""

    lisanimi_col = "Lisanimi"
    if lisanimi_col not in df.columns:
        print("Claude sammu ei tehtud: veerg 'Lisanimi' puudub.")
        return df

    photographer_cols = [c for c in df.columns if c.startswith("Fotograaf")]
    person_cols = [c for c in df.columns if c.startswith("Isik pildil")]

    for idx, row in df.iterrows():
        lisanimi = clean_text(row.get(lisanimi_col, ""))
        if not lisanimi:
            continue

        existing_photographers = unique_nonempty(row.get(c, "") for c in photographer_cols)
        existing_persons = unique_nonempty(row.get(c, "") for c in person_cols)

        try:
            result = claude_analyze_lisanimi(lisanimi, existing_photographers, existing_persons)
            df.at[idx, "Isik pildil (AI)"] = "; ".join(result.get("isik_pildil_ai", []))
            df.at[idx, "Roll (AI)"] = "; ".join(result.get("roll_ai", []))
            df.at[idx, "Fotograaf (AI)"] = "; ".join(result.get("fotograaf_ai", []))
            time.sleep(0.5)
        except Exception as e:
            print(f"Claude viga real {idx}: {e}")

    return df


# ─────────────────────────────────────────────────────────────
# 8. Asukohateksti lihtne parsija
# ─────────────────────────────────────────────────────────────

PLACE_ABBR = {
    "v.": "vald",
    "vald": "vald",
    "k.": "küla",
    "küla": "küla",
    "t.": "talu",
    "talu": "talu",
    "ms.": "mõis",
    "mõis": "mõis",
    "l.": "linn",
    "linn": "linn",
    "khk.": "kihelkond",
    "khk": "kihelkond",
    "kihelkond": "kihelkond",
    "raj.": "rajoon",
    "rajoon": "rajoon",
}

def parse_place_text(place_text) -> dict:
    """
    Parsib 'Koht täpsemalt' teksti lihtsateks osadeks.
    Siin ei tehta enam automaatset geokodeerimist, sest see andis ebaühtlase tulemuse
    ja vajab kultuuripärandi andmetes pigem hilisemat käsikontrolli.
    """
    text = clean_text(place_text)
    result = {
        "koht_algne_puhastatud": text,
        "koht_vald": "",
        "koht_küla": "",
        "koht_talu": "",
        "koht_mõis": "",
        "koht_linn": "",
        "koht_kihelkond": "",
        "koht_rajoon": "",
        "koht_muu": "",
        "koht_vajab_kontrolli": "ei",
    }

    if not text:
        result["koht_vajab_kontrolli"] = "jah"
        return result

    other = []
    parts = [p.strip() for p in text.split(",") if p.strip()]

    for part in parts:
        lower = part.lower().strip()
        matched = False

        for abbr, target in PLACE_ABBR.items():
            if lower.endswith(abbr):
                name = part[: -len(abbr)].strip(" .")
                col = f"koht_{target}"
                if col in result:
                    result[col] = "; ".join(unique_nonempty([result[col], name]))
                    matched = True
                    break

        if not matched:
            other.append(part)

    result["koht_muu"] = "; ".join(unique_nonempty(other))
    if result["koht_muu"]:
        result["koht_vajab_kontrolli"] = "jah"

    return result

def add_simple_place_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lisab asukohateksti lihtsa struktuuri ainult siis, kui 'Koht täpsemalt' on olemas."""
    if "Koht täpsemalt" not in df.columns:
        return df

    parsed = df["Koht täpsemalt"].apply(parse_place_text)
    parsed_df = pd.DataFrame(parsed.tolist())
    return pd.concat([df.reset_index(drop=True), parsed_df.reset_index(drop=True)], axis=1)


# ─────────────────────────────────────────────────────────────
# 9. Kolmeks analüüsitabeliks jagamine
# ─────────────────────────────────────────────────────────────

def find_cols(df: pd.DataFrame, prefixes: list[str]) -> list[str]:
    """Leiab veerud, mille nimi algab mõne antud prefiksiga."""
    return [c for c in df.columns if any(str(c).startswith(p) for p in prefixes)]

def split_to_analysis_tables(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Jagab laia tööfaili kolmeks tabeliks:
    fotod_master = üks rida ühe foto kohta;
    isikud_fotol_pikk = üks rida ühe foto-isiku/fotograafi seose kohta;
    märksõnad_pikk = üks rida ühe foto-märksõna kohta.
    """
    df = df.copy()
    if "PID" not in df.columns:
        df["PID"] = range(1, len(df) + 1)
    df["PID"] = df["PID"].astype(str).str.strip()

    keyword_cols = find_cols(df, ["ERA märksõna"])
    person_cols = find_cols(df, ["Isik pildil"])
    photographer_cols = find_cols(df, ["Fotograaf"])
    role_cols = find_cols(df, ["Roll"])

    repeated_cols = set(keyword_cols + person_cols + photographer_cols + role_cols)
    master_cols = [c for c in df.columns if c not in repeated_cols]
    fotod_master = df[master_cols].drop_duplicates("PID").copy()

    person_rows = []
    for _, row in df.iterrows():
        pid = row["PID"]
        photographers = unique_nonempty(row.get(c, "") for c in photographer_cols)
        roles = unique_nonempty(row.get(c, "") for c in role_cols)

        for person_col in person_cols:
            for person in split_multi_value(row.get(person_col, "")):
                person_rows.append({
                    "PID": pid,
                    "Isik": person,
                    "Roll": "; ".join(roles),
                    "Fotograaf": "; ".join(photographers),
                    "allikaveerg": person_col,
                })

        # Kui fotol isikut ei ole, aga fotograaf on olemas, säilitame fotograafi foto taseme seosena.
        if not any(split_multi_value(row.get(c, "")) for c in person_cols):
            for photographer in photographers:
                person_rows.append({
                    "PID": pid,
                    "Isik": "",
                    "Roll": "fotograaf",
                    "Fotograaf": photographer,
                    "allikaveerg": "Fotograaf",
                })

    isikud_fotol_pikk = pd.DataFrame(person_rows).drop_duplicates() if person_rows else pd.DataFrame(
        columns=["PID", "Isik", "Roll", "Fotograaf", "allikaveerg"]
    )

    keyword_rows = []
    for _, row in df.iterrows():
        pid = row["PID"]
        for col in keyword_cols:
            for kw in split_multi_value(row.get(col, "")):
                keyword_rows.append({
                    "PID": pid,
                    "Märksõna": kw,
                    "allikaveerg": col,
                })

    marksonad_pikk = pd.DataFrame(keyword_rows).drop_duplicates() if keyword_rows else pd.DataFrame(
        columns=["PID", "Märksõna", "allikaveerg"]
    )

    return fotod_master, isikud_fotol_pikk, marksonad_pikk


# ─────────────────────────────────────────────────────────────
# 10. Exceli väljund ja kokkuvõte
# ─────────────────────────────────────────────────────────────

def make_summary(fotod_master: pd.DataFrame, isikud: pd.DataFrame, marksonad: pd.DataFrame) -> pd.DataFrame:
    """Koostab lihtsa kontrollkokkuvõtte, et näha, kas tabelid tekkisid ootuspäraselt."""
    rows = [
        {"näitaja": "fotod_master read", "väärtus": len(fotod_master)},
        {"näitaja": "isikud_fotol_pikk read", "väärtus": len(isikud)},
        {"näitaja": "märksõnad_pikk read", "väärtus": len(marksonad)},
        {"näitaja": "unikaalseid PID-e", "väärtus": fotod_master["PID"].nunique() if "PID" in fotod_master.columns else ""},
        {"näitaja": "unikaalseid isikuid", "väärtus": isikud["Isik"].replace("", pd.NA).dropna().nunique() if "Isik" in isikud.columns else ""},
        {"näitaja": "unikaalseid märksõnu", "väärtus": marksonad["Märksõna"].nunique() if "Märksõna" in marksonad.columns else ""},
        {"näitaja": "märkus", "väärtus": "Isikuid, märksõnu ja kohanimesid puhastati hiljem täiendavalt käsitsi OpenRefine'is."},
        {"näitaja": "Claude API", "väärtus": "Ühes puhastusetapis kasutati tasulist Claude API-t abistavalt isikute/rollide/fotograafide vihjete leidmiseks."},
    ]
    return pd.DataFrame(rows)

def save_excel(output_xlsx: Path, fotod_master: pd.DataFrame, isikud: pd.DataFrame, marksonad: pd.DataFrame):
    """Salvestab kolm põhitabelit ja kokkuvõtte ühte Exceli faili."""
    summary = make_summary(fotod_master, isikud, marksonad)

    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        fotod_master.to_excel(writer, sheet_name="fotod_master", index=False)
        isikud.to_excel(writer, sheet_name="isikud_fotol_pikk", index=False)
        marksonad.to_excel(writer, sheet_name="märksõnad_pikk", index=False)
        summary.to_excel(writer, sheet_name="kokkuvõte", index=False)

    print(f"Valmis Excel: {output_xlsx}")
    print(summary)


# ─────────────────────────────────────────────────────────────
# 11. Põhivoo käivitamine
# ─────────────────────────────────────────────────────────────

def main():
    uploaded = load_original_csvs()
    all_rows = merge_csvs(uploaded)

    df = write_merged_csv(all_rows, MERGED_CSV)
    df = maybe_add_claude_columns(df)
    df = add_simple_place_columns(df)

    fotod_master, isikud, marksonad = split_to_analysis_tables(df)
    save_excel(OUTPUT_XLSX, fotod_master, isikud, marksonad)

    if COLAB:
        files.download(str(MERGED_CSV))
        files.download(str(OUTPUT_XLSX))

if __name__ == "__main__":
    main()
