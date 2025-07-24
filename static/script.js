console.log('Script.js cargado y ejecutándose.');

document.addEventListener('DOMContentLoaded', () => {
    console.log('Evento DOMContentLoaded disparado. La página está lista.');

    // Referencias a los elementos del DOM
    const uploader = document.getElementById('uploader');
    const imagePreview = document.getElementById('imagePreview');
    const imagePlaceholder = document.getElementById('image-placeholder');
    const processButton = document.getElementById('processButton');
    const statusDiv = document.getElementById('status');

    const reporteContainer = document.getElementById('reporte-container');
    const sustanciasEncontradasDiv = document.getElementById('sustancias-encontradas');
    const resultDiv = document.getElementById('result');

    // Verificamos si los elementos existen al inicio
    if (!uploader) console.error('Error Crítico: No se encontró el elemento #uploader');
    if (!processButton) console.error('Error Crítico: No se encontró el elemento #processButton');
    if (!reporteContainer) console.error('Error Crítico: No se encontró el elemento #reporte-container');

    let selectedFile = null;

    uploader.addEventListener('change', (event) => {
        console.log('Evento "change" en el uploader detectado.');
        selectedFile = event.target.files[0];
        if (selectedFile) {
            console.log('Archivo seleccionado:', selectedFile.name);
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                imagePreview.style.display = 'block';
                imagePlaceholder.style.display = 'none';
            };
            reader.readAsDataURL(selectedFile);
            reporteContainer.style.display = 'none';
            statusDiv.textContent = '';
        }
    });

    processButton.addEventListener('click', async () => {
        console.log('Botón "Analizar Imagen" presionado.');

        if (!selectedFile) {
            alert('Por favor, selecciona una imagen primero.');
            return;
        }

        statusDiv.textContent = 'Analizando, por favor espera...';
        processButton.disabled = true;
        
        console.log('Iniciando llamada fetch a /upload...');

        try {
            const formData = new FormData();
            formData.append('file', selectedFile);

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });
            
            console.log('Respuesta del fetch recibida. Estado:', response.status);

            const data = await response.json();
            console.log('Datos JSON recibidos del servidor:', data);

            if (!response.ok) {
                console.error('La respuesta del servidor no fue OK.');
                throw new Error(data.error || `Error del servidor: ${response.status}`);
            }
            
            console.log('Llamando a la función mostrarReporte...');
            mostrarReporte(data);

        } catch (error) {
            console.error('ERROR dentro del bloque try/catch:', error);
            statusDiv.textContent = `Error: ${error.message}`;
        } finally {
            console.log('Bloque "finally" ejecutado. Habilitando botón.');
            processButton.disabled = false;
        }
    });

    function mostrarReporte(data) {
        console.log('Dentro de mostrarReporte. Datos:', data);
        statusDiv.textContent = '¡Análisis completado!';
        
        if (reporteContainer && resultDiv && sustanciasEncontradasDiv) {
            console.log('Contenedores del reporte encontrados. Mostrando reporte...');
            reporteContainer.style.display = 'block';
            resultDiv.textContent = data.texto_completo || 'No se pudo extraer texto de la imagen.';

            // Limpiar resultados anteriores antes de añadir nuevos
            sustanciasEncontradasDiv.innerHTML = '';

            if (data.sustancias_encontradas && data.sustancias_encontradas.length > 0) {
                console.log(`Encontradas ${data.sustancias_encontradas.length} sustancias. Creando tarjetas...`);
                data.sustancias_encontradas.forEach(sustancia => {
                    const card = document.createElement('div');
                    card.className = `sustancia-card categoria-${sustancia.categoria.toLowerCase()}`;
                    card.innerHTML = `
                        <h3>${sustancia.nombre}</h3>
                        <p><strong>Categoría de Riesgo: ${sustancia.categoria}</strong></p>
                        <p>${sustancia.descripcion}</p>
                    `;
                    sustanciasEncontradasDiv.appendChild(card);
                });
            } else {
                console.log('No se encontraron sustancias en el reporte.');
                sustanciasEncontradasDiv.innerHTML = '<p>No se encontraron sustancias de nuestra lista en el texto de la imagen.</p>';
            }
        } else {
            console.error('Error fatal: No se encontraron los contenedores del reporte en el HTML al momento de mostrar.');
            statusDiv.textContent = 'Error: Faltan elementos en la página para mostrar el reporte.';
        }
    }
});