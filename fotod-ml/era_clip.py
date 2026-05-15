# Käesolevas analüüsis kasutati OpenAI CLIP (Contrastive Language–Image Pretraining) mudelit, et võrrelda arhiivifotosid eeldefineeritud temaatiliste kategooriatega. 
# CLIP võimaldab siduda pilte ja tekstilisi kirjeldusi samasse tähendusruumi, hinnates kui hästi konkreetne pilt vastab etteantud kategooria kirjeldusele.
# Mudeli abil ennustati igale fotole kõige tõenäolisemad märksõnakategooriad ning võrreldi tulemusi olemasolevate käsitsi loodud märgendustega. 
# Lisaks salvestati iga ennustuse tõenäosusskoorid ja hinnati, kui sageli leidus õige kategooria mudeli top1, top3 või top5 tulemuste seas.

from pathlib import Path
import re
import random
import warnings

import pandas as pd
import numpy as np
from PIL import Image, ImageFile
from tqdm import tqdm

import torch
from transformers import CLIPProcessor, CLIPModel
from sklearn.metrics import precision_recall_fscore_support

ImageFile.LOAD_TRUNCATED_IMAGES = True
warnings.filterwarnings("ignore", category=UserWarning)


# ============================================================
# 1. Seaded ja sisendfailid
# ============================================================

EXCEL_PATH = "ERA_märksõnad_ML.xlsx"
SHEET_NAME = "ml_multihot_klastrid"
IMAGE_ROOT = Path.home() / "Desktop" / "era_fotod"
OUTPUT_EXCEL = "era_clip_KOIK_pildid_sigmoid.xlsx"

N_IMAGES = None          # 500 = testvalim, None = kõik pildid
RANDOM_SEED = 42
TOP_K = 5
FORCE_CPU = False

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}


# ============================================================
# 2. CLIP-i tekstipromptid kategooriatele
# ============================================================

CLUSTER_PROMPTS = {
    "abstraktne": "abstract pattern, symbol, unclear object, non-representational subject",
    "ehitis": "building, house, farm building, barn, church, architecture",
    "inimene": "portrait, person, people, human figure, group of people, family",
    "jahindus ja kalastus": "hunting, fishing, hunters, fishermen, fishing nets, fish, game animals",
    "loodus": "nature, landscape, forest, field, river, lake, trees, countryside",
    "loom": "animal, horse, cow, sheep, dog, cat, bird, livestock",
    "majapidamine ja tööriistad": "household objects, tools, farm tools, work equipment, utensils",
    "meditsiin": "medicine, healthcare, doctor, nurse, hospital, illness, medical equipment",
    "muu": "miscellaneous subject, other category, unclear archive photograph",
    "muusika": "music, musical instruments, musicians, singing, choir, band, performance",
    "mälestusmärk": "monument, memorial, statue, gravestone, commemorative marker",
    "mööbel": "furniture, chair, table, bed, cupboard, room interior, furnishings",
    "religioon": "religion, church, priest, cross, altar, sacred object, religious ritual",
    "sõiduk": "vehicle, car, cart, wagon, bicycle, boat, train, tractor, transport",
    "tants ja mäng": "dancing, playing, games, children playing, folk dance, leisure activity",
    "tekst/trükis": "text, printed material, book, document, sign, poster, newspaper, writing",
    "toit ja jook": "food, drink, meal, bread, dishes, table setting, kitchen",
    "tähtpäev": "celebration, holiday, wedding, funeral, ceremony, festival, anniversary",
    "välimus": "clothing, costume, appearance, hairstyle, accessories, traditional dress",
}


# ============================================================
# 3. Abifunktsioonid: Exceli read seotakse pildifailidega
# ============================================================
#
# Kuna failinimed ja PID-d ei olnud alati ühtlases formaadis,
# proovib kood tuletada võimalikud pildifaili nimed nii PID-st
# kui ka olemasolevatest failinime veergudest.
#
# Seejärel ehitatakse kogu pildikaustast indeks, et leida
# igale Exceli reale vastav pildifail.

# ============================================================

def pid_to_number(pid):
    if pd.isna(pid):
        return None
    nums = re.findall(r"\d+", str(pid))
    return int(nums[-1]) if nums else None


