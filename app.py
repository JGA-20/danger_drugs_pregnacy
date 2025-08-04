from flask import Flask, request, jsonify, render_template
import pytesseract
from PIL import Image
import io
import pandas as pd
import traceback
import os
import google.generativeai as genai
import json

# --- 2. Configuraciones ---
tesseract_path = os.getenv("TESSERACT_CMD")
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("ADVERTENCIA: GOOGLE_API_KEY no encontrada. La IA no funcionará.")
        gemini_model = None
    else:
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        print("API de Google Gemini configurada correctamente.")
except Exception as e:
    print(f"ERROR al configurar la API de Gemini: {e}")
    gemini_model = None

try:
    df_sustancias = pd.read_csv('sustancias.csv', encoding='latin-1')
    df_sustancias.fillna('', inplace=True)
    df_sustancias['nombre_lower'] = df_sustancias['Nombre'].str.lower()
    if 'NombreNormalizado' in df_sustancias.columns:
        df_sustancias['normalizado_lower'] = df_sustancias['NombreNormalizado'].str.lower()
    print("El archivo sustancias.csv se cargó y limpió correctamente.")
except Exception as e:
    print(f"ERROR al leer el archivo CSV: {e}")
    df_sustancias = pd.DataFrame()

app = Flask(__name__)

# --- 3. Funciones de Ayuda ---

def extraer_medicamentos_con_ia(texto_receta):
    """Extrae nombres de medicamentos del texto OCR."""
    if not gemini_model: return []
    prompt = "Analiza el siguiente texto. Extrae SOLAMENTE los nombres de los medicamentos o sustancias. Devuelve una lista separada por comas. Ejemplo: Ibuprofeno, Paracetamol, Aspirina.\n\nTexto: " + texto_receta
    try:
        print("Enviando 1ª llamada a la IA para EXTRACCIÓN...")
        response = gemini_model.generate_content(prompt)
        medicamentos_extraidos = response.text.strip()
        print(f"Medicamentos extraídos por la IA: '{medicamentos_extraidos}'")
        return [med.strip() for med in medicamentos_extraidos.split(',') if med.strip()]
    except Exception as e:
        print(f"ERROR en la extracción con IA: {e}")
        return []

def generar_resumen_ia(sustancias_analizadas):
    """Genera un resumen de los riesgos en tono amigable."""
    if not gemini_model or not sustancias_analizadas:
        return "No encontramos información de riesgo sobre las sustancias detectadas en nuestra base de datos."

    prompt_parts = [
        "Actúa como una experta en farmacia que habla con otra amiga que está embarazada. Tu tono debe ser cercano, tranquilizador y muy fácil de entender si pecar de muy amigable.",
        "Olvídate de los tecnicismos. Explica en lenguaje coloquial qué significan los riesgos de estas sustancias. Usa analogías si es necesario, como 'piénsalo como una luz de semáforo'.",
        "Al final, cierra la conversación con una recomendación cálida pero firme de que hable con su doctor, algo como 'recuerda que yo soy solo una ayuda, la última palabra siempre la tiene tu médico de confianza'.",
        "\nAquí te paso lo que encontré:\n"
    ]

    for sustancia in sustancias_analizadas:
        prompt_parts.append(f"- {sustancia['nombre']} (Categoría {sustancia['categoria']}): {sustancia['descripcion']}")
    
    try:
        print("Enviando 2ª llamada a la IA para RESUMEN (tono amigable)...")
        response = gemini_model.generate_content("\n".join(prompt_parts))
        print("Resumen amigable recibido.")
        return response.text
    except Exception as e:
        print(f"ERROR en el resumen con IA: {e}")
        return "Tuvimos un problema al generar el resumen."

# --- 4. Rutas de la Aplicación ---

@app.route('/')
def home():
    """Sirve la página principal."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """El orquestador principal: OCR -> IA Extracción -> Python Clasificación -> IA Resumen."""
    if 'file' not in request.files: return jsonify({'error': 'No se encontró ningún archivo'}), 400
    file = request.files['file']
    if not file.filename: return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    if df_sustancias.empty:
        return jsonify({'error': 'La base de datos de sustancias no está cargada en el servidor.'}), 500

    try:
        print("\n--- INICIANDO NUEVO ANÁLISIS ---")
        image_bytes = file.read()
        texto_extraido = pytesseract.image_to_string(Image.open(io.BytesIO(image_bytes)), lang='spa')
        
        lista_medicamentos_ia = extraer_medicamentos_con_ia(texto_extraido)
        if not lista_medicamentos_ia:
             return jsonify({'texto_completo': texto_extraido, 'sustancias_analizadas': [], 'sustancias_desconocidas': [], 'resumen_llm': 'El asistente de IA no pudo extraer nombres de medicamentos del texto.'})

        print("Clasificando medicamentos en Python...")
        sustancias_analizadas = []
        sustancias_desconocidas = []
        medicamentos_ia_ya_procesados = set()

        for medicamento_ia in lista_medicamentos_ia:
            if medicamento_ia in medicamentos_ia_ya_procesados: continue
            
            encontrado = False
            for _, row in df_sustancias.iterrows():
                if medicamento_ia.lower() in row['nombre_lower']:
                    info_sustancia = { 'nombre': row['Nombre'], 'categoria': row['Categoría'], 'descripcion': row['Declaración de seguridad'] }
                    sustancias_analizadas.append(info_sustancia)
                    encontrado = True
                    for med_ia_sub in lista_medicamentos_ia:
                        if med_ia_sub.lower() in row['nombre_lower']:
                             medicamentos_ia_ya_procesados.add(med_ia_sub)
                    break
            
            if not encontrado:
                sustancias_desconocidas.append(medicamento_ia)
            
            medicamentos_ia_ya_procesados.add(medicamento_ia)

        resumen_llm = generar_resumen_ia(sustancias_analizadas)

        return jsonify({
            'texto_completo': texto_extraido,
            'sustancias_analizadas': sustancias_analizadas,
            'sustancias_desconocidas': sustancias_desconocidas,
            'resumen_llm': resumen_llm
        })

    except Exception:
        print(f"ERROR INESPERADO EN LA RUTA /upload: {traceback.format_exc()}")
        return jsonify({'error': 'Ocurrió un error interno grave en el servidor.'}), 500

# --- 5. Punto de Entrada ---
if __name__ == '__main__':
    app.run(debug=True)