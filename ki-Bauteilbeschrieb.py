# ki-Bauteilbeschrieb.py
# -------------------------------------------------------------------
# Bauteil-Analyse mit KI ODER Mock/Simulator
# - Mock standardmäßig aktiv (kein API-Key nötig)
# - Horizontale 1-Reihen-Galerie (scrollbar) + Auswahl
# - Ergebnisse in 2 Spalten: pro Karte Bild + "📑 Details anzeigen"
# - Excel-Export mit Fallback (openpyxl, wenn xlsxwriter fehlt)
# -------------------------------------------------------------------
import os
import io
import json
import base64
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
from PIL import Image

# ---------- Seite / Styles ----------
st.set_page_config(page_title="Bauteil Auto-Tagger", page_icon="🧱", layout="wide")
st.title("🧱 Bauteil Auto-Tagger")
st.caption("Excel-Kategorien + Fotos → erkennt mehrere Bauteile pro Bild, ordnet zu und erstellt Beschriebe. (Mock ohne API verfügbar)")

st.markdown("""
<style>
.block-container {max-width: 1200px;}
.card { padding: 14px; border-radius: 14px; background: #ffffff; border: 1px solid #e5e7eb; box-shadow: 0 6px 18px rgba(16,24,40,0.06); margin-bottom: 14px; }
.badge { display:inline-block; padding: 2px 8px; border-radius: 999px; background:#eef2ff; color:#3730a3; border:1px solid #e5e7eb; font-size:.8rem; }
.hscroll-wrap { overflow-x: auto; overflow-y: hidden; white-space: nowrap; padding: 8px 2px 4px 2px; border: 1px solid #e5e7eb; border-radius: 12px; background: #fff; }
.tile { display: inline-block; width: 260px; margin-right: 12px; vertical-align: top; }
.tile img { width: 100%; height: 180px; object-fit: cover; border-radius: 10px; display: block; border: 1px solid #eee; }
.tile .cap { font-size: 0.85rem; color: #374151; margin-top: 6px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; text-align:center; }
</style>
""", unsafe_allow_html=True)

# ---------- Sidebar ----------
with st.sidebar:
    st.header("⚙️ Einstellungen")
    MOCK_MODE = st.toggle("Mock/Simulator verwenden (ohne API)", value=True,
                          help="Wenn aktiv, werden Antworten simuliert. Kein OpenAI-Schlüssel/Guthaben nötig.")
    model_name = st.selectbox("Modell (nur wenn Mock AUS)", ["gpt-5"], index=0)
    temperature = st.slider("Kreativität (nur KI)", 0.0, 1.0, 0.2, 0.05)
    with st.expander("ℹ️ Hilfe & Diagnose", expanded=False):
        st.markdown("""
**Mock**: Funktioniert ohne API/Key.  
**KI**: `OPENAI_API_KEY` in `.env` oder `.streamlit/secrets.toml` eintragen (Project-Key `sk-proj-...`).  
Bei 429/Quota-Fehler wird automatisch auf Mock gewechselt.
""")

# ---------- Helpers ----------
def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().capitalize() for c in df.columns]
    return df

def best_category_for_bauteil(df_cat: pd.DataFrame, bauteil: str) -> str:
    rows = df_cat[df_cat["Bauteil"].astype(str).str.strip().str.lower() == str(bauteil).strip().lower()]
    if len(rows) > 0:
        return str(rows["Kategorie"].iloc[0])
    return ""