def possible_image_names(row):
    names = set()

    for col in ["failinimi", "Failinimi", "filename", "file_name", "pildifail", "Pildifail"]:
        if col in row.index and pd.notna(row[col]):
            raw_name = Path(str(row[col])).name.lower().strip()
            names.add(raw_name)

            n2 = pid_to_number(row[col])
            if n2 is not None:
                for width in [5, 4, 0]:
                    stem = f"mf_{n2:0{width}d}" if width else f"mf_{n2}"
                    for ext in IMAGE_EXTENSIONS:
                        names.add(stem + ext)

    n = pid_to_number(row["PID"] if "PID" in row.index else None)

    if n is not None:
        for width in [5, 4, 0]:
            stem = f"mf_{n:0{width}d}" if width else f"mf_{n}"
            for ext in IMAGE_EXTENSIONS:
                names.add(stem + ext)

    return names


def find_excel_file():
    path = Path(EXCEL_PATH)
    if path.exists():
        return path

    xlsx_files = list(Path(".").glob("*.xlsx"))
    if len(xlsx_files) == 1:
        print(f"Exceli täpne nimi ei klappinud, kasutan leitud faili: {xlsx_files[0]}")
        return xlsx_files[0]

    raise FileNotFoundError(f"Ei leidnud Excelit: {EXCEL_PATH}")


def build_image_index(image_root):
    image_root = Path(image_root).expanduser()
    if not image_root.exists():
        raise FileNotFoundError(f"Pildikausta ei leitud: {image_root}")

    print(f"Indekseerin pildid kaustast: {image_root}")

    index = {}
    count = 0
    for p in image_root.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
            index.setdefault(p.name.lower().strip(), p)
            count += 1

    print(f"Leidsin {count} pildifaili.")
    return index


def find_matching_image(names, image_index):
    for n in names:
        n_clean = n.lower().strip()
        if n_clean in image_index:
            return image_index[n_clean], "exact"

    for n in names:
        stem = Path(n).stem.lower().strip()
        for indexed_name, indexed_path in image_index.items():
            indexed_stem = Path(indexed_name).stem.lower().strip()
            if indexed_stem.startswith(stem + "_"):
                return indexed_path, "suffix_fallback"

    return None, None


def choose_device():
    if FORCE_CPU:
        return torch.device("cpu")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def get_cluster_columns(df):
    metadata = {
        "PID", "pid", "failinimi", "Failinimi", "filename", "file_name",
        "Sisu kirjeldus", "Kirjeldus", "Aasta", "Žanr", "Kihelkond",
        "Koht täpsemalt", "Fotograaf", "Fotograaf (puhastatud)",
        "true_labels", "labels", "klastrid", "Märksõna2", "_has_manual_cluster",
    }

    cols = []
    for col in df.columns:
        if col in metadata:
            continue
        values = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(values) and set(values.unique()).issubset({0, 1, 0.0, 1.0}):
            cols.append(col)

    return cols


# ============================================================
# 4. Valim: Exceliga seotud pildid + pildikaustast leitud lisapildid
# ============================================================

