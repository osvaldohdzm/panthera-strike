// static/js/login_combined_animations.js
$(document).ready(function () {
    // --- HUD Animation ---
    const $hudWrapper = $('#animacion-hud-wrapper');
    if ($hudWrapper.length) {
        const $anim2Container = $('#anim2-container');
        const $anim2_a3_placeholder = $('#anim2-a3-placeholder');
        const $anim2_a4 = $('#anim2-a4');
        const $anim2_a5 = $('#anim2-a5');
        const $anim2_a8 = $('#anim2-a8');
        const $anim2_a9 = $('#anim2-a9');
        const $anim2_f1 = $('#anim2-f1');
        const $anim2_f2 = $('#anim2-f2');
        const $anim2_f5 = $('#anim2-f5');
        const $anim2_b1 = $('#anim2-b1');

        function getRandomDelay(maxSeconds = 1, minSeconds = 0) {
            return (Math.random() * (maxSeconds - minSeconds) + minSeconds).toFixed(2) + 's';
        }

        if ($anim2_a3_placeholder.length) {
            for (let i = 1; i <= 10; i++) {
                $('<span></span>')
                    .addClass('anim2-num-span' + i)
                    .css('animation', `anim2-kf-opacity 1s ${getRandomDelay(2)} infinite`)
                    .appendTo($anim2_a3_placeholder);
            }
            setInterval(() => {
                $anim2_a3_placeholder.find('span').each(function () {
                    $(this).text(Math.ceil(Math.random() * 999));
                });
            }, 150);
        }

        if ($anim2_a4.length) {
            for (let i = 1; i <= 14; i++) {
                $('<span></span>').addClass('anim2-a4-bar' + i).appendTo($anim2_a4);
            }
            setInterval(() => {
                $anim2_a4.find('span').each(function () {
                    $(this).css('width', (Math.random() * 100) + '%');
                });
            }, 500);
        }

        if ($anim2_a5.length) {
            for (let i = 1; i <= 15; i++) {
                $('<span></span>')
                    .append($('<b></b>').addClass('anim2-a5-block' + i)
                    .css('animation', `anim2-kf-a5-b 1s ${getRandomDelay(1)} infinite`))
                    .appendTo($anim2_a5);
            }
        }

        const $clockTarget = $anim2Container.children('#anim2-a7'); // Global clock
        if ($clockTarget.length) {
            const $hoursSpan = $clockTarget.find('.anim2-a731');
            const $minutesSpan = $clockTarget.find('.anim2-a732');
            const $daySpan = $clockTarget.find('.anim2-a741');
            const $monthSpan = $clockTarget.find('.anim2-a742');
            const $yearSpan = $clockTarget.find('.anim2-a743');

            function updateClockTime() {
                const now = new Date();
                $hoursSpan.text((now.getHours() < 10 ? '0' : '') + now.getHours() + ':');
                $minutesSpan.text((now.getMinutes() < 10 ? '0' : '') + now.getMinutes());
            }
            function setClockDate() {
                const now = new Date();
                $daySpan.text((now.getDate() < 10 ? '0' : '') + now.getDate() + '/');
                $monthSpan.text((now.getMonth() < 9 ? '0' : '') + (now.getMonth() + 1) + '/'); // month is 0-indexed
                $yearSpan.text(now.getFullYear());
            }
            setInterval(updateClockTime, 1000);
            updateClockTime();
            setClockDate();
        }

        if ($anim2_a8.length && !$anim2_a8.find('span').length) {
            for (let i = 1; i <= 14; i++) {
                $anim2_a8.append('<span></span>');
            }
        }

        if ($anim2_a9.length) {
            if ($anim2_a9.find('span').length < 2) {
                $anim2_a9.html('<span>000000000</span><span>00000</span>'); // Adjusted order based on typical HUDs
            }
            const $span1 = $anim2_a9.find('span:first-child');
            const $span2 = $anim2_a9.find('span:last-child');
            setInterval(() => {
                $span1.text(String(Math.floor(100000000 + Math.random() * 900000000)));
                $span2.text(String(Math.floor(10000 + Math.random() * 90000)));
            }, 250);
        }

        function populateFigureElement($element, count, rotationStep, translateY, contentGenerator) {
            if ($element && $element.length) {
                for (let i = 1; i <= count; i++) {
                    const $item = $('<span></span>').addClass($element.attr('id') + '-item' + i);
                    $item.css('transform', `rotateZ(${i * rotationStep}deg) translateY(${translateY}px)`);
                    if (contentGenerator) {
                        $item.html(contentGenerator(i));
                    }
                    $element.append($item);
                }
            }
        }
        populateFigureElement($anim2_f1, 12, 30, 75);
        populateFigureElement($anim2_f2, 36, 10, 80);
        populateFigureElement($anim2_f5, 18, 20, 40, () => `<b>${(Math.random() * 30).toFixed(0)}</b>`);

        if ($anim2_b1.length) {
            for (let i = 1; i <= 10; i++) {
                $('<span></span>')
                    .addClass('anim2-b1-bar' + i)
                    .css({
                        'left': (i * 7 - 7) + 'px',
                        'animation': `anim2-kf-b1 ${getRandomDelay(1.5, 0.5)} ease-in-out infinite alternate`
                    })
                    .appendTo($anim2_b1);
            }
        }
    } // end if $hudWrapper.length

    // --- Background Hexagon Animation ---
    const $sectionElementForHex = $('body > section'); // More specific selector if needed

    if ($sectionElementForHex.length) {
        const $container = $('<div></div>').addClass('container').appendTo($sectionElementForHex);
        
        const hexWidth = 50;
        const hexHeight = 55; 
        const rowMarginTop = -16; // From .row CSS
        const effectiveHexHeight = hexHeight + rowMarginTop;

        function createHexGrid() {
            $container.empty(); // Clear previous grid if window resizes
            const screenWidth = $(window).width();
            const screenHeight = $(window).height();
            const hexagonsPerRow = Math.ceil(screenWidth / hexWidth) + 2;
            const numberOfRows = Math.ceil(screenHeight / effectiveHexHeight) + 2;

            for (let i = 0; i < numberOfRows; i++) {
                const $row = $('<div></div>').addClass('row').appendTo($container);
                for (let j = 0; j < hexagonsPerRow; j++) {
                    $('<div></div>').addClass('hexagon').appendTo($row);
                }
            }
        }
        createHexGrid();
        // Optional: Recreate grid on window resize (debounced for performance)
        let resizeTimeout;
        $(window).on('resize', function() {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(createHexGrid, 250);
        });

    } else {
        console.error("Error JS: No se encontr\u00F3 el elemento <section> para crear el fondo de hex\u00E1gonos.");
    }
});