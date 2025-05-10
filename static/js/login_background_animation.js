document.addEventListener('DOMContentLoaded', function() {
    const sectionElement = document.querySelector('section');

    if (sectionElement) {

        const container = document.createElement('div');
        container.classList.add('container');
        sectionElement.appendChild(container);

        const hexWidth = 50; // Ancho del hexágono en px (de .hexagon CSS)
        const hexHeight = 55; // Alto del hexágono en px (de .hexagon CSS)
        const rowMarginTop = -16; // Margen superior negativo para solapar filas (de .row CSS)
        const effectiveHexHeight = hexHeight + rowMarginTop; // Altura efectiva que ocupa una fila con solapamiento

        const screenWidth = window.innerWidth;
        const screenHeight = window.innerHeight;

        const hexagonsPerRow = Math.ceil(screenWidth / hexWidth) + 2; 
        const numberOfRows = Math.ceil(screenHeight / effectiveHexHeight) + 2;

        for (let i = 0; i < numberOfRows; i++) {
            const row = document.createElement('div');
            row.classList.add('row');
            for (let j = 0; j < hexagonsPerRow; j++) {
                const hexagon = document.createElement('div');
                hexagon.classList.add('hexagon');
                row.appendChild(hexagon);
            }
            container.appendChild(row);
        }
    } else {
        console.error("Error JS: No se encontró el elemento <section> para crear el fondo de hexágonos.");
    }
});