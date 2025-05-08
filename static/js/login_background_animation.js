document.addEventListener('DOMContentLoaded', function() {
    const sectionElement = document.querySelector('section');

    if (sectionElement) {
        const numberOfSpans = 256; // Puedes ajustar este número para más o menos mosaicos
                                   // 256 (16x16) es un buen valor de inicio.
        for (let i = 0; i < numberOfSpans; i++) {
            let span = document.createElement('span');
            sectionElement.appendChild(span);
        }
    } else {
        // Este mensaje ayudará a saber si el script no encuentra el <section>
        console.error("Error JS: No se encontró el elemento <section> para crear los mosaicos de fondo.");
    }
});