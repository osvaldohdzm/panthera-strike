document.addEventListener('DOMContentLoaded', function() {
    const sectionElement = document.querySelector('section');

    if (sectionElement) {
        const numberOfSpans = 500; // Aumentado para mejor cobertura en diferentes aspect ratios
        for (let i = 0; i < numberOfSpans; i++) {
            let span = document.createElement('span');
            sectionElement.appendChild(span);
        }
    } else {
        // Este mensaje ayudará a saber si el script no encuentra el <section>
        console.error("Error JS: No se encontró el elemento <section> para crear los mosaicos de fondo.");
    }
});