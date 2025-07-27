# app.py

from flask import Flask, request, jsonify, render_template
import pytesseract
from PIL import Image
import io
import pandas as pd
import traceback
import re
import os
import google.generativeai as genai

# --- CONFIGURACIÓN DE TESSERACT 
tesseract_path = os.getenv("TESSERACT_CMD")
if tesseract_path:
    print(f"Usando ruta de Tesseract desde la variable de entorno: {tesseract_path}")
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
else:
    print("Variable de entorno TESSERACT_CMD no encontrada. Se usará la ruta por defecto del sistema.")

# --- CONFIGURACIÓN DE LA API DE GOOGLE GEMINI ---
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ADVERTENCIA: La variable de entorno GOOGLE_API_KEY no está configurada. Las funciones de IA no funcionarán.")
        gemini_model = None
    else:
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        print("API de Google Gemini configurada correctamente.")
except Exception as e:
    print(f"ERROR al configurar la API de Gemini: {e}")
    gemini_model = None

# --- Carga y preparación de datos ---
try:
    df_sustancias = pd.read_csv('sustancias.csv', encoding='latin-1')
    df_sustancias['nombre_lower'] = df_sustancias['Nombre'].str.lower()
    if 'NombreNormalizado' in df_sustancias.columns:
        df_sustancias['normalizado_lower'] = df_sustancias['NombreNormalizado'].str.lower().fillna('')
    print("El archivo sustancias.csv se cargó correctamente.")
except FileNotFoundError:
    print("ADVERTENCIA: El archivo 'sustancias.csv' no fue encontrado. La búsqueda de sustancias no funcionará.")
    df_sustancias = pd.DataFrame()
except Exception as e:
    print(f"ERROR al leer el archivo CSV: {e}")
    df_sustancias = pd.DataFrame()

# --- Inicialización de Flask ---
app = Flask(__name__)

# --- Funciones de IA ---

def extraer_medicamentos_con_ia(texto_receta):
    if not gemini_model:
        return []

    prompt = (
        "Analiza el siguiente texto. Tu única tarea es extraer los nombres de los medicamentos o sustancias activas. "
        "Devuelve únicamente una lista de estos nombres, separados por comas. "
        "Ignora dosis, instrucciones, nombres de doctores o cualquier otra palabra. "
        "Si no encuentras ningún medicamento, devuelve una respuesta vacía.\n\n"
        "Texto a analizar:\n"
        f"--- INICIO ---\n{texto_receta}\n--- FIN ---"
    )

    try:
        print("Enviando prompt a Gemini para EXTRACCIÓN de medicamentos...")
        response = gemini_model.generate_content(prompt)
        medicamentos_extraidos = response.text.strip()
        print(f"Medicamentos extraídos por la IA: '{medicamentos_extraidos}'")
        
        if medicamentos_extraidos:
            lista_medicamentos = [med.strip() for med in medicamentos_extraidos.split(',') if med.strip()]
            return lista_medicamentos
        return []
    except Exception as e:
        print(f"ERROR al extraer medicamentos con la IA: {e}")
        return []

def generar_resumen_ia(sustancias):
    if not gemini_model or not sustancias:
        return "No se encontraron sustancias conocidas para generar un resumen."

    prompt_parts = [
        "Actúa como un asistente farmacéutico empático y muy claro. Te daré una lista de sustancias encontradas en un producto y su categoría de riesgo en el embarazo (A, B, C, D, X).",
        "Tu misión es explicar en un lenguaje extremadamente sencillo, directo y sin tecnicismos qué significan estos riesgos para una mujer embarazada o que planea estarlo.",
        "Resume el nivel de precaución necesario. Al final, SIEMPRE debes incluir la recomendación enfática de consultar a un médico antes de tomar cualquier decisión.",
        "\nAquí están las sustancias:\n"
    ]

    for sustancia in sustancias:
        prompt_parts.append(f"- **{sustancia['nombre']} (Categoría {sustancia['categoria']}):** {sustancia['descripcion']}")

    prompt_parts.append("\nGenera un resumen consolidado y fácil de entender basado en esta información.")
    prompt = "\n".join(prompt_parts)

    try:
        print("Enviando prompt a Gemini para RESUMEN de riesgos...")
        response = gemini_model.generate_content(prompt)
        print("Resumen de riesgos recibido de Gemini.")
        return response.text
    except Exception as e:
        print(f"ERROR al llamar a la API de Gemini para resumen: {e}")
        return "Hubo un error al generar el resumen de riesgos."

# --- Rutas de la aplicación ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No se encontró ningún archivo'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    if file and not df_sustancias.empty:
        try:
            image_bytes = file.read()
            image = Image.open(io.BytesIO(image_bytes))
            
            print("Iniciando extracción de texto con Tesseract...")
            texto_extraido = pytesseract.image_to_string(image, lang='spa')
            print(f"Texto completo extraído: '{texto_extraido[:200]}...'")

            lista_medicamentos_ia = extraer_medicamentos_con_ia(texto_extraido)

            sustancias_analizadas = []
            sustancias_desconocidas = []
            nombres_ya_agregados = set()

            print("Clasificando medicamentos extraídos por la IA...")
            for medicamento_nombre in lista_medicamentos_ia:
                medicamento_lower = medicamento_nombre.lower()
                encontrado = False
                
                for _, row in df_sustancias.iterrows():
                    nombres_a_buscar = {str(row['nombre_lower'])}
                    if 'normalizado_lower' in row and pd.notna(row['normalizado_lower']) and row['normalizado_lower']:
                        nombres_a_buscar.add(str(row['normalizado_lower']))
                    
                    if medicamento_lower in nombres_a_buscar:
                        if row['Nombre'] not in nombres_ya_agregados:
                            print(f"✔️ Sustancia CONOCIDA encontrada: {row['Nombre']}")
                            info_sustancia = { 'nombre': row['Nombre'], 'categoria': row['Categoría'], 'descripcion': row['Declaración de seguridad'] }
                            sustancias_analizadas.append(info_sustancia)
                            nombres_ya_agregados.add(row['Nombre'])
                            encontrado = True
                            break
                
                if not encontrado and medicamento_nombre not in nombres_ya_agregados:
                    print(f"⚠️ Sustancia DESCONOCIDA detectada: {medicamento_nombre}")
                    sustancias_desconocidas.append(medicamento_nombre)
                    nombres_ya_agregados.add(medicamento_nombre)

            resumen_llm = generar_resumen_ia(sustancias_analizadas)
            
            return jsonify({
                'texto_completo': texto_extraido,
                'sustancias_analizadas': sustancias_analizadas,
                'sustancias_desconocidas': sustancias_desconocidas,
                'resumen_llm': resumen_llm
            })

        except Exception as e:
            print(f"ERROR DURANTE EL PROCESAMIENTO: {traceback.format_exc()}")
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500
            
    return jsonify({'error': 'No se pudo procesar el archivo o la base de datos no está cargada.'}), 500

if __name__ == '__main__':
    app.run(debug=True)