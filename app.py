# -*- coding: utf-8 -*-
"""
APP DE RADON - VERSION STREAMLIT
=================================
Migración de la app de escritorio (Tkinter + OpenCV) a Streamlit.

Conserva TODA la lógica original:
  - Gestión de Centros y Detectores en SQLite
  - Marcado del punto del detector sobre el plano
  - Generación de informe PDF (idéntica, con logo y cabecera)
  - Ajustes (técnico/empresa)

Cambios respecto a la versión Windows:
  - La cámara ya no usa cv2.VideoCapture (ventana propia de escritorio):
    usa st.camera_input, que abre la cámara nativa del navegador
    (funciona igual en PC como en el móvil Android).
  - El punto sobre el plano se marca con un clic usando el componente
    streamlit-image-coordinates.
  - Al generar el PDF aparece un botón "Enviar por WhatsApp" que usa la
    Web Share API de Android para abrir el diálogo nativo de compartir
    con el PDF ya adjunto.
"""

import os
import io
import re
import json
import base64
import sqlite3
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageOps

try:
    from streamlit_image_coordinates import streamlit_image_coordinates
    IMG_COORD_DISPONIBLE = True
except ImportError:
    IMG_COORD_DISPONIBLE = False

st.set_page_config(page_title="Detectores Rn", page_icon="☢️", layout="wide")

