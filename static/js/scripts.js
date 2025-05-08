$(document).ready(function() {
    const a3 = $('#animacion');
    const a4 = $('#a4');
    const a5 = $('#a5');
    const a8 = $('#a8');
    const a9 = $('#a9');
    const f1 = $('#f1');
    const f2 = $('#f2');
    const f5 = $('#f5');
    
    $('.f11, .f12, .f13, .f14, .f15, .f16, .f17, .f18, .f19, .f110, .f111, .f112').css('transform', function() {
        return 'rotateZ(' + (Math.random() * 360) + 'deg) translateY(91px)';
    });
    
    $('.f21, .f22, .f23, .f24, .f25, .f26, .f27, .f28, .f29, .f210, .f211, .f212, .f213, .f214, .f215, .f216, .f217, .f218, .f219, .f220, .f221, .f222, .f223, .f224, .f225, .f226, .f227, .f228, .f229, .f230, .f231, .f232, .f233').css('transform', function() {
        return 'rotateZ(' + (Math.random() * 360) + 'deg) translateY(95px)';
    });
    
    for (let i = 1; i < 11; i++) {      
        a3.append('<span class=a3'+i+'></span>'); 
        $('.a3'+i+'').css({ 
            '-webkit-animation': 'a3 1s '+(Math.random()*2)+'s infinite', 
            '-moz-animation': 'a3 1s '+(Math.random()*2)+'s infinite',
            'color': '#ff0000'
        }); 
    } 
    
    setInterval(function() { 
        $('#animacion span').each(function() { 
            $(this).text(Math.ceil(Math.random()*999));
        }); 
    }, 100);
    
    for (let i = 1; i < 31; i++) {      
        a4.append('<span class=a3'+i+'></span>'); 
    }
    
    setInterval(function() { 
        $('#a4 span').each(function() { 
            $(this).width((Math.random()*15)); 
        }); 
    }, 500);  
    
    for (let i = 1; i < 16; i++) {      
        a5.append('<span><b class=a5'+i+'></b></span>'); 
        $('.a5'+i+'').css({ 
            '-webkit-animation': 'a3 1s 0.'+i+'s infinite', 
            '-moz-animation': 'a3 1s 0.'+i+'s infinite' 
        });   
    } 
    
    setInterval(function() { 
        var h = Math.ceil(Math.random()*24); 
        var m = Math.ceil(Math.random()*60); 
        if (h<10) {$('.a731').text('0'+h+':');} 
        else {$('.a731').text(h+':');} 
        if (m<10) {$('.a732').text('0'+m);} 
        else {$('.a732').text(m);}  
    }, 100); 
    
    setInterval(function() { 
        var d = Math.ceil(Math.random()*30); 
        var m = Math.ceil(Math.random()*12); 
        var min = 1700, max = 1999; 
        var rand = min - 0.5 + Math.random()*(max-min+1) 
        rand = Math.round(rand); 
        if (d<10) {$('.a741').text('0'+d+'/');} 
        else {$('.a741').text(d+'/');} 
        if (m<10) {$('.a742').text('0'+m+'/');} 
        else {$('.a742').text(m+'/');} 
        $('.a743').text(rand); 
    }, 50); 
    
    for (let i = 1; i < 41; i++) {      
        a8.append('<span></span>'); 
    } 
    
    setInterval(function() { 
        var mino = 10000, maxo = 99999; 
        var rand = mino - 0.5 + Math.random()*(maxo-mino+1); 
        rand = Math.round(rand); 
        var mine = 100000000, maxe = 999999999;  
        var ran = mine - 0.5 + Math.random()*(maxe-mine+1); 
        ran = Math.round(ran);  
        $('#a9 span:odd').text(rand); 
        $('#a9 span:even').text(ran);  
    }, 100); 
    
    for (let i = 1; i < 37; i++) {      
        f2.append('<span class=f2'+i+'></span>'); 
        $('.f2'+i+'').css({ 
            '-webkit-transform': 'rotateZ('+i+'0deg) translateY(95px)' 
        });   
    } 
    
    for (let i = 1; i < 19; i++) {      
        f5.append('<span class=f5'+i+'><b>'+Math.random()*30+'</b></span>'); 
        $('.f5'+i+'').css({ 
            '-webkit-transform': 'rotateZ('+i*2+'0deg) translateY(40px)' 
        });   
    } 
    
    for (let i = 1; i < 13; i++) {      
        f1.append('<span class=f1'+i+'></span>'); 
        $('.f1'+i+'').css({ 
            '-webkit-transform': 'rotateZ('+i*30+'deg) translateY(91px)' 
        });   
    }
});

// Animación de creación de spans
for(let i=0; i<200; i++) {
    let span = document.createElement('span');
    document.querySelector('section').appendChild(span);
}