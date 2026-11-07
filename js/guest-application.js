(function () {
  'use strict';
  var form = document.getElementById('guest-apply-form');
  if (!form || !window.fetch) return; // Native Netlify POST remains the fallback.
  var busy = false;
  form.addEventListener('submit', function (event) {
    if (!form.checkValidity()) return;
    event.preventDefault();
    if (busy) return;
    var data = new FormData(form);
    if (data.get('bot-field')) return;
    busy = true;
    var button = form.querySelector('[type="submit"]');
    var status = document.getElementById('guest-apply-status');
    button.disabled = true;
    status.textContent = 'Sending your application…';
    fetch('/', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: new URLSearchParams(data).toString()
    }).then(function (response) {
      if (!response.ok) throw new Error('Submission not accepted');
      // Measures Netlify acceptance, not editorial approval or a database write.
      // No personal fields or URL query values are sent to Analytics.
      if (typeof window.gtag === 'function') {
        window.gtag('event', 'guest_application_submit', {
          form_name: 'guest-application',
          method: 'netlify_accepted',
          transport_type: 'beacon'
        });
      }
      form.style.display = 'none';
      var success = document.getElementById('apply-success');
      success.style.display = 'block';
      success.scrollIntoView({block: 'center'});
    }).catch(function () {
      busy = false;
      button.disabled = false;
      status.textContent = 'Your application could not be confirmed. Please try again.';
    });
  });
})();
