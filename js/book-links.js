(function () {
  'use strict';
  if (location.hostname !== 'signalroompodcast.com') return;
  document.addEventListener('click', function (event) {
    var link = event.target.closest && event.target.closest('a[data-book-link]');
    if (!link || typeof window.gtag !== 'function') return;
    // A referral click is interest, never a purchase or qualified lead.
    window.gtag('event', 'book_referral_click', {
      book_title: 'Beneath the Signal',
      placement: link.getAttribute('data-book-link'),
      destination: 'chrisjhutchins.com/book/',
      transport_type: 'beacon'
    });
  });
})();