def safe_json_parse(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{"); end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try: return json.loads(text[start:end+1])
            except Exception: pass
        start = text.find("["); end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try: return json.loads(text[start:end+1])
            except Exception: pass
    return None

def image_to_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"

def thumb_b64(img_file, max_size=(520, 520)) -> str:
    pil = Image.open(img_file).convert("RGB")
    pil_thumb = pil.copy(); pil_thumb.thumbnail(max_size)
    buf = io.BytesIO(); pil_thumb.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

# ---------- MOCK / Simulator ----------
MOCK_KEYWORDS = {
    "fenster": ["Fenster"],
    "window": ["Fenster"],
    "wc": ["Sanitärobjekte", "Haustechnik"],
    "toilet": ["Sanitärobjekte"],
    "sanit": ["Sanitärobjekte"],
    "rohr": ["Haustechnik"],
    "leitung": ["Haustechnik"],
    "heiz": ["Heizung", "Haustechnik"],
    "fassade": ["Fassade", "Türen"],
    "tuer": ["Türen"], "tür": ["Türen"], "door": ["Türen"],
    "rohbau": ["Rohbau"]
}
MOCK_DEFAULTS = [
    ["Fenster", "Haustechnik"],
    ["Türen", "Fassade"],
    ["Sanitärobjekte"],
    ["Haustechnik"],
    ["Rohbau"]
]
def mock_describe(bauteil: str) -> str:
    templates = {
        "Fenster": ("Holz-/Metall-Fenster mit Isolierverglasung, funktionsfähig. "
                    "Energetik nicht Stand der Technik (kein 3-fach). Absturzsicherung prüfen. "
                    "Empfehlung: mittelfristige Erneuerung."),
        "Sanitärobjekte": ("Stand-WC aus Keramik mit Aufputz-Spülkasten. Funktionstüchtig, "
                           "Wasserverbrauch höher als moderne Sparsysteme. Empfehlung: Ersatz 5–10 Jahre."),
        "Haustechnik": ("Rohr- und Armaturenverbund (Absperrventile, Zähler). Anlage in Betrieb, "
                        "altersbedingt Korrosions-/Leckagerisiko. Empfehlung: Prüfung & Teilersatz."),
        "Heizung": ("Zentrale Heizungsanlage (Typ unspezifisch). Funktionstauglich, "
                    "Lebensdauer erreicht/nähernd. Empfehlung: kurz-/mittelfristiger Ersatz."),
        "Türen": ("Automatische Glas-Schiebetür mit Aluminiumprofilen. Funktionsfähig, "
                  "Dichtungen prüfen. Empfehlung: Wartungsvertrag & jährliche Kontrolle."),
        "Fassade": ("Naturstein-/Mineralfassade ohne sichtbare Schadstellen. "
                    "Regelmäßiger Unterhalt ausreichend. Empfehlung: Reinigung & Inspektion im Turnus."),
        "Rohbau": ("Ortbeton (UG/TG), gedämmtes Zweischalenmauerwerk (EG/OG), Holz-Dachkonstruktion. "
                   "Keine visuellen Mängel. Empfehlung: routinemäßige Bauwerksprüfung.")
    }
    return templates.get(bauteil, f"{bauteil}: Funktionsfähig. Empfehlung: turnusmäßige Wartung.")

def mock_pick_bauteile(filename: str, excel_bauteile: List[str], max_items: int = 3) -> List[str]:
    name = filename.lower()
    hits = []
    for k, cand in MOCK_KEYWORDS.items():
        if k in name:
            for c in cand:
                if c in excel_bauteile and c not in hits:
                    hits.append(c)
    if not hits:
        for combo in MOCK_DEFAULTS:
            filtered = [c for c in combo if c in excel_bauteile]
            if filtered:
                hits = filtered
                break
    if not hits:
        hits = excel_bauteile[:2]
    return hits[:max_items]

def simulate_vision(filename: str, excel_bauteile: List[str], max_items: int = 3) -> Dict[str, Any]:
    import random
    random.seed(42 + hash(filename) % 10000)
    picks = mock_pick_bauteile(filename, excel_bauteile, max_items=max_items)
    detections = []
    for p in picks:
        detections.append({
            "bauteil": p,
            "beschreibung": mock_describe(p),
            "wahrscheinlichkeit": round(random.uniform(0.7, 0.95), 2),
            "notizen": "Simuliert (Mock) – ersetzt KI-Antwort ohne API."
        })
    return {"detections": detections}

# ---------- KI (nur wenn Mock aus) ----------
def get_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        try: key = st.secrets["OPENAI_API_KEY"]
        except Exception: key = None
    return key

def build_prompt(bauteile_liste: List[str]) -> list:
    sys = {
        "role": "system",
        "content": (
            "Du bist ein sachlicher, technisch präziser Bau-/Immobiliengutachter. "
            "Erkenne mehrere Bauteile pro Bild und liefere detaillierte, normnahe Beschreibungen "
            "wie in Bauzustandsberichten (Material/Typ, geschätztes Baujahr, Funktionszustand, "
            "sichtbare Mängel, Norm-/Sicherheitsaspekte, konkrete Maßnahmen mit Dringlichkeit). "
            "Antworte nur mit JSON der Form: "
            '{"detections":[{"bauteil":"...","beschreibung":"...","wahrscheinlichkeit":0.0,"notizen":"..."}]}'
        )
    }
    user_text = (
        "Hier ist ein Bild. "
        "Wähle alle passenden Bauteile aus dieser Liste (Mehrfachauswahl erlaubt): "
        f"{bauteile_liste}. "
        "Gib für jedes erkannte Bauteil eine ausführliche Beschreibung. "
        "Liefere ausschließlich JSON unter 'detections' mit Feldern "
        "bauteil, beschreibung, wahrscheinlichkeit (0..1), notizen."
    )
    user = {"role": "user", "content": [{"type": "text", "text": user_text}]}
    return [sys, user]

def call_openai_vision(data_uri: str, bauteile_liste: List[str], model: str = "gpt-5", temperature: float = 0.2) -> Any:
    try:
        from openai import OpenAI
    except Exception:
        raise RuntimeError("OpenAI SDK nicht installiert. `pip install openai` oder Mock aktivieren.")
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("Kein OPENAI_API_KEY gefunden. `.env`/`secrets.toml` pflegen oder Mock aktivieren.")
    client = OpenAI(api_key=api_key)
    messages = build_prompt(bauteile_liste)
    messages[-1]["content"].append({"type": "image_url", "image_url": {"url": data_uri}})
    try:
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=900
        )
        text = resp.choices[0].message.content or ""
    except Exception as e:
        if "insufficient_quota" in str(e) or "429" in str(e):
            return simulate_vision("quota_fallback.jpg", bauteile_liste, max_items=3)
        raise
    data = safe_json_parse(text)
    if data is None:
        raise RuntimeError("Antwort konnte nicht als JSON geparst werden.")
    return data

# ---------- Uploads ----------
col1, col2 = st.columns([1,1])
with col1:
    excel = st.file_uploader("📄 Excel mit Spalten **Bauteil** & **Kategorie**", type=["xlsx","xls"])
with col2:
    images = st.file_uploader("🖼️ Bilder hochladen (Mehrfachauswahl)", type=["jpg","jpeg","png"], accept_multiple_files=True)

if not excel:
    st.info("Bitte Excel-Datei hochladen.")
    st.stop()

try:
    df_cat = normalize_cols(pd.read_excel(excel))
except Exception as e:
    st.error(f"Excel konnte nicht gelesen werden: {e}")
    st.stop()

if "Bauteil" not in df_cat.columns or "Kategorie" not in df_cat.columns:
    st.error("Die Excel-Datei benötigt die Spalten **Bauteil** und **Kategorie**.")
    st.stop()

known_bauteile = list(dict.fromkeys(df_cat["Bauteil"].astype(str).str.strip().tolist()))

# ---------- Horizontale 1-Reihen-Galerie + Auswahl ----------
selected_names: List[str] = []

if images:
    st.markdown("### 🖼️ Bilder-Galerie (horizontal scroll)")
    thumbs_b64 = [(img.name, thumb_b64(img, max_size=(520,520))) for img in images]

    html = ['<div class="hscroll-wrap">']
    for name, b64 in thumbs_b64:
        html.append(f'<div class="tile"><img src="data:image/jpeg;base64,{b64}"/><div class="cap">{name}</div></div>')
    html.append('</div>')
    st.markdown("\n".join(html), unsafe_allow_html=True)

    st.markdown("#### Auswahl")
    all_names = [img.name for img in images]
    if st.checkbox("Alle auswählen", value=False):
        selected_names = all_names
    else:
        selected_names = st.multiselect("Bilder auswählen", options=all_names, default=[])
    if not selected_names:
        st.info("Kein Bild ausgewählt – bei **Start** werden **alle** Bilder verarbeitet.")
else:
    st.info("Bitte zuerst Bilder hochladen, dann erscheinen sie hier als horizontale Galerie.")

# ---------- Analyse starten ----------
run_btn = st.button("🚀 Start", type="primary", use_container_width=True)
results: List[Dict[str, Any]] = []

if run_btn:
    if not images:
        st.warning("Bitte zuerst Bilder hochladen.")
    else:
        name_to_file = {img.name: img for img in images}
        to_process = [name_to_file[n] for n in selected_names if n in name_to_file] or list(images)

        # ✅ 2 Spalten EINMAL anlegen (nicht pro Bild)
        cols = st.columns(2)

        with st.spinner("Analysiere Bilder …"):
            for i, img_file in enumerate(to_process):
                # Bild laden + verkleinerte Kopie für Vision/Mock
                pil = Image.open(img_file).convert("RGB")
                pil_small = pil.copy(); pil_small.thumbnail((1280, 1280))
                data_uri = image_to_data_uri(pil_small)

                # KI oder Mock
                try:
                    if MOCK_MODE:
                        raw = simulate_vision(img_file.name, known_bauteile, max_items=3)
                    else:
                        raw = call_openai_vision(data_uri, known_bauteile, model=model_name, temperature=temperature)
                except Exception as ai_err:
                    st.warning(f"KI-Aufruf fehlgeschlagen → Mock verwendet. Details: {ai_err}")
                    raw = simulate_vision(img_file.name, known_bauteile, max_items=3)

                detections = raw.get("detections", []) or []

                # ----- Karte in linke/rechte Spalte nach Index -----
                with cols[i % 2]:
                    st.markdown('<div class="card">', unsafe_allow_html=True)

                    # Kompaktes Bild in der Karte
                    preview = pil.copy(); preview.thumbnail((800, 800))
                    st.image(preview, caption=f"Bild {i+1}: {img_file.name}", use_container_width=True)

                    with st.expander("📑 Details anzeigen", expanded=False):
                        if not detections:
                            st.info("Keine Bauteile erkannt/simuliert.")
                        else:
                            for det in detections:
                                btl = str(det.get("bauteil","")).strip()
                                beschr = str(det.get("beschreibung","")).strip()
                                prob = float(det.get("wahrscheinlichkeit", 0) or 0)
                                notes = str(det.get("notizen","")).strip()
                                kat = best_category_for_bauteil(df_cat, btl)

                                st.markdown(f"**Bauteil:** {btl}  \n**Kategorie:** {kat}  \n**Wahrscheinlichkeit:** {prob:.2f}")
                                st.markdown(f"**Beschreibung:** {beschr}")
                                if notes:
                                    st.caption(notes)
                                st.markdown("---")

                                # Für Export sammeln
                                results.append({
                                    "Bild": img_file.name,
                                    "Bauteil": btl,
                                    "Kategorie": kat,
                                    "Beschreibung": beschr,
                                    "Wahrscheinlichkeit": round(prob, 3),
                                    "Notizen": notes
                                })

                    st.markdown('</div>', unsafe_allow_html=True)

# ---------- Export ----------
if results:
    st.markdown("### ⬇️ Export")
    df_results = pd.DataFrame(results)

    out = io.BytesIO()
    try:
        # bevorzugt xlsxwriter (falls installiert)
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            df_results.to_excel(writer, index=False, sheet_name="Bericht")
            meta = pd.DataFrame({
                "Erstellt am": [datetime.now().strftime("%Y-%m-%d %H:%M")],
                "Bilder": [", ".join(sorted(set(df_results['Bild'].tolist())))]
            })
            meta.to_excel(writer, index=False, sheet_name="Meta")
    except ModuleNotFoundError:
        # Fallback ohne Zusatzinstallation
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df_results.to_excel(writer, index=False, sheet_name="Bericht")
            meta = pd.DataFrame({
                "Erstellt am": [datetime.now().strftime("%Y-%m-%d %H:%M")],
                "Bilder": [", ".join(sorted(set(df_results['Bild'].tolist())))]
            })
            meta.to_excel(writer, index=False, sheet_name="Meta")

    st.download_button(
        "📥 Bericht als Excel (.xlsx)",
        data=out.getvalue(),
        file_name=f"Bauteil_Bericht_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