#
# prepare_sample():
# - märgib, millistel ridadel on käsitsi määratud klaster
# - seob Exceli read päris pildifailidega
# - lisab analüüsi ka need pildid, mida Exceliga siduda ei õnnestunud
#
def prepare_sample(df, cluster_cols, image_index):
    df = df.copy()

    y = df[cluster_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    df["_has_manual_cluster"] = y.sum(axis=1) > 0

    print(f"Exceli ridade arv: {len(df)}")
    print(f"Excelis käsitsi klastriga fotosid: {int(df['_has_manual_cluster'].sum())}")
    print(f"Pildikaustas indekseeritud faile: {len(image_index)}")

    found = []
    missing_excel_rows = []
    used_image_paths = set()

    for _, row in df.iterrows():
        names = possible_image_names(row)
        path, match_type = find_matching_image(names, image_index)

        d = row.to_dict()
        d["_possible_names"] = "; ".join(sorted(names))
        d["_match_type"] = match_type if match_type else "not_found"

        if path:
            d["_image_path"] = str(path)
            d["_image_filename"] = Path(path).name
            d["_source"] = "excel_matched"
            found.append(d)
            used_image_paths.add(str(path))
        else:
            missing_excel_rows.append(d)

    for indexed_name, indexed_path in image_index.items():
        if str(indexed_path) in used_image_paths:
            continue

        d = {
            "PID": "",
            "failinimi": indexed_name,
            "_possible_names": indexed_name,
            "_match_type": "image_only",
            "_image_path": str(indexed_path),
            "_image_filename": indexed_name,
            "_has_manual_cluster": False,
            "_source": "image_only",
        }

        for c in cluster_cols:
            d[c] = 0

        found.append(d)

    found_df = pd.DataFrame(found)
    missing_df = pd.DataFrame(missing_excel_rows)

    print(f"Analüüsitavaid pilte kokku: {len(found_df)}")
    print(f"Neist Exceliga seotud: {(found_df['_source'] == 'excel_matched').sum()}")
    print(f"Neist ainult pildikaustast: {(found_df['_source'] == 'image_only').sum()}")
    print(f"Exceli ridu, millele pilti ei leitud: {len(missing_df)}")

    if "_match_type" in found_df.columns:
        print("Match type jaotus:")
        print(found_df["_match_type"].value_counts(dropna=False).to_string())

    if len(found_df) == 0:
        raise RuntimeError("Ei leidnud ühtegi pilti.")

    if N_IMAGES is None:
        sample = found_df.reset_index(drop=True)
        print(f"Analüüsin kõiki pilte: {len(sample)}")
    else:
        sample = found_df.sample(n=min(N_IMAGES, len(found_df)), random_state=RANDOM_SEED).reset_index(drop=True)
        print(f"Valisin katseks {len(sample)} pilti.")

    return sample, missing_df


# ============================================================
# 5. CLIP ennustamine
# ============================================================
#
# Tekstipromptid teisendatakse CLIP mudeli embeddinguteks
# ning iga pildi embeddingut võrreldakse nende kategooriatega.
#
# Tulemuseks saadakse iga pildi kõige tõenäolisemad kategooriad
# koos skooride ja cosine similarity väärtustega.

# ============================================================

def make_text_prompts(cluster_cols):
    prompts = []
    for c in cluster_cols:
        c_clean = str(c).strip()
        prompts.append(CLUSTER_PROMPTS.get(c_clean, f"{c_clean}, archive photograph subject"))
    return prompts


def extract_feature_tensor(output):
    if isinstance(output, torch.Tensor):
        return output

    for attr in ["pooler_output", "text_embeds", "image_embeds"]:
        if hasattr(output, attr) and getattr(output, attr) is not None:
            return getattr(output, attr)

    if hasattr(output, "last_hidden_state") and output.last_hidden_state is not None:
        return output.last_hidden_state[:, 0, :]

    if isinstance(output, (tuple, list)):
        for item in output:
            if isinstance(item, torch.Tensor):
                return item

    raise TypeError(f"Ei oska mudeli väljundist embeddingut võtta: {type(output)}")


@torch.no_grad()
def compute_text_features(model, processor, cluster_cols, device):
    prompts = make_text_prompts(cluster_cols)
    inputs = processor(text=prompts, return_tensors="pt", padding=True, truncation=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    features = extract_feature_tensor(model.get_text_features(**inputs))
    features = features / features.norm(dim=-1, keepdim=True)

    return features, prompts


@torch.no_grad()
def compute_image_features(model, processor, image, device):
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    features = extract_feature_tensor(model.get_image_features(**inputs))
    features = features / features.norm(dim=-1, keepdim=True)

    return features


#
# predict_images():
# - loeb iga pildi sisse
# - arvutab CLIP embeddingu
# - võrdleb seda tekstikategooriatega
# - salvestab top5 ennustused ja nende skoorid
#
@torch.no_grad()
def predict_images(model, processor, sample_df, cluster_cols, text_features, device):
    rows = []

    for _, row in tqdm(sample_df.iterrows(), total=len(sample_df), desc="Analüüsin pilte"):
        image_path = row["_image_path"]

        try:
            image = Image.open(image_path).convert("RGB")
            image_features = compute_image_features(model, processor, image, device)

            cosine_scores = (image_features @ text_features.T).squeeze(0)
            sigmoid_scores = torch.sigmoid(cosine_scores)

            cosine_np = cosine_scores.detach().cpu().numpy()
            score_np = sigmoid_scores.detach().cpu().numpy()

            top_idx = np.argsort(score_np)[::-1][:TOP_K]
            pred = [cluster_cols[i] for i in top_idx]
            scores = [float(score_np[i]) for i in top_idx]
            cosine_top = [float(cosine_np[i]) for i in top_idx]

            true = [c for c in cluster_cols if pd.to_numeric(row.get(c, 0), errors="coerce") == 1]

            top1_score = scores[0]
            top2_score = scores[1] if len(scores) > 1 else np.nan
            confidence_margin = top1_score - top2_score if len(scores) > 1 else np.nan

            out = {
                "PID": row.get("PID", ""),
                "failinimi": row.get("failinimi", row.get("Failinimi", "")),
                "image_filename": row.get("_image_filename", Path(image_path).name),
                "image_path": image_path,
                "source": row.get("_source", ""),
                "match_type": row.get("_match_type", ""),
                "has_manual_cluster": bool(row.get("_has_manual_cluster", False)),
                "true_clusters": "; ".join(true),
                "pred_top1": pred[0] if len(pred) > 0 else "",
                "pred_top2": pred[1] if len(pred) > 1 else "",
                "pred_top3": pred[2] if len(pred) > 2 else "",
                "pred_top4": pred[3] if len(pred) > 3 else "",
                "pred_top5": pred[4] if len(pred) > 4 else "",
                "pred_top1_score": scores[0] if len(scores) > 0 else np.nan,
                "pred_top2_score": scores[1] if len(scores) > 1 else np.nan,
                "pred_top3_score": scores[2] if len(scores) > 2 else np.nan,
                "pred_top4_score": scores[3] if len(scores) > 3 else np.nan,
                "pred_top5_score": scores[4] if len(scores) > 4 else np.nan,
                "pred_top1_cosine": cosine_top[0] if len(cosine_top) > 0 else np.nan,
                "pred_top2_cosine": cosine_top[1] if len(cosine_top) > 1 else np.nan,
                "pred_top3_cosine": cosine_top[2] if len(cosine_top) > 2 else np.nan,
                "confidence_margin_top1_top2": confidence_margin,
                "hit_top1": int(pred[0] in true) if len(pred) > 0 and len(true) > 0 else np.nan,
                "hit_any_top3": int(any(c in true for c in pred[:3])) if len(true) > 0 else np.nan,
                "hit_any_top5": int(any(c in true for c in pred[:5])) if len(true) > 0 else np.nan,
            }

            for c, s, cos in zip(cluster_cols, score_np, cosine_np):
                out[f"score_{c}"] = float(s)
                out[f"cosine_{c}"] = float(cos)

            rows.append(out)

        except Exception as e:
            rows.append({
                "PID": row.get("PID", ""),
                "failinimi": row.get("failinimi", row.get("Failinimi", "")),
                "image_filename": row.get("_image_filename", Path(image_path).name),
                "image_path": image_path,
                "source": row.get("_source", ""),
                "match_type": row.get("_match_type", ""),
                "has_manual_cluster": bool(row.get("_has_manual_cluster", False)),
                "error": str(e),
            })

    return pd.DataFrame(rows)


# ============================================================
# 6. Hindamine ainult käsitsi klastriga piltidel
# ============================================================
#
# Täpsust hinnatakse ainult nende fotode põhjal,
# millel oli olemas inimese poolt määratud kategooria.
#
# Arvutatakse:
# - top1 täpsus
# - kas õige kategooria leidub top3 seas
# - kas õige kategooria leidub top5 seas
# - precision / recall / F1 skoorid kategooriate kaupa

# ============================================================

def make_metrics(pred_df, sample_df, cluster_cols):
    y_true = sample_df[cluster_cols].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int).values
    idx = {c: i for i, c in enumerate(cluster_cols)}

    y_pred_top3 = np.zeros_like(y_true)
    y_pred_top5 = np.zeros_like(y_true)

    for r, row in pred_df.iterrows():
        for col in ["pred_top1", "pred_top2", "pred_top3"]:
            label = row.get(col, "")
            if label in idx:
                y_pred_top3[r, idx[label]] = 1

        for col in ["pred_top1", "pred_top2", "pred_top3", "pred_top4", "pred_top5"]:
            label = row.get(col, "")
            if label in idx:
                y_pred_top5[r, idx[label]] = 1

    precision3, recall3, f13, support = precision_recall_fscore_support(
        y_true, y_pred_top3, average=None, zero_division=0
    )
    precision5, recall5, f15, _ = precision_recall_fscore_support(
        y_true, y_pred_top5, average=None, zero_division=0
    )

    metrics = pd.DataFrame({
        "cluster": cluster_cols,
        "support_true": support,
        "precision_top3": precision3,
        "recall_top3": recall3,
        "f1_top3": f13,
        "predicted_count_top3": y_pred_top3.sum(axis=0),
        "precision_top5": precision5,
        "recall_top5": recall5,
        "f1_top5": f15,
        "predicted_count_top5": y_pred_top5.sum(axis=0),
    }).sort_values("support_true", ascending=False)

    overall = pd.DataFrame([{
        "n_eval_images": len(pred_df),
        "top1_accuracy_multilabel": pred_df["hit_top1"].mean(),
        "top3_any_hit_rate": pred_df["hit_any_top3"].mean(),
        "top5_any_hit_rate": pred_df["hit_any_top5"].mean(),
        "mean_top1_score": pred_df["pred_top1_score"].mean(),
        "max_top1_score": pred_df["pred_top1_score"].max(),
        "min_top1_score": pred_df["pred_top1_score"].min(),
        "mean_confidence_margin": pred_df["confidence_margin_top1_top2"].mean(),
        "note": "Täpsus arvutatud ainult nende piltide põhjal, millel on käsitsi klaster olemas. Kõik pildid said siiski CLIP-i ennustuse.",
    }])

    return metrics, overall


def make_threshold_summary(pred_df):
    thresholds = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    rows = []

    for t in thresholds:
        subset = pred_df[pred_df["pred_top1_score"] >= t]
        rows.append({
            "threshold_top1_score": t,
            "n_images_above_threshold": len(subset),
            "share_images_above_threshold": len(subset) / len(pred_df) if len(pred_df) else 0,
            "top1_accuracy_within_threshold": subset["hit_top1"].mean() if len(subset) else np.nan,
            "top3_hit_within_threshold": subset["hit_any_top3"].mean() if len(subset) else np.nan,
            "top5_hit_within_threshold": subset["hit_any_top5"].mean() if len(subset) else np.nan,
        })

    return pd.DataFrame(rows)


# ============================================================
# 7. Põhiprotsess: laadimine, ennustamine, hindamine ja salvestamine
# ============================================================
#
# Töövoog:
# 1. Loetakse Excel ja leitakse kategooriaveerud
# 2. Seotakse read pildifailidega
# 3. Laetakse CLIP mudel
# 4. Ennustatakse igale pildile kategooriad
# 5. Hinnatakse tulemusi käsitsi märgendatud piltidel
# 6. Salvestatakse kõik tulemused Excelisse
#
# ============================================================

def main():
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    torch.manual_seed(RANDOM_SEED)

    excel = find_excel_file()
    print(f"Loen Excelit: {excel}")

    df = pd.read_excel(excel, sheet_name=SHEET_NAME)

    cluster_cols = get_cluster_columns(df)
    print(f"Leidsin {len(cluster_cols)} klastrit:")
    print(cluster_cols)

    image_index = build_image_index(IMAGE_ROOT)
    sample_df, missing_df = prepare_sample(df, cluster_cols, image_index)

    device = choose_device()
    print(f"Kasutan seadet: {device}")

    print("Laen CLIP mudeli.")
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
    model.eval()

    text_features, prompts = compute_text_features(model, processor, cluster_cols, device)
    prompt_df = pd.DataFrame({"cluster": cluster_cols, "prompt": prompts})

    pred_df = predict_images(model, processor, sample_df, cluster_cols, text_features, device)

    eval_mask = sample_df["_has_manual_cluster"] == True
    sample_eval = sample_df[eval_mask].reset_index(drop=True)
    pred_eval = pred_df[eval_mask].reset_index(drop=True)

    metrics_df, overall_df = make_metrics(pred_eval, sample_eval, cluster_cols)
    threshold_df = make_threshold_summary(pred_eval)

    corpus_summary = pd.DataFrame([{
        "total_images_analyzed": len(pred_df),
        "images_with_manual_cluster_for_evaluation": len(pred_eval),
        "images_without_manual_cluster_ml_only": int((sample_df["_has_manual_cluster"] == False).sum()),
        "excel_matched_images": int((sample_df["_source"] == "excel_matched").sum()),
        "image_only_images": int((sample_df["_source"] == "image_only").sum()),
        "missing_excel_rows": len(missing_df),
    }])

    print(f"Salvestan tulemused: {OUTPUT_EXCEL}")

    with pd.ExcelWriter(OUTPUT_EXCEL, engine="openpyxl") as writer:
        pred_df.to_excel(writer, sheet_name="predictions_all", index=False)
        pred_eval.to_excel(writer, sheet_name="predictions_eval_only", index=False)
        metrics_df.to_excel(writer, sheet_name="cluster_metrics", index=False)
        overall_df.to_excel(writer, sheet_name="overall_eval_only", index=False)
        threshold_df.to_excel(writer, sheet_name="threshold_eval_only", index=False)
        corpus_summary.to_excel(writer, sheet_name="corpus_summary", index=False)
        prompt_df.to_excel(writer, sheet_name="prompts", index=False)
        sample_df.to_excel(writer, sheet_name="sample_all", index=False)
        missing_df.to_excel(writer, sheet_name="missing_excel_rows", index=False)

    print("Valmis.")
    print(f"Tulemus: {Path(OUTPUT_EXCEL).resolve()}")
    print()
    print("Korpuse kokkuvõte:")
    print(corpus_summary.to_string(index=False))
    print()
    print("Hindamistulemused ainult käsitsi klastriga piltidel:")
    print(overall_df.to_string(index=False))
    print()
    print("Lävendite kokkuvõte:")
    print(threshold_df.to_string(index=False))


if __name__ == "__main__":
    main()
