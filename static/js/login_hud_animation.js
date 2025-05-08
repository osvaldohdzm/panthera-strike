// Script para Animación HUD (Animación 02)
$(document).ready(function () {
    const anim2_a3_placeholder = $('#anim2-a3-placeholder');
    const anim2_a4 = $('#anim2-a4');
    const anim2_a5 = $('#anim2-a5');
    const anim2_a8 = $('#anim2-a8'); // Contenedor para las líneas horizontales
    const anim2_a9 = $('#anim2-a9'); // Contenedor para números aleatorios par/impar
    const anim2_f1 = $('#anim2-f1');
    const anim2_f2 = $('#anim2-f2');
    const anim2_f5 = $('#anim2-f5');
    const anim2_b1 = $('#anim2-b1'); // Contenedor para las barras b1

    // Generación de números aleatorios para #anim2-a3-placeholder
    if (anim2_a3_placeholder.length) {
        for (let i = 1; i < 11; i++) { // 10 spans de números
            anim2_a3_placeholder.append('<span class="anim2-num-span' + i + '"></span>');
            $('.anim2-num-span' + i).css({
                '-webkit-animation': 'anim2-kf-opacity 1s ' + (Math.random() * 2) + 's infinite',
                '-moz-animation': 'anim2-kf-opacity 1s ' + (Math.random() * 2) + 's infinite',
                // El color ya está definido en el CSS #anim2-a3-placeholder
            });
        }
        setInterval(function () {
            $('#anim2-a3-placeholder span').each(function () {
                $(this).text(Math.ceil(Math.random() * 999));
            });
        }, 100);
    }

    // Animación para #anim2-a4 (barras verticales)
    if (anim2_a4.length) {
        for (let i = 1; i < 15; i++) { // Número de barras
            anim2_a4.append('<span class="anim2-a4-bar' + i + '"></span>');
        }
        setInterval(function () {
            $('#anim2-a4 span').each(function () {
                $(this).width((Math.random() * 100) + '%'); // Ancho aleatorio en %
            });
        }, 500);
    }

    // Animación para #anim2-a5 (bloques en la parte inferior)
    if (anim2_a5.length) {
        for (let i = 1; i < 16; i++) { // Número de spans contenedores de <b>
            anim2_a5.append('<span><b class="anim2-a5-block' + i + '"></b></span>');
            // La animación 'anim2-kf-a5-b' se aplica a '.anim2-a5-blockX b' desde CSS
            // Aquí se aplica al <b> directamente
             $('.anim2-a5-block' + i).css({
                '-webkit-animation': 'anim2-kf-a5-b 1s ' + (Math.random() * 1) + 's infinite',
                '-moz-animation': 'anim2-kf-a5-b 1s ' + (Math.random() * 1) + 's infinite'
            });
        }
    }

    // Actualización de hora en #anim2-a7 (el global, no el de figure)
    const clockTarget = $('#anim2-container > #anim2-a7'); // Seleccionar el #anim2-a7 global
    if (clockTarget.length) {
        setInterval(function () {
            var h = new Date().getHours();
            var m = new Date().getMinutes();
            if (h < 10) { clockTarget.find('.anim2-a731').text('0' + h + ':'); }
            else { clockTarget.find('.anim2-a731').text(h + ':'); }
            if (m < 10) { clockTarget.find('.anim2-a732').text('0' + m); }
            else { clockTarget.find('.anim2-a732').text(m); }
        }, 1000);

        // Fecha actual (estática o actualizada)
        var currentDate = new Date();
        var d = currentDate.getDate();
        var mo = currentDate.getMonth() + 1;
        var y = currentDate.getFullYear();
        if (d < 10) { clockTarget.find('.anim2-a741').text('0' + d + '/'); } else { clockTarget.find('.anim2-a741').text(d + '/'); }
        if (mo < 10) { clockTarget.find('.anim2-a742').text('0' + mo + '/'); } else { clockTarget.find('.anim2-a742').text(mo + '/'); }
        clockTarget.find('.anim2-a743').text(y);
    }


    // Animación para #anim2-a8 (líneas horizontales con barrido)
    if (anim2_a8.length && !anim2_a8.find('span').length) { // Solo agregar si no existen
        for (let i = 1; i < 15; i++) { // Número de líneas horizontales
            anim2_a8.append('<span></span>');
        }
    }

    // Animación para #anim2-a9 (números aleatorios par/impar)
    if (anim2_a9.length) {
        // Asegurarse que los spans existen si el HTML no los provee inicialmente
        if (anim2_a9.find('span').length < 2) {
            anim2_a9.html('<span>00000</span><span>000000000</span>'); // Valores iniciales
        }
        setInterval(function () {
            var mino = 10000, maxo = 99999;
            var rand = mino - 0.5 + Math.random() * (maxo - mino + 1);
            rand = Math.round(rand);
            var mine = 100000000, maxe = 999999999;
            var ran = mine - 0.5 + Math.random() * (maxe - mine + 1);
            ran = Math.round(ran);
            $('#anim2-a9 span:odd').text(rand); // El segundo span
            $('#anim2-a9 span:even').text(ran); // El primer span
        }, 200); // Intervalo más largo para que sea legible
    }

    // Generación de elementos para #anim2-f1 (dentro de #anim2-figure)
    if (anim2_f1.length) {
        for (let i = 1; i < 13; i++) { // 12 items
            anim2_f1.append('<span class="anim2-f1-item' + i + '"></span>');
            $('.anim2-f1-item' + i).css({
                '-webkit-transform': 'rotateZ(' + i * 30 + 'deg) translateY(60px)', // translateY ajustado para figure
                '-moz-transform': 'rotateZ(' + i * 30 + 'deg) translateY(60px)'
            });
        }
    }
    // Generación de elementos para #anim2-f2 (dentro de #anim2-figure)
    if (anim2_f2.length) {
        for (let i = 1; i < 37; i++) { // 36 items
            anim2_f2.append('<span class="anim2-f2-item' + i + '"></span>');
            $('.anim2-f2-item' + i).css({
                '-webkit-transform': 'rotateZ(' + i * 10 + 'deg) translateY(65px)', // translateY ajustado
                '-moz-transform': 'rotateZ(' + i * 10 + 'deg) translateY(65px)'
            });
        }
    }
    // Generación de elementos para #anim2-f5 (dentro de #anim2-figure)
    if (anim2_f5.length) {
        for (let i = 1; i < 19; i++) { // 18 items
            anim2_f5.append('<span class="anim2-f5-item' + i + '"><b>' + (Math.random() * 30).toFixed(0) + '</b></span>');
            $('.anim2-f5-item' + i).css({
                '-webkit-transform': 'rotateZ(' + i * 20 + 'deg) translateY(30px)', // translateY ajustado
                '-moz-transform': 'rotateZ(' + i * 20 + 'deg) translateY(30px)'
            });
        }
    }

    // Generación de barras para #anim2-b1
    if (anim2_b1.length) {
        for (let i = 1; i <= 10; i++) { // 10 barras
            anim2_b1.append('<span class="anim2-b1-bar' + i + '"></span>');
            $('.anim2-b1-bar' + i).css({
                'left': (i * 7 - 7) + 'px', // Espaciado de las barras (5px width + 2px gap)
                '-webkit-animation': 'anim2-kf-b1 ' + (0.5 + Math.random() * 1.5) + 's ease-in-out infinite alternate',
                '-moz-animation': 'anim2-kf-b1 ' + (0.5 + Math.random() * 1.5) + 's ease-in-out infinite alternate'
            });
        }
    }
});