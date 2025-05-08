document.addEventListener('DOMContentLoaded', function() {
    const sectionElement = document.querySelector('section');

    if (sectionElement) {
        const numberOfSpans = 256;
        for (let i = 0; i < numberOfSpans; i++) {
            let span = document.createElement('span');
            sectionElement.appendChild(span);
        }
    } else {
        console.error("Error: El elemento <section> para la animación de fondo no fue encontrado.");
    }
});