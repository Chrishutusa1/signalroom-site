(function () {
  'use strict';
  var form = document.getElementById('sponsor-inquiry');
  if (!form || !window.fetch) return;
  var busy = false;
  form.addEventListener('submit', function (event) {
    if (!form.checkValidity()) return;
    event.preventDefault();
    if (busy) return;
    var data = new FormData(form);
    if (data.get('bot-field')) return;
    busy = true;
    var button = form.querySelector('[type="submit"]');
    var status = document.getElementById('sponsor-inquiry-status');
    button.disabled = true;
    status.textContent = 'Sending your inquiry…';
    fetch('/', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams(data).toString()})
      .then(function (response) {
        if (!response.ok) throw new Error('Submission not accepted');
        if (typeof window.gtag === 'function') window.gtag('event','sponsor_inquiry', {lead_type:'sponsorship',property_brand:'signal_room',method:'accepted_inquiry_form',transport_type:'beacon'});
        form.reset();
        status.textContent = 'Thank you. Your sponsorship inquiry has been received.';
        // Keep disabled after success to prevent accidental duplicate submissions.
      }).catch(function () {
        busy = false; button.disabled = false;
        status.textContent = 'Your inquiry could not be confirmed. Please try again.';
      });
  });
})();