# Ajustes visuales generales: texto en negrita, títulos más pequeños,
# texto pequeño (captions/etiquetas) más grande, botones destacados en
# naranja, y fondo gris oscuro en todos los paneles/tarjetas.
st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-weight: 700 !important;
    }

    /* Títulos más pequeños (pantalla de inicio y el resto de pantallas) */
    h1 { font-size: 1.55rem !important; }
    h2 { font-size: 1.25rem !important; }
    h3 { font-size: 1.1rem !important; }

    /* Texto pequeño (captions, ayudas, pies de foto...) más grande y legible */
    [data-testid="stCaptionContainer"], .stCaption, small {
        font-size: 1rem !important;
    }
    label, .stMarkdown p {
        font-size: 1.02rem !important;
    }

    /* Todos los botones (destacados "primary" y normales "secondary",
       que en modo oscuro se ven negros) en naranja */
    button[kind="primary"], button[kind="primaryFormSubmit"],
    button[kind="secondary"], button[kind="secondaryFormSubmit"],
    .stDownloadButton button {
        background-color: #F97316 !important;
        border-color: #F97316 !important;
        color: #ffffff !important;
    }
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover,
    button[kind="secondary"]:hover, button[kind="secondaryFormSubmit"]:hover,
    .stDownloadButton button:hover {
        background-color: #ea6a0c !important;
        border-color: #ea6a0c !important;
    }

    /* Botón "Eliminar" (marcado con un div justo antes, ver código
       Python): diminuto, ajustado al ancho del texto/icono, en un
       rosa tenue para que quede claramente secundario frente a "Abrir". */
    div:has(> div.marcador-btn-eliminar) + div button {
        background-color: #d98ca0 !important;
        border-color: #d98ca0 !important;
        color: #ffffff !important;
        font-size: 0.7rem !important;
        font-weight: 400 !important;
        padding: 0.05rem 0.5rem !important;
        min-height: 1.5rem !important;
        height: 1.5rem !important;
        line-height: 1 !important;
        width: auto !important;
        min-width: 0 !important;
        display: inline-flex !important;
        opacity: 0.85;
    }
    div:has(> div.marcador-btn-eliminar) + div button:hover {
        background-color: #c1708a !important;
        border-color: #c1708a !important;
        opacity: 1;
    }
    div:has(> div.marcador-btn-eliminar) + div[data-testid="stButton"] {
        display: flex !important;
        justify-content: flex-start !important;
    }

    /* "Ventanas" (tarjetas, expanders, formularios) con fondo gris oscuro */
    div[data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="stExpander"],
    div[data-testid="stForm"] {
        background-color: #262626 !important;
        border-radius: 10px;
    }

    /* Títulos de cada ventana/panel en naranja */
    h1, h2, h3 {
        color: #F97316 !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p {
        color: #F97316 !important;
    }

    /* Cabecera de los desplegables tipo acordeón (expanders) en blanco,
       para que combine con las casillas (p.ej. "➕ Nuevo centro") */
    div[data-testid="stExpander"] summary {
        background-color: #ffffff !important;
        border-radius: 0 !important;
    }

    /* Casillas de texto y desplegables: SOLO el recuadro donde se
       escribe/selecciona queda en blanco con letra negra, un 25% más
       grande (1rem -> 1.25rem) y con esquinas rectas (sin redondear).
       La etiqueta de encima (el texto que describe el campo, con
       testid "stWidgetLabel") se excluye a propósito para que quede
       sobre el fondo gris de la ventana.
       Se usa "*" para pintar TODO lo de dentro del recuadro (incluida
       la parte del desplegable de Streamlit, que anida varios niveles
       de <div> internos) y luego se fuerza la etiqueta a transparente
       para que no quede afectada. */
    div[data-testid="stTextInput"] > div:not([data-testid="stWidgetLabel"]),
    div[data-testid="stTextInput"] > div:not([data-testid="stWidgetLabel"]) *,
    div[data-testid="stTextArea"] > div:not([data-testid="stWidgetLabel"]),
    div[data-testid="stTextArea"] > div:not([data-testid="stWidgetLabel"]) *,
    div[data-testid="stNumberInput"] > div:not([data-testid="stWidgetLabel"]),
    div[data-testid="stNumberInput"] > div:not([data-testid="stWidgetLabel"]) *,
    div[data-testid="stDateInput"] > div:not([data-testid="stWidgetLabel"]),
    div[data-testid="stDateInput"] > div:not([data-testid="stWidgetLabel"]) *,
    div[data-testid="stSelectbox"] > div:not([data-testid="stWidgetLabel"]),
    div[data-testid="stSelectbox"] > div:not([data-testid="stWidgetLabel"]) * {
        background-color: #ffffff !important;
        color: #000000 !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        border-radius: 0 !important;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stDateInput"] input,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] * {
        background-color: #ffffff !important;
        color: #000000 !important;
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        border-radius: 0 !important;
    }
    /* La etiqueta de encima NO se toca: se fuerza a volver al color de
       texto normal de la app, sobre el fondo gris de la ventana. */
    div[data-testid="stWidgetLabel"],
    div[data-testid="stWidgetLabel"] * {
        background-color: transparent !important;
    }
    /* Menú desplegable del selectbox al abrirlo: se renderiza en un
       "popover" flotante fuera del recuadro, así que se cubre con
       TODOS los posibles selectores que puede usar Streamlit/BaseWeb
       (testid, data-baseweb de popover/menu/menu-item, y roles ARIA
       listbox/option) y con "*" para llegar a todas las capas
       internas de texto/fondo, sea cual sea la estructura exacta. */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] *,
    div[data-baseweb="menu"],
    div[data-baseweb="menu"] *,
    li[data-baseweb="menu-item"],
    li[data-baseweb="menu-item"] *,
    ul[data-testid="stSelectboxVirtualDropdown"],
    ul[data-testid="stSelectboxVirtualDropdown"] *,
    [role="listbox"],
    [role="listbox"] *,
    [role="option"],
    [role="option"] * {
        background-color: #ffffff !important;
        color: #000000 !important;
        border-radius: 0 !important;
    }
    div[data-baseweb="popover"] li,
    li[data-baseweb="menu-item"],
    ul[data-testid="stSelectboxVirtualDropdown"] li,
    [role="listbox"] li,
    [role="option"] {
        font-size: 1.25rem !important;
    }
    /* Opción resaltada al pasar el ratón/dedo: un gris muy claro para
       distinguirla, siempre con texto negro */
    div[data-baseweb="popover"] li:hover,
    li[data-baseweb="menu-item"]:hover,
    ul[data-testid="stSelectboxVirtualDropdown"] li:hover,
    [role="listbox"] li:hover,
    [role="option"]:hover,
    div[data-baseweb="popover"] li[aria-selected="true"],
    li[data-baseweb="menu-item"][aria-selected="true"],
    [role="listbox"] li[aria-selected="true"],
    [role="option"][aria-selected="true"] {
        background-color: #eeeeee !important;
        color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# BASE DE DATOS  (idéntica a la app de escritorio)
# ============================================================

DB_NAME = "radon_data.db"


def get_data_dir():
    """Carpeta donde se guardan la BD y las imágenes.

    Se usa una carpeta junto al propio script para que funcione igual
    en local, en un servidor o en Streamlit Community Cloud. Si prefieres
    guardar los datos en el perfil del usuario como hacía la app de
    Windows, cambia la línea siguiente por:
        data_dir = os.path.join(os.path.expanduser("~"), "RadonApp")
    """
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "RadonApp_data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_db_path():
    return os.path.join(get_data_dir(), DB_NAME)


def init_db():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS centros
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  nombre TEXT, zona TEXT, fecha_medicion TEXT, imagen_exterior_path TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS detectores
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  centro_id INTEGER,
                  planta TEXT, sala TEXT, fecha TEXT, detector_codigo TEXT,
                  plano_path TEXT, punto_x REAL, punto_y REAL,
                  foto_situacion_path TEXT, foto_detector_path TEXT,
                  fecha_creacion TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (id INTEGER PRIMARY KEY CHECK (id=1), tecnico TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (id, tecnico) VALUES (1, '')")
    conn.commit()
    conn.close()


def crear_centro(nombre):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("INSERT INTO centros (nombre, zona, fecha_medicion, imagen_exterior_path) VALUES (?, '', ?, NULL)",
              (nombre, datetime.now().strftime("%d/%m/%Y")))
    rowid = c.lastrowid
    conn.commit()
    conn.close()
    return rowid


def fetch_centros():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT id, nombre, zona, fecha_medicion, imagen_exterior_path FROM centros ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows


def get_centro(centro_id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT id, nombre, zona, fecha_medicion, imagen_exterior_path FROM centros WHERE id=?", (centro_id,))
    row = c.fetchone()
    conn.close()
    return row


def update_centro(centro_id, nombre, zona, fecha, imagen_path):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("UPDATE centros SET nombre=?, zona=?, fecha_medicion=?, imagen_exterior_path=? WHERE id=?",
              (nombre, zona, fecha, imagen_path, centro_id))
    conn.commit()
    conn.close()


def delete_centro(centro_id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("DELETE FROM detectores WHERE centro_id=?", (centro_id,))
    c.execute("DELETE FROM centros WHERE id=?", (centro_id,))
    conn.commit()
    conn.close()


def insert_detector(data):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''INSERT INTO detectores
                 (centro_id, planta, sala, fecha, detector_codigo, plano_path,
                  punto_x, punto_y, foto_situacion_path, foto_detector_path, fecha_creacion)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)''', data)
    rowid = c.lastrowid
    conn.commit()
    conn.close()
    return rowid


def update_detector(detector_id, data):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute('''UPDATE detectores SET
                 centro_id=?, planta=?, sala=?, fecha=?, detector_codigo=?, plano_path=?,
                 punto_x=?, punto_y=?, foto_situacion_path=?, foto_detector_path=?, fecha_creacion=?
                 WHERE id=?''', data + (detector_id,))
    conn.commit()
    conn.close()


def fetch_detectores(centro_id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT * FROM detectores WHERE centro_id=? ORDER BY id ASC", (centro_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_detector(detector_id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT * FROM detectores WHERE id=?", (detector_id,))
    row = c.fetchone()
    conn.close()
    return row


def delete_detector(detector_id):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("DELETE FROM detectores WHERE id=?", (detector_id,))
    conn.commit()
    conn.close()


def get_tecnico():
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("SELECT tecnico FROM settings WHERE id=1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""


def set_tecnico(valor):
    conn = sqlite3.connect(get_db_path())
    c = conn.cursor()
    c.execute("UPDATE settings SET tecnico=? WHERE id=1", (valor,))
    conn.commit()
    conn.close()


# ============================================================
# UTILIDADES
# ============================================================

def _slug(texto):
    texto = (texto or "centro").lower()
    texto = re.sub(r"[^a-z0-9]+", "_", texto).strip("_")
    return texto or "centro"


def guardar_bytes_imagen(file_bytes, prefijo, ext=".jpg"):
    """Guarda bytes de una imagen (subida o capturada con la cámara) en la
    carpeta de datos y devuelve la ruta del archivo guardado."""
    data_dir = get_data_dir()
    nombre = f"{prefijo}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
    destino = os.path.join(data_dir, nombre)
    with open(destino, "wb") as f:
        f.write(file_bytes)
    return destino


def extension_de(uploaded_file, por_defecto=".jpg"):
    if uploaded_file is None:
        return por_defecto
    nombre = getattr(uploaded_file, "name", "") or ""
    ext = os.path.splitext(nombre)[1]
    return ext if ext else por_defecto


# ============================================================
# LOGOTIPO (para cabecera del informe PDF) - idéntico al original
# ============================================================

LOGO_PNG_B64 = (
    "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"
)

# ============================================================
# GENERAR PDF (idéntico al original, sin dependencias de Tkinter)
# ============================================================

def generar_pdf(centro_id, output_path):
    try:
        import base64
        import io
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.platypus import Image as RLImage
        from reportlab.lib.utils import ImageReader
        from PIL import Image as PILImage, ImageDraw
        
        centro = get_centro(centro_id)
        if not centro:
            raise ValueError("Centro no encontrado")
        
        _, nombre, zona, fecha, img_ext = centro
        detectores = fetch_detectores(centro_id)
        tecnico = get_tecnico()
        
        # ---- Logotipo (para cabecera de todas las paginas) ----
        logo_bytes = base64.b64decode(LOGO_PNG_B64)
        with PILImage.open(io.BytesIO(logo_bytes)) as _logo_im:
            logo_w_px, logo_h_px = _logo_im.size
        logo_aspect = logo_w_px / logo_h_px
        
        def _dibujar_cabecera(canvas_obj, doc_):
            canvas_obj.saveState()
            header_h = 1.3 * cm
            header_w = header_h * logo_aspect
            page_w, page_h = doc_.pagesize
            x = (page_w - header_w) / 2
            y = page_h - 0.5 * cm - header_h
            img_reader = ImageReader(io.BytesIO(logo_bytes))
            canvas_obj.drawImage(img_reader, x, y, width=header_w, height=header_h,
                                  mask='auto', preserveAspectRatio=True)
            canvas_obj.restoreState()
        
        doc = SimpleDocTemplate(output_path, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=3.2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        centrado = ParagraphStyle('Centrado', parent=styles['Normal'], alignment=TA_CENTER)
        nombre_style = ParagraphStyle('NombreCentro', parent=styles['Normal'],
                                       fontName='Helvetica-Bold', fontSize=20, leading=24,
                                       alignment=TA_CENTER, spaceAfter=4)
        zona_style = ParagraphStyle('ZonaCentro', parent=styles['Normal'],
                                     fontName='Helvetica', fontSize=20, leading=24,
                                     alignment=TA_CENTER, textColor=colors.HexColor('#444444'),
                                     spaceAfter=10)
        story = []
        
        story.append(Paragraph("Informe de colcación de detectores de Rn", styles["Title"]))
        story.append(Spacer(1, 0.6*cm))
        story.append(Paragraph(nombre or '-', nombre_style))
        if zona:
            story.append(Paragraph(zona, zona_style))
        story.append(Spacer(1, 0.3*cm))
        
        if img_ext and os.path.exists(img_ext):
            try:
                with PILImage.open(img_ext) as im_ext:
                    w, h = im_ext.size
                r = min(20*cm/w, 15*cm/h)
                img_portada = RLImage(img_ext, width=w*r, height=h*r)
                img_portada.hAlign = 'CENTER'
                story.append(img_portada)
                story.append(Spacer(1, 0.5*cm))
            except Exception:
                pass
        
        story.append(Paragraph(f"<b>Fecha:</b> {fecha or '-'}", centrado))
        if tecnico:
            story.append(Paragraph(f"<b>Responsable:</b> {tecnico}", centrado))
        story.append(Paragraph(f"<b>Detectores:</b> {len(detectores)}", centrado))
        story.append(Spacer(1, 0.5*cm))
        
        for idx, d in enumerate(detectores, 1):
            (did, _, planta, sala, fecha_det, codigo, plano, px, py, foto_sit, foto_det, _) = d
            story.append(PageBreak())
            
            titulo_partes = [codigo or "-", nombre or "-"]
            if zona:
                titulo_partes.append(zona)
            titulo_detector = f"Detector {idx}: " + " - ".join(titulo_partes)
            story.append(Paragraph(titulo_detector, styles["Heading2"]))
            
            tabla = Table([
                ["Planta", planta or "-"],
                ["Sala", sala or "-"],
                ["Codigo", codigo or "-"],
                ["Fecha", fecha_det or "-"],
            ], colWidths=[5*cm, 10*cm])
            tabla.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
                ("BACKGROUND", (0,0), (0,-1), colors.whitesmoke),
            ]))
            story.append(tabla)
            story.append(Spacer(1, 0.4*cm))
            
            if plano and os.path.exists(plano):
                story.append(Paragraph("Ubicacion en el plano:", styles["Heading4"]))
                try:
                    with PILImage.open(plano) as im_plano:
                        im_plano = im_plano.convert("RGB")
                        w, h = im_plano.size
                        if px is not None and py is not None and px >= 0 and py >= 0:
                            draw = ImageDraw.Draw(im_plano)
                            cx, cy = px * w, py * h
                            r = max(6, int(min(w, h) * 0.012))
                            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                                         fill=(220, 20, 20), outline=(120, 0, 0), width=2)
                        tmp_plano_path = os.path.join(get_data_dir(), f"_tmp_plano_{did}.jpg")
                        im_plano.save(tmp_plano_path, quality=90)
                    r = min(14*cm/w, 9*cm/h)
                    story.append(RLImage(tmp_plano_path, width=w*r, height=h*r))
                    story.append(Spacer(1, 0.4*cm))
                except Exception:
                    pass
            
            if foto_sit and os.path.exists(foto_sit) and foto_det and os.path.exists(foto_det):
                story.append(Paragraph("Fotos:", styles["Heading4"]))
                try:
                    with PILImage.open(foto_sit) as im:
                        w, h = im.size
                    r = min(7*cm/w, 7*cm/h)
                    img1 = RLImage(foto_sit, width=w*r, height=h*r)
                except:
                    img1 = Paragraph("(no disponible)", styles["Normal"])
                try:
                    with PILImage.open(foto_det) as im:
                        w, h = im.size
                    r = min(7*cm/w, 7*cm/h)
                    img2 = RLImage(foto_det, width=w*r, height=h*r)
                except:
                    img2 = Paragraph("(no disponible)", styles["Normal"])
                story.append(Table([[img1, img2]], colWidths=[8*cm, 8*cm]))
        
        doc.build(story, onFirstPage=_dibujar_cabecera, onLaterPages=_dibujar_cabecera)
        return True
    except Exception as e:
        raise Exception(f"Error: {str(e)}")


# ============================================================
# GENERAR EXCEL (hoja de cálculo del centro, con las fotos de cada
# detector incrustadas cada una en su propia celda)
# ============================================================

def generar_excel(centro_id, output_path):
    """Genera un .xlsx en formato de tabla "plana" (sin ningún bloque de
    cabecera encima), pensado para poder ir pegando debajo los datos de
    otros centros más adelante. El nombre del centro y el área figuran
    como las dos primeras columnas de cada fila, junto con todos los
    datos de cada detector y sus tres fotos (plano con el punto
    marcado, situación, detector) incrustadas cada una en su propia
    celda, manteniendo su proporción real."""
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    centro = get_centro(centro_id)
    if not centro:
        raise Exception("Centro no encontrado")
    cid, nombre, zona, fecha, img_centro = centro
    detectores = fetch_detectores(centro_id)

    FUENTE = "Arial"
    fuente_normal = Font(name=FUENTE, size=10)
    fuente_cabecera = Font(name=FUENTE, size=10, bold=True, color="FFFFFF")
    centrado = Alignment(horizontal="center", vertical="center", wrap_text=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Detectores"

    borde_fino = Border(*[Side(style="thin", color="CCCCCC")] * 4)

    # --- Tabla plana: nada por encima de la cabecera. "Centro" y "Área"
    # son las dos primeras columnas de cada fila, para poder pegar
    # debajo los datos de otros centros sin que estorbe ningún bloque. ---
    header_row = 1
    headers = [
        "Centro", "Área", "ID", "Planta", "Sala", "Código", "Fecha", "Hora",
        "Plano", "Foto situación", "Foto detector",
    ]
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row=header_row, column=i, value=h)
        c.font = fuente_cabecera
        c.fill = PatternFill("solid", fgColor="F97316")
        c.alignment = centrado
        c.border = borde_fino

    col_letra = {h: get_column_letter(i) for i, h in enumerate(headers, start=1)}
    for h in ("Plano", "Foto situación", "Foto detector"):
        ws.column_dimensions[col_letra[h]].width = 24
    for h in ("Centro", "Planta", "Sala", "Código", "Fecha"):
        ws.column_dimensions[col_letra[h]].width = 15
    ws.column_dimensions[col_letra["Área"]].width = 13
    ws.column_dimensions[col_letra["Hora"]].width = 8

    TAM_IMG_PX = 150  # tamaño MÁXIMO (lado mayor) de cada foto dentro de su celda

    fila = header_row + 1
    for d in detectores:
        (did, _, planta, sala, fecha_det, codigo, plano_p, punto_x, punto_y,
         foto_sit_p, foto_det_p, fecha_creacion) = d

        hora = (fecha_creacion or "").split(" ")[-1] if fecha_creacion else ""

        valores = [
            nombre or "", zona or "", did, planta or "", sala or "",
            codigo or "", fecha_det or "", hora,
        ]
        for col, val in enumerate(valores, start=1):
            c = ws.cell(row=fila, column=col, value=val)
            c.font = fuente_normal
            c.alignment = centrado
            c.border = borde_fino
        # Las tres celdas de fotos también con borde, aunque queden vacías
        for h in ("Plano", "Foto situación", "Foto detector"):
            ws[f"{col_letra[h]}{fila}"].border = borde_fino

        ws.row_dimensions[fila].height = 115  # espacio suficiente para las fotos

        hay_punto = (
            punto_x is not None and punto_y is not None
            and 0 <= punto_x <= 1 and 0 <= punto_y <= 1
        )

        for col_name, ruta in (
            ("Plano", plano_p),
            ("Foto situación", foto_sit_p),
            ("Foto detector", foto_det_p),
        ):
            if ruta and os.path.exists(ruta):
                try:
                    with Image.open(ruta) as im_orig:
                        # IMPORTANTE: las fotos de móvil llevan a menudo
                        # metadatos EXIF de rotación que PIL no aplica
                        # solo; sin esto, el ancho/alto "en bruto" no
                        # coincide con cómo se ve realmente la foto y la
                        # proporción calculada sale mal.
                        im = ImageOps.exif_transpose(im_orig)
                        im = im.convert("RGB")
                        if col_name == "Plano" and hay_punto:
                            # Dibujar el punto rojo del detector sobre el
                            # plano, igual que en el informe PDF.
                            draw = ImageDraw.Draw(im)
                            w, h = im.size
                            cx, cy = punto_x * w, punto_y * h
                            r = max(6, int(min(w, h) * 0.02))
                            draw.ellipse(
                                [cx - r, cy - r, cx + r, cy + r],
                                fill=(220, 20, 20), outline=(120, 0, 0), width=2,
                            )
                        im.thumbnail((900, 900))
                        buf = io.BytesIO()
                        im.save(buf, format="JPEG", quality=85)
                        buf.seek(0)
                        ancho_real, alto_real = im.size

                    # Escalar manteniendo la proporción real (sin
                    # deformar), ajustando al lado mayor = TAM_IMG_PX.
                    escala = min(TAM_IMG_PX / ancho_real, TAM_IMG_PX / alto_real)
                    xl_img = XLImage(buf)
                    xl_img.width = max(1, round(ancho_real * escala))
                    xl_img.height = max(1, round(alto_real * escala))
                    ws.add_image(xl_img, f"{col_letra[col_name]}{fila}")
                except Exception:
                    c_err = ws[f"{col_letra[col_name]}{fila}"]
                    c_err.value = "(no se pudo incrustar la imagen)"
                    c_err.font = fuente_normal
                    c_err.alignment = centrado
        fila += 1

    wb.save(output_path)
    return True


# ============================================================
# WIDGETS DE IMAGEN (Subir archivo / Cámara del navegador)
# Sustituyen a los botones "Seleccionar" / "Camara" de la app Tkinter.
# ============================================================

# Solo se permite un flujo de cámara abierto a la vez en TODO el
# formulario (plano, foto de situación, foto del detector, imagen del
# centro). Guarda qué campo "posee" la cámara ahora mismo; el resto no
# monta su propio st.camera_input hasta que ese campo la libere. Esto
# evita el error "no autorizado" que da el móvil cuando varios widgets
# intentan acceder a la cámara al mismo tiempo.
GLOBAL_CAM_OWNER_KEY = "_camara_activa_global"


def widget_imagen(label, state_key, key_prefix, con_camara=True, con_boton_quitar=True):
    """Selector de imagen con pestañas 'Subir' y 'Cámara'.

    Guarda automáticamente el archivo elegido en la carpeta de datos y
    recuerda la ruta en st.session_state[state_key]. Devuelve esa ruta
    (o None si no hay imagen).
    """
    st.markdown(f"**{label}**")
    file_id_key = key_prefix + "__file_id"
    cam_nonce_key = key_prefix + "__cam_nonce"
    cam_activa_key = key_prefix + "__cam_activa"
    if cam_nonce_key not in st.session_state:
        st.session_state[cam_nonce_key] = 0
    if cam_activa_key not in st.session_state:
        st.session_state[cam_activa_key] = False  # la cámara NO se activa sola

    tab_labels = ["📁 Subir"] + (["📷 Cámara"] if con_camara else [])
    tabs = st.tabs(tab_labels)
    nuevo_bytes = None
    nueva_ext = ".jpg"
    vino_de_camara = False

    with tabs[0]:
        up = st.file_uploader(
            "Selecciona una imagen", type=["png", "jpg", "jpeg"],
            key=key_prefix + "_up", label_visibility="collapsed",
        )
        if up is not None:
            fid = ("up", getattr(up, "file_id", None) or f"{up.name}_{up.size}")
            if st.session_state.get(file_id_key) != fid:
                nuevo_bytes = up.getvalue()
                nueva_ext = extension_de(up)
                st.session_state[file_id_key] = fid

    if con_camara:
        with tabs[1]:
            hay_imagen = bool(st.session_state.get(state_key))
            # Solo se permite UNA cámara activa a la vez en todo el formulario:
            # si otro campo la tiene abierta, este campo no monta su propio
            # visor (así se evita el error "no autorizado" por streams
            # de cámara simultáneos en el móvil).
            es_el_activo = st.session_state.get(GLOBAL_CAM_OWNER_KEY) == cam_activa_key
            otra_cam_en_uso = (
                st.session_state.get(GLOBAL_CAM_OWNER_KEY) is not None and not es_el_activo
            )

            if st.session_state[cam_activa_key] and es_el_activo:
                cam_key = f"{key_prefix}_cam_{st.session_state[cam_nonce_key]}"
                foto = st.camera_input(
                    "Capturar foto", key=cam_key, label_visibility="collapsed",
                )
                if foto is not None:
                    nuevo_bytes = foto.getvalue()
                    nueva_ext = ".jpg"
                    vino_de_camara = True
            else:
                if hay_imagen:
                    st.caption("Foto capturada (se muestra abajo).")
                etiqueta_btn = "📷 Tomar otra foto" if hay_imagen else "📷 Activar cámara"
                if otra_cam_en_uso:
                    st.caption("La cámara está siendo usada en otro campo. Termina esa foto primero.")
                elif st.button(etiqueta_btn, key=key_prefix + "_activar_cam"):
                    st.session_state[cam_activa_key] = True
                    st.session_state[GLOBAL_CAM_OWNER_KEY] = cam_activa_key
                    st.rerun()

    if nuevo_bytes is not None:
        path = guardar_bytes_imagen(nuevo_bytes, key_prefix, nueva_ext)
        st.session_state[state_key] = path
        if vino_de_camara:
            # Ocultamos el visor de la cámara y liberamos el "turno" para
            # que otro campo pueda activarla.
            st.session_state[cam_activa_key] = False
            st.session_state[cam_nonce_key] += 1
            if st.session_state.get(GLOBAL_CAM_OWNER_KEY) == cam_activa_key:
                st.session_state[GLOBAL_CAM_OWNER_KEY] = None
            st.rerun()

    path_actual = st.session_state.get(state_key)
    if con_boton_quitar:
        col_prev, col_btn = st.columns([3, 1])
    else:
        col_prev = st.container()
    with col_prev:
        if path_actual and os.path.exists(path_actual):
            st.image(path_actual, use_container_width=True)
        else:
            st.caption("Sin imagen")
    if con_boton_quitar:
        with col_btn:
            if path_actual and st.button("🗑️ Quitar", key=key_prefix + "_quitar"):
                st.session_state[state_key] = None
                st.session_state[file_id_key] = None
                st.session_state[cam_activa_key] = False
                if st.session_state.get(GLOBAL_CAM_OWNER_KEY) == cam_activa_key:
                    st.session_state[GLOBAL_CAM_OWNER_KEY] = None
                st.rerun()

    return st.session_state.get(state_key)


def widget_plano(state_prefix):
    """Gestiona la imagen del plano y el punto marcado con un clic/toque,
    igual que el canvas clicable de la app de escritorio.

    Solo admite subir un archivo (sin opción de cámara para el plano).
    """
    path_key = state_prefix + "_path"
    px_key = state_prefix + "_px"
    py_key = state_prefix + "_py"
    file_id_key = state_prefix + "__file_id"

    st.markdown("**Plano**")
    up = st.file_uploader(
        "Selecciona un plano", type=["png", "jpg", "jpeg"],
        key=state_prefix + "_up", label_visibility="collapsed",
    )
    nuevo_bytes = None
    if up is not None:
        fid = ("up", getattr(up, "file_id", None) or f"{up.name}_{up.size}")
        if st.session_state.get(file_id_key) != fid:
            nuevo_bytes = up.getvalue()
            st.session_state[file_id_key] = fid

    if nuevo_bytes is not None:
        path = guardar_bytes_imagen(nuevo_bytes, "plano")
        st.session_state[path_key] = path
        st.session_state[px_key] = None
        st.session_state[py_key] = None

    plano_path = st.session_state.get(path_key)
    if plano_path and os.path.exists(plano_path):
        st.caption(
            "Toca sobre el plano para marcar la ubicación del detector "
            "(el punto rojo aparecerá en el informe)."
        )
        try:
            img_orig = Image.open(plano_path).convert("RGB")
        except Exception:
            st.warning("No se pudo abrir la imagen del plano.")
            return plano_path, st.session_state.get(px_key), st.session_state.get(py_key)

        # Se redimensiona ANTES de mostrarla para que las coordenadas que
        # devuelve el componente coincidan exactamente con esta imagen.
        ancho_max = 680
        escala = min(1.0, ancho_max / img_orig.width)
        disp_w = max(1, int(img_orig.width * escala))
        disp_h = max(1, int(img_orig.height * escala))
        img_disp = img_orig.resize((disp_w, disp_h), Image.Resampling.LANCZOS)

        px = st.session_state.get(px_key)
        py = st.session_state.get(py_key)
        if px is not None and py is not None:
            draw = ImageDraw.Draw(img_disp)
            cx, cy = px * disp_w, py * disp_h
            r = max(6, int(min(disp_w, disp_h) * 0.02))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                         fill=(220, 20, 20), outline=(120, 0, 0), width=2)

        if IMG_COORD_DISPONIBLE:
            coords = streamlit_image_coordinates(img_disp, key=state_prefix + "_coords")
            if coords is not None:
                nuevo_px = max(0.0, min(1.0, coords["x"] / disp_w))
                nuevo_py = max(0.0, min(1.0, coords["y"] / disp_h))
                if (px, py) != (nuevo_px, nuevo_py):
                    st.session_state[px_key] = nuevo_px
                    st.session_state[py_key] = nuevo_py
                    st.rerun()
        else:
            st.image(img_disp, use_container_width=False)
            st.warning(
                "Para marcar el punto sobre el plano instala el componente:\n\n"
                "`pip install streamlit-image-coordinates`"
            )
    else:
        st.caption("Sin plano")

    return plano_path, st.session_state.get(px_key), st.session_state.get(py_key)


# ============================================================
# COMPARTIR PDF POR WHATSAPP (Web Share API - Android)
# ============================================================

def boton_compartir_whatsapp_archivo(ruta, nombre_archivo, mime_type, texto_mensaje,
                                      etiqueta_boton, id_sufijo, titulo_compartir):
    """Botón genérico que abre el diálogo nativo de "Compartir" de
    Android con UN archivo (PDF, Excel...) ya adjunto (el usuario elige
    WhatsApp), usando la Web Share API. Requisitos del navegador/dispositivo:
      - Android + Chrome (u otro navegador compatible).
      - La app debe servirse por HTTPS (o localhost). Si usas
        `streamlit run` en tu PC y accedes desde el móvil por IP local
        (http://192.168.x.x:8501) el navegador bloqueará esta función
        por no ser un "contexto seguro": usa un túnel HTTPS (p. ej.
        Cloudflare Tunnel, ngrok) o despliega en Streamlit Community
        Cloud.
    """
    with open(ruta, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    texto_js = texto_mensaje.replace("\\", "\\\\").replace("`", "\\`").replace("\n", "\\n")
    nombre_js = nombre_archivo.replace("\\", "\\\\").replace("`", "\\`")
    titulo_js = titulo_compartir.replace("\\", "\\\\").replace("`", "\\`")

    html = f"""
    <div style="font-family: 'Source Sans Pro', sans-serif;">
      <button id="btn-compartir-{id_sufijo}" style="
          background-color:#25D366; color:white; border:none;
          padding:12px 20px; border-radius:8px; font-size:16px;
          font-weight:600; cursor:pointer; width:100%;">
        {etiqueta_boton}
      </button>
      <p id="msg-compartir-{id_sufijo}" style="margin-top:8px; font-size:13px; color:#ccc;"></p>
    </div>
    <script>
      const b64_{id_sufijo} = "{b64}";
      const nombreArchivo_{id_sufijo} = `{nombre_js}`;
      const textoMensaje_{id_sufijo} = `{texto_js}`;
      const tituloCompartir_{id_sufijo} = `{titulo_js}`;
      const mimeType_{id_sufijo} = "{mime_type}";

      function b64ToBlob_{id_sufijo}(b64Data, contentType) {{
        const byteChars = atob(b64Data);
        const byteNumbers = new Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) {{
          byteNumbers[i] = byteChars.charCodeAt(i);
        }}
        const byteArray = new Uint8Array(byteNumbers);
        return new Blob([byteArray], {{ type: contentType }});
      }}

      const btn_{id_sufijo} = document.getElementById("btn-compartir-{id_sufijo}");
      const msg_{id_sufijo} = document.getElementById("msg-compartir-{id_sufijo}");

      btn_{id_sufijo}.addEventListener("click", async () => {{
        try {{
          const blob = b64ToBlob_{id_sufijo}(b64_{id_sufijo}, mimeType_{id_sufijo});
          const file = new File([blob], nombreArchivo_{id_sufijo}, {{ type: mimeType_{id_sufijo} }});

          if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
            await navigator.share({{
              files: [file],
              title: tituloCompartir_{id_sufijo},
              text: textoMensaje_{id_sufijo},
            }});
          }} else if (navigator.share) {{
            await navigator.share({{ title: tituloCompartir_{id_sufijo}, text: textoMensaje_{id_sufijo} }});
            msg_{id_sufijo}.textContent = "Tu navegador no admite adjuntar el archivo directamente; descárgalo y compártelo manualmente.";
          }} else {{
            msg_{id_sufijo}.textContent = "Tu navegador no soporta compartir archivos. Descárgalo con el botón de abajo y compártelo manualmente desde WhatsApp.";
          }}
        }} catch (err) {{
          if (err.name !== "AbortError") {{
            msg_{id_sufijo}.textContent = "No se pudo abrir el diálogo de compartir: " + err.message;
          }}
        }}
      }});
    </script>
    """
    components.html(html, height=110)


def boton_compartir_whatsapp(pdf_path, nombre_archivo, texto_mensaje):
    """Botón que comparte el PDF del informe por WhatsApp."""
    boton_compartir_whatsapp_archivo(
        pdf_path, nombre_archivo, "application/pdf", texto_mensaje,
        "📲 Enviar por WhatsApp", "pdf", "Informe de detectores de Rn",
    )


def boton_compartir_whatsapp_excel(xlsx_path, nombre_archivo, texto_mensaje):
    """Botón que comparte la hoja de cálculo del informe por WhatsApp."""
    boton_compartir_whatsapp_archivo(
        xlsx_path, nombre_archivo,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        texto_mensaje, "📊 Enviar Excel por WhatsApp", "xlsx",
        "Hoja de cálculo de detectores de Rn",
    )


def boton_compartir_whatsapp_fotos(imagenes, texto_mensaje):
    """Botón que comparte por WhatsApp SOLO las fotos marcadas en la
    checklist (sin el PDF), usando la Web Share API con varios archivos
    a la vez. Se separa del PDF a propósito: compartir un PDF mezclado
    con imágenes en el mismo envío falla en bastantes navegadores/apps.

    imagenes: lista de tuplas (ruta_en_disco, nombre_de_archivo).
    """
    archivos = []
    for ruta, nombre in imagenes:
        if not ruta or not os.path.exists(ruta):
            continue
        ext = os.path.splitext(nombre)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        with open(ruta, "rb") as f:
            archivos.append({
                "b64": base64.b64encode(f.read()).decode("utf-8"),
                "name": nombre,
                "type": mime,
            })

    if not archivos:
        st.caption("Marca al menos una foto arriba para poder enviarla.")
        return

    archivos_json = json.dumps(archivos)
    texto_json = json.dumps(texto_mensaje)
    n_fotos = len(archivos)

    html = f"""
    <div style="font-family: 'Source Sans Pro', sans-serif;">
      <button id="btn-compartir-fotos" style="
          background-color:#25D366; color:white; border:none;
          padding:12px 20px; border-radius:8px; font-size:16px;
          font-weight:600; cursor:pointer; width:100%;">
        🖼️ Enviar {n_fotos} foto(s) por WhatsApp
      </button>
      <p id="msg-compartir-fotos" style="margin-top:8px; font-size:13px; color:#ccc;"></p>
    </div>
    <script>
      const archivosDataFotos = {archivos_json};
      const textoMensajeFotos = {texto_json};

      function b64ToBlobFotos(b64Data, contentType) {{
        const byteChars = atob(b64Data);
        const byteNumbers = new Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) {{
          byteNumbers[i] = byteChars.charCodeAt(i);
        }}
        const byteArray = new Uint8Array(byteNumbers);
        return new Blob([byteArray], {{ type: contentType }});
      }}

      const btnFotos = document.getElementById("btn-compartir-fotos");
      const msgFotos = document.getElementById("msg-compartir-fotos");

      btnFotos.addEventListener("click", async () => {{
        try {{
          const files = archivosDataFotos.map(
            a => new File([b64ToBlobFotos(a.b64, a.type)], a.name, {{ type: a.type }})
          );
          if (navigator.canShare && navigator.canShare({{ files }})) {{
            await navigator.share({{
              files: files,
              title: "Fotos del informe de detectores de Rn",
              text: textoMensajeFotos,
            }});
          }} else if (navigator.share) {{
            await navigator.share({{ title: "Fotos del informe de detectores de Rn", text: textoMensajeFotos }});
            msgFotos.textContent = "Tu navegador no admite adjuntar varias fotos a la vez.";
          }} else {{
            msgFotos.textContent = "Tu navegador no soporta compartir archivos. Descarga las fotos manualmente.";
          }}
        }} catch (err) {{
          if (err.name !== "AbortError") {{
            msgFotos.textContent = "No se pudo abrir el diálogo de compartir: " + err.message;
          }}
        }}
      }});
    </script>
    """
    components.html(html, height=110)


def _limpiar_namespace(ns):
    borrar = [k for k in st.session_state.keys()
              if k == ns or k.startswith(ns + "_") or k.startswith(ns + "__")]
    for k in borrar:
        del st.session_state[k]
    # Si la cámara global la tenía un campo de este formulario, la
    # liberamos para que no quede "atascada" al salir de la pantalla.
    owner = st.session_state.get(GLOBAL_CAM_OWNER_KEY)
    if owner and (owner == ns or owner.startswith(ns + "_") or owner.startswith(ns + "__")):
        st.session_state[GLOBAL_CAM_OWNER_KEY] = None


def abrir_detector_nuevo():
    ns_previo = st.session_state.get("detector_form_ns")
    if ns_previo:
        _limpiar_namespace(ns_previo)
    st.session_state.detector_actual = None
    st.session_state.view = "detector"


def abrir_detector_editar(detector_id):
    ns_previo = st.session_state.get("detector_form_ns")
    if ns_previo:
        _limpiar_namespace(ns_previo)
    st.session_state.detector_actual = detector_id
    st.session_state.view = "detector"


# ============================================================
# PANTALLA: INICIO (lista de centros)
# ============================================================

def pantalla_inicio():
    col_t, col_a = st.columns([5, 1])
    with col_t:
        st.title("☢️ Detectores de Radón")
        st.markdown(
            '<p style="color:#F97316; font-size:1.1rem; font-weight:700; margin:0;">'
            'Registro de colocación</p>',
            unsafe_allow_html=True,
        )
    with col_a:
        if st.button("👤 Responsable"):
            st.session_state.view = "ajustes"
            st.rerun()

    with st.expander("➕ Nuevo centro"):
        with st.form("form_nuevo_centro", clear_on_submit=True):
            nombre_nuevo = st.text_input("Nombre del centro")
            crear = st.form_submit_button("Crear centro")
        if crear:
            if nombre_nuevo and nombre_nuevo.strip():
                cid = crear_centro(nombre_nuevo.strip())
                st.session_state.centro_actual = cid
                st.session_state.view = "centro"
                st.rerun()
            else:
                st.warning("Escribe un nombre para el centro")

    centros = fetch_centros()
    if not centros:
        st.info("No hay centros todavía. Crea el primero arriba con «➕ Nuevo centro».")
        return

    st.markdown("---")
    st.subheader("Centros registrados")

    opciones = list(range(len(centros)))
    etiquetas = {
        i: f"{c[1] or '(sin nombre)'}"
           + (f" · {c[2]}" if c[2] else "")
           + f"  (ID {c[0]})"
        for i, c in enumerate(centros)
    }
    idx_sel = st.selectbox(
        "Centro", options=opciones, format_func=lambda i: etiquetas[i],
        key="selector_centro_home", label_visibility="collapsed",
    )
    cid_sel, nombre_sel, zona_sel, fecha_sel, img_sel = centros[idx_sel]

    b1, b2 = st.columns([3, 1])
    with b1:
        if st.button("📂 Abrir centro", type="primary", use_container_width=True):
            st.session_state.centro_actual = cid_sel
            st.session_state.view = "centro"
            st.rerun()
    with b2:
        st.markdown('<div class="marcador-btn-eliminar"></div>', unsafe_allow_html=True)
        if st.button("❌ Eliminar", key="btn_eliminar_centro_home"):
            st.session_state["confirmar_borrado_centro"] = cid_sel
            st.rerun()

    if st.session_state.get("confirmar_borrado_centro") == cid_sel:
        st.warning(f"¿Eliminar el centro «{nombre_sel}» y todos sus detectores? Esta acción no se puede deshacer.")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("Sí, eliminar", key=f"confirmar_del_{cid_sel}", type="primary"):
                delete_centro(cid_sel)
                st.session_state["confirmar_borrado_centro"] = None
                st.rerun()
        with cc2:
            if st.button("Cancelar", key=f"cancelar_del_{cid_sel}"):
                st.session_state["confirmar_borrado_centro"] = None
                st.rerun()


# ============================================================
# PANTALLA: CENTRO (datos, detectores, generar PDF)
# ============================================================

def pantalla_centro():
    cid = st.session_state.centro_actual
    centro = get_centro(cid) if cid else None
    if not centro:
        st.error("Centro no encontrado.")
        if st.button("← Volver"):
            st.session_state.view = "inicio"
            st.rerun()
        return

    cid, nombre, zona, fecha, img_path = centro

    if st.button("← Volver a Centros"):
        st.session_state.view = "inicio"
        st.rerun()

    st.title(f"🏢 {nombre}")

    with st.expander("Datos del centro", expanded=True):
        ns_centro = f"centro_{cid}"
        # OJO: Streamlit borra el valor de un text_input de su
        # session_state en cuanto ese widget deja de renderizarse en
        # una ejecución (p.ej. al salir a la pantalla de inicio). Por
        # eso aquí se usa "value=" directamente con el dato de la base
        # de datos en cada entrada a la pantalla, en vez de precargarlo
        # solo la primera vez (ese patrón perdía los datos al volver).
        img_key = ns_centro + "_img"
        if img_key not in st.session_state:
            st.session_state[img_key] = img_path

        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Nombre", value=nombre or "", key=ns_centro + "_nombre")
            st.text_input("Área", value=zona or "", key=ns_centro + "_zona")
            st.text_input(
                "Fecha", value=fecha or datetime.now().strftime("%d/%m/%Y"),
                key=ns_centro + "_fecha",
            )
        with c2:
            widget_imagen("Imagen exterior", img_key, key_prefix=ns_centro + "_imgw", con_boton_quitar=False)

        if st.button("💾 Guardar centro"):
            nombre_in = st.session_state[ns_centro + "_nombre"].strip()
            if not nombre_in:
                st.warning("El nombre es obligatorio")
            else:
                update_centro(
                    cid, nombre_in,
                    st.session_state[ns_centro + "_zona"].strip(),
                    st.session_state[ns_centro + "_fecha"].strip(),
                    st.session_state.get(img_key),
                )
                st.success("Centro guardado")
                st.rerun()

    st.markdown("---")
    st.subheader("Detectores colocados")

    if st.button("➕ Nuevo detector"):
        abrir_detector_nuevo()
        st.rerun()

    detectores = fetch_detectores(cid)
    if not detectores:
        st.info("Todavía no se han añadido detectores para este centro.")
    else:
        opciones = list(range(len(detectores)))
        etiquetas = {}
        for i, d in enumerate(detectores):
            did, _, planta, sala, fecha_det, codigo = d[0], d[1], d[2], d[3], d[4], d[5]
            partes = [codigo or f"Detector {did}"]
            if sala:
                partes.append(sala)
            if planta:
                partes.append(f"Planta {planta}")
            etiquetas[i] = " · ".join(partes) + f"  (ID {did})"

        idx_sel = st.selectbox(
            "Detector", options=opciones, format_func=lambda i: etiquetas[i],
            key=f"selector_detector_{cid}", label_visibility="collapsed",
        )
        d_sel = detectores[idx_sel]
        did_sel = d_sel[0]

        b1, b2 = st.columns([3, 1])
        with b1:
            if st.button("📂 Abrir detector", type="primary", use_container_width=True):
                abrir_detector_editar(did_sel)
                st.rerun()
        with b2:
            st.markdown('<div class="marcador-btn-eliminar"></div>', unsafe_allow_html=True)
            if st.button("❌ Eliminar", key="btn_eliminar_detector_home"):
                st.session_state["confirmar_borrado_det"] = did_sel
                st.rerun()

        if st.session_state.get("confirmar_borrado_det") == did_sel:
            st.warning("¿Eliminar este detector? Esta acción no se puede deshacer.")
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("Sí, eliminar", key=f"conf_del_det_{did_sel}", type="primary"):
                    delete_detector(did_sel)
                    st.session_state["confirmar_borrado_det"] = None
                    st.rerun()
            with cc2:
                if st.button("Cancelar", key=f"cancel_del_det_{did_sel}"):
                    st.session_state["confirmar_borrado_det"] = None
                    st.rerun()

    st.markdown("---")
    st.subheader("📄 Informe PDF")

    if not detectores:
        st.caption("Añade al menos un detector para poder generar el informe.")
    else:
        if st.button("Generar PDF", type="primary"):
            try:
                nombre_pdf = f"informe_{_slug(nombre)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                ruta_pdf = os.path.join(get_data_dir(), nombre_pdf)
                with st.spinner("Generando informe..."):
                    generar_pdf(cid, ruta_pdf)
                st.session_state["ultimo_pdf"] = ruta_pdf
                st.session_state["ultimo_pdf_nombre"] = nombre_pdf
                st.session_state["ultimo_pdf_centro"] = cid
                st.success("PDF generado correctamente")
            except Exception as e:
                st.error(f"Error al generar el PDF: {e}")

        ultimo_pdf = st.session_state.get("ultimo_pdf")
        if ultimo_pdf and os.path.exists(ultimo_pdf) and st.session_state.get("ultimo_pdf_centro") == cid:
            with open(ultimo_pdf, "rb") as f:
                pdf_bytes = f.read()
            st.download_button(
                "⬇️ Descargar PDF", data=pdf_bytes,
                file_name=st.session_state.get("ultimo_pdf_nombre", "informe.pdf"),
                mime="application/pdf",
            )
            texto_wa = f"Informe de colocación de detectores de Rn – {nombre or ''}"
            boton_compartir_whatsapp(
                ultimo_pdf,
                st.session_state.get("ultimo_pdf_nombre", "informe.pdf"),
                texto_wa,
            )

            # Checklist de fotos del informe (imagen exterior del centro y
            # plano/situación/detector de cada detector) para elegir cuáles
            # se adjuntan junto al PDF al enviar por WhatsApp.
            fotos_disponibles = []
            if img_path and os.path.exists(img_path):
                ext = os.path.splitext(img_path)[1] or ".jpg"
                fotos_disponibles.append({
                    "ruta": img_path,
                    "nombre_archivo": f"exterior_{_slug(nombre)}{ext}",
                    "etiqueta": "Foto exterior del centro",
                })
            for d in detectores:
                did_d, codigo_d = d[0], d[5]
                plano_d, foto_sit_d, foto_det_d = d[6], d[9], d[10]
                base_id = codigo_d or f"Detector {did_d}"
                if plano_d and os.path.exists(plano_d):
                    ext = os.path.splitext(plano_d)[1] or ".jpg"
                    fotos_disponibles.append({
                        "ruta": plano_d, "nombre_archivo": f"plano_det{did_d}{ext}",
                        "etiqueta": f"Plano — {base_id}",
                    })
                if foto_sit_d and os.path.exists(foto_sit_d):
                    ext = os.path.splitext(foto_sit_d)[1] or ".jpg"
                    fotos_disponibles.append({
                        "ruta": foto_sit_d, "nombre_archivo": f"situacion_det{did_d}{ext}",
                        "etiqueta": f"Foto situación — {base_id}",
                    })
                if foto_det_d and os.path.exists(foto_det_d):
                    ext = os.path.splitext(foto_det_d)[1] or ".jpg"
                    fotos_disponibles.append({
                        "ruta": foto_det_d, "nombre_archivo": f"detector_det{did_d}{ext}",
                        "etiqueta": f"Foto detector — {base_id}",
                    })

            if fotos_disponibles:
                st.markdown("**Fotos del informe:**")

                sb1, sb2 = st.columns(2)
                with sb1:
                    if st.button("☑️ Seleccionar todas", key=f"wa_selall_{cid}", use_container_width=True):
                        for i, foto in enumerate(fotos_disponibles):
                            st.session_state[f"wa_chk_{cid}_{i}_{_slug(foto['nombre_archivo'])}"] = True
                        st.rerun()
                with sb2:
                    if st.button("⬜ Quitar selección", key=f"wa_deselall_{cid}", use_container_width=True):
                        for i, foto in enumerate(fotos_disponibles):
                            st.session_state[f"wa_chk_{cid}_{i}_{_slug(foto['nombre_archivo'])}"] = False
                        st.rerun()

                seleccionadas = []
                for i, foto in enumerate(fotos_disponibles):
                    marcado = st.checkbox(
                        foto["etiqueta"],
                        key=f"wa_chk_{cid}_{i}_{_slug(foto['nombre_archivo'])}",
                    )
                    if marcado:
                        seleccionadas.append((foto["ruta"], foto["nombre_archivo"]))

                texto_wa_fotos = f"Fotos del informe – {nombre or ''}"
                boton_compartir_whatsapp_fotos(seleccionadas, texto_wa_fotos)
                if not seleccionadas:
                    st.caption("Marca las fotos que quieras adjuntar además del PDF.")

            st.caption(
                "El botón de WhatsApp abre el panel nativo de «Compartir» de Android "
                "con el PDF ya adjunto (tú eliges el chat). Requiere que la app se "
                "sirva por HTTPS — ver notas en el README."
            )

        st.markdown("---")
        st.subheader("📊 Hoja de cálculo")
        if st.button("Generar Excel", type="primary"):
            try:
                nombre_xlsx = f"detectores_{_slug(nombre)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                ruta_xlsx = os.path.join(get_data_dir(), nombre_xlsx)
                with st.spinner("Generando hoja de cálculo (incrustando fotos)..."):
                    generar_excel(cid, ruta_xlsx)
                st.session_state["ultimo_excel"] = ruta_xlsx
                st.session_state["ultimo_excel_nombre"] = nombre_xlsx
                st.session_state["ultimo_excel_centro"] = cid
                st.success("Excel generado correctamente")
            except Exception as e:
                st.error(f"Error al generar el Excel: {e}")

        ultimo_excel = st.session_state.get("ultimo_excel")
        if ultimo_excel and os.path.exists(ultimo_excel) and st.session_state.get("ultimo_excel_centro") == cid:
            with open(ultimo_excel, "rb") as f:
                excel_bytes = f.read()
            st.download_button(
                "⬇️ Descargar Excel", data=excel_bytes,
                file_name=st.session_state.get("ultimo_excel_nombre", "detectores.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            texto_wa_excel = f"Hoja de cálculo de detectores de Rn – {nombre or ''}"
            boton_compartir_whatsapp_excel(
                ultimo_excel,
                st.session_state.get("ultimo_excel_nombre", "detectores.xlsx"),
                texto_wa_excel,
            )
            st.caption(
                "Incluye todos los datos de cada detector, con el plano y las "
                "fotos de situación y del detector incrustados cada uno en su "
                "propia celda."
            )


# ============================================================
# PANTALLA: DETECTOR (nuevo / editar)
# ============================================================

def pantalla_detector():
    cid = st.session_state.centro_actual
    detector_id = st.session_state.detector_actual
    ns = f"det_{detector_id or 'nuevo'}"
    st.session_state["detector_form_ns"] = ns

    init_key = ns + "__cargado"
    if not st.session_state.get(init_key):
        if detector_id:
            d = get_detector(detector_id)
            (did, _, planta, sala, fecha, codigo, plano, px, py, foto_sit, foto_det, _) = d
        else:
            centro = get_centro(cid)
            planta = sala = codigo = ""
            fecha = centro[3] if centro else datetime.now().strftime("%d/%m/%Y")
            plano = foto_sit = foto_det = None
            px = py = None

        st.session_state[ns + "_planta"] = planta or ""
        st.session_state[ns + "_sala"] = sala or ""
        st.session_state[ns + "_fecha"] = fecha or datetime.now().strftime("%d/%m/%Y")
        st.session_state[ns + "_codigo"] = codigo or ""
        st.session_state[ns + "_plano_path"] = plano
        st.session_state[ns + "_plano_px"] = px if (px is not None and px >= 0) else None
        st.session_state[ns + "_plano_py"] = py if (py is not None and py >= 0) else None
        st.session_state[ns + "_foto_sit"] = foto_sit
        st.session_state[ns + "_foto_det"] = foto_det
        st.session_state[init_key] = True

    if st.button("← Volver al centro"):
        _limpiar_namespace(ns)
        st.session_state.view = "centro"
        st.rerun()

    st.title("✏️ Editar detector" if detector_id else "➕ Nuevo detector")

    st.subheader("Datos del detector")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Planta", key=ns + "_planta")
        st.text_input("Sala", key=ns + "_sala")
    with c2:
        st.text_input("Fecha", key=ns + "_fecha")
        st.text_input("Código", key=ns + "_codigo")

    st.markdown("---")
    widget_plano(ns + "_plano")

    st.markdown("---")
    st.subheader("Fotos (lado a lado)")
    fc1, fc2 = st.columns(2)
    with fc1:
        widget_imagen("Situación", ns + "_foto_sit", key_prefix=ns + "_fsit")
    with fc2:
        widget_imagen("Detector", ns + "_foto_det", key_prefix=ns + "_fdet")

    st.markdown("---")
    b1, b2 = st.columns(2)
    with b1:
        guardar = st.button("💾 Guardar detector", type="primary", use_container_width=True)
    with b2:
        cancelar = st.button("Cancelar", use_container_width=True)

    if cancelar:
        _limpiar_namespace(ns)
        st.session_state.view = "centro"
        st.rerun()

    if guardar:
        sala_val = st.session_state[ns + "_sala"].strip()
        codigo_val = st.session_state[ns + "_codigo"].strip()
        if not sala_val:
            st.warning("La sala es obligatoria")
        elif not codigo_val:
            st.warning("El código es obligatorio")
        else:
            px = st.session_state.get(ns + "_plano_px")
            py = st.session_state.get(ns + "_plano_py")
            data = (
                cid,
                st.session_state[ns + "_planta"].strip(),
                sala_val,
                st.session_state[ns + "_fecha"].strip(),
                codigo_val,
                st.session_state.get(ns + "_plano_path"),
                px if px is not None else -1,
                py if py is not None else -1,
                st.session_state.get(ns + "_foto_sit"),
                st.session_state.get(ns + "_foto_det"),
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            )
            if detector_id:
                update_detector(detector_id, data)
            else:
                insert_detector(data)

            _limpiar_namespace(ns)
            st.session_state.view = "centro"
            st.success("Detector guardado")
            st.rerun()


# ============================================================
# PANTALLA: AJUSTES
# ============================================================

def pantalla_ajustes():
    st.title("👤 Responsable")
    if st.button("← Volver"):
        st.session_state.view = "centro" if st.session_state.get("centro_actual") else "inicio"
        st.rerun()

    st.text_input(
        "Responsable (aparece en el PDF)",
        value=get_tecnico(),
        key="ajustes_tecnico",
    )
    if st.button("Guardar ajustes", type="primary"):
        set_tecnico(st.session_state["ajustes_tecnico"].strip())
        st.session_state.view = "inicio"
        st.rerun()


# ============================================================
# MAIN
# ============================================================

def main():
    init_db()

    if "view" not in st.session_state:
        st.session_state.view = "inicio"
    if "centro_actual" not in st.session_state:
        st.session_state.centro_actual = None
    if "detector_actual" not in st.session_state:
        st.session_state.detector_actual = None

    view = st.session_state.view
    if view == "inicio":
        pantalla_inicio()
    elif view == "centro":
        pantalla_centro()
    elif view == "detector":
        pantalla_detector()
    elif view == "ajustes":
        pantalla_ajustes()
    else:
        st.session_state.view = "inicio"
        st.rerun()


if __name__ == "__main__":
    main()
