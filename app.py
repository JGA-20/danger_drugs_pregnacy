# app.py

from flask import Flask, request, jsonify, render_template
import pytesseract
from PIL import Image
import io
import pandas as pd
import traceback # Importamos para un mejor log de errores

# --- CONFIGURACIÓN DE TESSERACT CON TU RUTA ESPECÍFICA ---
pytesseract.pytesseract.tesseract_cmd = r'D:\tesseract\tesseract.exe'

# --- Carga y preparación de datos ---
try:
    df_sustancias = pd.read_csv('sustancias.csv', encoding='latin-1')
    df_sustancias['nombre_lower'] = df_sustancias['Nombre'].str.lower()
    print("El archivo sustancias.csv se cargó correctamente.")
except FileNotFoundError:
    print("ADVERTENCIA: El archivo 'sustancias.csv' no fue encontrado. La búsqueda de sustancias no funcionará.")
    df_sustancias = pd.DataFrame()
except Exception as e:
    print(f"ERROR al leer el archivo CSV: {e}")
    df_sustancias = pd.DataFrame()


# --- Inicialización de Flask ---
app = Flask(__name__)

# --- Rutas de la aplicación ---

@app.route('/')
def home():
    """Sirve la página principal."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Recibe una imagen, extrae el texto, busca sustancias y devuelve un reporte."""
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
            print(f"Texto extraído: '{texto_extraido[:100]}...'") # Muestra los primeros 100 caracteres
            texto_lower = texto_extraido.lower()

            sustancias_encontradas = []
            print("Buscando sustancias en el texto...")
            for index, row in df_sustancias.iterrows():
                if row['nombre_lower'] in texto_lower:
                    print(f"¡Sustancia encontrada!: {row['Nombre']}")
                    info_sustancia = {
                        'nombre': row['Nombre'],
                        'categoria': row['Categoría'],
                        'descripcion': row['Declaración de seguridad']
                    }
                    sustancias_encontradas.append(info_sustancia)
            
            print(f"Se encontraron {len(sustancias_encontradas)} sustancias.")
            return jsonify({
                'texto_completo': texto_extraido,
                'sustancias_encontradas': sustancias_encontradas
            })

        except Exception as e:
            # Imprime el error completo en la consola del servidor para depuración
            print(f"ERROR DURANTE EL PROCESAMIENTO: {traceback.format_exc()}")
            return jsonify({'error': f'Error interno del servidor al procesar la imagen: {str(e)}'}), 500
            
    return jsonify({'error': 'No se pudo procesar el archivo o la base de datos de sustancias no está cargada.'}), 500


if __name__ == '__main__':
    app.run(debug=True)