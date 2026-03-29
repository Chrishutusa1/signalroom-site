// LinkedIn profile links for Signal Room Podcast guests
(function() {
    var linkedInUrls = {
        'Ratnadeep Bhattacharjee': 'https://www.linkedin.com/in/ratnadeepbhattacharjee/',
        'Susie Branagan': 'https://www.linkedin.com/in/susie-branagan/',
        'Gary Cao': 'https://www.linkedin.com/in/garycao/',
        'Aleida Lanza': 'https://www.linkedin.com/in/aleidalanza/',
        'Brian Sutherland': 'https://www.linkedin.com/in/briandsutherland/',
        'Mark Gendreau': 'https://www.linkedin.com/in/markgendreaumd/',
        'Amanda Roser': 'https://www.linkedin.com/in/amandabroser/',
        'MarKeisha Snaith': 'https://www.linkedin.com/in/markeishasnaith/',
        'Natasha Dole': 'https://www.linkedin.com/in/natashadole/',
        'David Finkelshteyn': 'https://www.linkedin.com/in/david-finkelshteyn-03191a130/',
        'Guman Chauhan': 'https://www.linkedin.com/in/guman-chauhan-m-s-cissp-cism-600824103/',
        'Amit Shivpuja': 'https://www.linkedin.com/in/amitshivpuja/',
        'Anitha Mareedu': 'https://www.linkedin.com/in/anithamareedu/',
        'Asha Mahesh': 'https://www.linkedin.com/in/ashamahesh/',
        'Barry Chaiken': 'https://www.linkedin.com/in/barrychaiken/',
        'Carol Velandia': 'https://www.linkedin.com/in/carolvelandia/',
        'Keshavan Seshadri': 'https://www.linkedin.com/in/keshavanseshadri/',
        'Larry Kuhn': 'https://www.linkedin.com/in/larrykuhn/',
        'Parth Gargish': 'https://www.linkedin.com/in/parthgargish/',
        'Ritu Chakrawarty': 'https://www.linkedin.com/in/rituchakrawarty/'
    };

    var linkedInSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>';

    // Handle guest cards on guests.html
    document.querySelectorAll('.guest-card').forEach(function(card) {
        var nameEl = card.querySelector('.guest-card-name');
        if (!nameEl) return;
        var name = nameEl.textContent.trim();
        var url = linkedInUrls[name];
        if (!url) return;

        var wrapper = document.createElement('div');
        wrapper.className = 'guest-card-wrapper';
        card.parentNode.insertBefore(wrapper, card);
        wrapper.appendChild(card);

        var link = document.createElement('a');
        link.href = url;
        link.className = 'guest-linkedin';
        link.target = '_blank';
        link.rel = 'noopener';
        link.title = 'View ' + name + ' on LinkedIn';
        link.innerHTML = linkedInSvg;
        link.addEventListener('click', function(e) { e.stopPropagation(); });
        wrapper.appendChild(link);
    });

    // Handle sidebar guest on episode pages
    document.querySelectorAll('.sidebar-guest').forEach(function(sidebar) {
        var nameEl = sidebar.querySelector('h3');
        if (!nameEl) return;
        var name = nameEl.textContent.trim();
        var url = linkedInUrls[name];
        if (!url) return;

        var link = document.createElement('a');
        link.href = url;
        link.className = 'sidebar-guest-linkedin';
        link.target = '_blank';
        link.rel = 'noopener';
        link.title = 'View ' + name + ' on LinkedIn';
        link.innerHTML = linkedInSvg + ' LinkedIn Profile';
        sidebar.appendChild(link);
    });
})();
