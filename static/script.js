// static/script.js

document.addEventListener('DOMContentLoaded', () => {
    const uploader = document.getElementById('uploader');
    const imagePreview = document.getElementById('imagePreview');
    const imagePlaceholder = document.getElementById('image-placeholder');
    const processButton = document.getElementById('processButton');
    const statusDiv = document.getElementById('status');

    let selectedFile = null;

    uploader.addEventListener('change', (event) => {
        selectedFile = event.target.files[0];
        if (selectedFile) {
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                imagePreview.style.display = 'block';
                imagePlaceholder.style.display = 'none';
            };
            reader.readAsDataURL(selectedFile);
            
            const reporteContainer = document.getElementById('reporte-container');
            if (reporteContainer) {
                reporteContainer.style.display = 'none';
            }
            statusDiv.textContent = '';
        }
    });

    processButton.addEventListener('click', async () => {
        if (!selectedFile) {
            alert('Por favor, selecciona una imagen primero.');
            return;
        }

        statusDiv.textContent = 'Analizando, por favor espera... Esto puede tardar unos segundos.';
        processButton.disabled = true;
        
        try {
            const formData = new FormData();
            formData.append('file', selectedFile);

            const response = await fetch('/upload', { method: 'POST', body: formData });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `Error del servidor: ${response.status}`);
            }
            
            mostrarReporte(data);

        } catch (error) {
            statusDiv.textContent = `Error: ${error.message}`;
            console.error('Error en la llamada fetch:', error);
        } finally {
            processButton.disabled = false;
        }
    });

    function mostrarReporte(data) {
        statusDiv.textContent = '¡Análisis completado!';
        
        const reporteCont = document.getElementById('reporte-container');
        const resultDiv = document.getElementById('result');
        const sustanciasEncontradasDiv = document.getElementById('sustancias-encontradas');
        const resumenLlmDiv = document.getElementById('resumen-llm');
        const seccionDesconocidas = document.getElementById('seccion-desconocidas');
        const sustanciasDesconocidasDiv = document.getElementById('sustancias-desconocidas');

        if (reporteCont && resultDiv && sustanciasEncontradasDiv && resumenLlmDiv && seccionDesconocidas && sustanciasDesconocidasDiv) {
            
            reporteCont.style.display = 'block';
            resultDiv.textContent = data.texto_completo || 'No se pudo extraer texto de la imagen.';
            sustanciasEncontradasDiv.innerHTML = '';
            resumenLlmDiv.innerHTML = '';
            sustanciasDesconocidasDiv.innerHTML = '';

            if (data.resumen_llm) {
                let htmlResumen = data.resumen_llm.replace(/\n/g, '<br>');
                htmlResumen = htmlResumen.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                resumenLlmDiv.innerHTML = `<p>${htmlResumen}</p>`;
            } else {
                resumenLlmDiv.innerHTML = '<p>No se pudo generar un resumen.</p>';
            }

            if (data.sustancias_analizadas && data.sustancias_analizadas.length > 0) {
                data.sustancias_analizadas.forEach(sustancia => {
                    const card = document.createElement('div');
                    card.className = `sustancia-card categoria-${sustancia.categoria.toLowerCase()}`;
                    card.innerHTML = `<h3>${sustancia.nombre}</h3><p><strong>Categoría de Riesgo: ${sustancia.categoria}</strong></p><p>${sustancia.descripcion}</p>`;
                    sustanciasEncontradasDiv.appendChild(card);
                });
            } else {
                sustanciasEncontradasDiv.innerHTML = '<p>No se encontraron en nuestra base de datos sustancias de riesgo conocido a partir del texto de la imagen.</p>';
            }

            if (data.sustancias_desconocidas && data.sustancias_desconocidas.length > 0) {
                seccionDesconocidas.style.display = 'block';
                data.sustancias_desconocidas.forEach(nombre => {
                    const tag = document.createElement('div');
                    tag.className = 'sustancia-desconocida';
                    tag.textContent = nombre;
                    sustanciasDesconocidasDiv.appendChild(tag);
                });
            } else {
                seccionDesconocidas.style.display = 'none';
            }

        } else {
            console.error('No se pudo mostrar el reporte. Faltan elementos en el DOM.');
            statusDiv.textContent = 'Error: Faltan elementos en la página para mostrar el reporte. Revisa la consola (F12).';
        }
    }
});