# app.py (Versión de Alto Rendimiento / Todo-en-Uno)

from flask import Flask, request, jsonify, render_template
import pytesseract
from PIL import Image
import io
import pandas as pd
import traceback
import re
import os
import google.generativeai as genai
import json

# --- CONFIGURACIÓN DE TESSERACT PORTÁTIL ---
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
    # Limpiamos el NaN de la descripción desde el principio
    df_sustancias['Declaración de seguridad'] = df_sustancias['Declaración de seguridad'].fillna("No hay una declaración de seguridad disponible.")
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

# --- NUEVA FUNCIÓN DE IA "TODO EN UNO" ---
def analizar_receta_con_ia(texto_receta, df_sustancias_conocidas):
    if not gemini_model:
        return {'error': 'El modelo de IA no está configurado.'}

    lista_sustancias_str = ", ".join(df_sustancias_conocidas['nombre_lower'].unique())

    prompt = f"""
    Eres un asistente farmacéutico experto. Realiza las siguientes tareas en orden:
    1.  Analiza el siguiente texto de una receta o lista de ingredientes:
        --- TEXTO A ANALIZAR ---
        {texto_receta}
        --- FIN DEL TEXTO ---

    2.  De ese texto, extrae todos los nombres de medicamentos o sustancias que puedas identificar.

    3.  Compara los nombres que extrajiste con la siguiente lista de sustancias de riesgo conocido que te proporciono:
        --- LISTA DE SUSTANCIAS CONOCIDAS ---
        {lista_sustancias_str}
        --- FIN DE LA LISTA ---

    4.  Para cada sustancia que encontraste TANTO en el texto de la receta COMO en la lista de sustancias conocidas, busca su información correspondiente en los datos que te doy más abajo y agrégala a una lista.

    5.  Crea un resumen en lenguaje sencillo sobre los riesgos de las sustancias encontradas. Si no encuentras ninguna sustancia de riesgo, di que no se encontraron sustancias de riesgo conocido en la base de datos.

    6.  Devuelve tu respuesta ÚNICAMENTE como un objeto JSON válido, sin texto adicional antes o después. El JSON debe tener la siguiente estructura exacta:
        {{
          "sustancias_analizadas": [{{ "nombre": "Nombre Completo de la Sustancia del CSV", "categoria": "Categoría del CSV", "descripcion": "Descripción del CSV" }}],
          "sustancias_desconocidas": ["Nombre de sustancia encontrada en la receta pero no en la lista del CSV"],
          "resumen_llm": "Tu resumen en lenguaje sencillo aquí."
        }}

    Aquí están los datos completos de las sustancias conocidas para que los uses en el paso 4. Usa el nombre exacto de la columna 'Nombre' para el resultado:
    --- DATOS COMPLETOS CSV ---
    {df_sustancias_conocidas.to_json(orient='records')}
    --- FIN DE DATOS CSV ---
    """

    try:
        print("Enviando una ÚNICA llamada a la IA para análisis completo...")
        # Aumentamos el timeout por si la tarea es compleja
        request_options = {"timeout": 120}
        response = gemini_model.generate_content(prompt, request_options=request_options)
        
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        print("Respuesta recibida y limpiada. Intentando decodificar JSON...")
        
        resultado_json = json.loads(cleaned_response)
        return resultado_json

    except json.JSONDecodeError:
        print(f"ERROR FATAL: La respuesta de la IA no es un JSON válido. Respuesta recibida:\n{response.text}")
        return {'sustancias_analizadas': [], 'sustancias_desconocidas': [], 'resumen_llm': 'Error: El asistente de IA no respondió con el formato esperado. Por favor, intenta de nuevo.'}
    except Exception as e:
        print(f"ERROR al llamar a la API de IA: {e}")
        return {'error': f'Error al comunicarse con el asistente de IA: {e}'}

# --- Rutas de la aplicación ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({'error': 'No se encontró ningún archivo'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    if file and not df_sustancias.empty:
        try:
            image_bytes = file.read()
            image = Image.open(io.BytesIO(image_bytes))
            
            print("\n--- NUEVO ANÁLISIS (MODO ALTO RENDIMIENTO) ---")
            texto_extraido = pytesseract.image_to_string(image, lang='spa')

            # Llamamos a la nueva función "todo en uno"
            resultado_ia = analizar_receta_con_ia(texto_extraido, df_sustancias)

            if 'error' in resultado_ia:
                return jsonify({'error': resultado_ia['error']}), 500

            return jsonify({
                'texto_completo': texto_extraido,
                'sustancias_analizadas': resultado_ia.get('sustancias_analizadas', []),
                'sustancias_desconocidas': resultado_ia.get('sustancias_desconocidas', []),
                'resumen_llm': resultado_ia.get('resumen_llm', '')
            })

        except Exception as e:
            print(f"ERROR DURANTE EL PROCESAMIENTO: {traceback.format_exc()}")
            return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500
            
    return jsonify({'error': 'No se pudo procesar el archivo o la base de datos no está cargada.'}), 500

if __name__ == '__main__':
    app.run(debug=True)