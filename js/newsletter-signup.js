/* newsletter-signup.js - inline AI Health Pulse signup for signalroompodcast.com.
 *
 * Any <form data-newsletter-signup> posts the email to the shared signup
 * endpoint (hdsc-ops). The BeeHiiv key never reaches the browser. The endpoint
 * derives attribution (utm_source) from this page's Origin; data-campaign only
 * names the placement (homepage, episode, article, and so on).
 *
 * Failure and no-JS fallback: a plain link to the hosted BeeHiiv page.
 */
(function () {
  "use strict";

  var ENDPOINT = "https://hdsc-ops.netlify.app/.netlify/functions/newsletter-subscribe";
  var FALLBACK =
    "https://aihealthpulse.beehiiv.com/subscribe?utm_source=signalroompodcast.com&utm_medium=site-form-fallback";

  function setStatus(form, text, kind) {
    var el = form.querySelector("[data-newsletter-status]");
    if (!el) return;
    el.textContent = "";
    el.className = "newsletter-signup__status" + (kind ? " newsletter-signup__status--" + kind : "");
    if (kind === "error") {
      el.appendChild(document.createTextNode(text + " "));
      var a = document.createElement("a");
      a.href = FALLBACK;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "Subscribe on the newsletter page instead.";
      el.appendChild(a);
    } else {
      el.textContent = text;
    }
  }

  function bind(form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var emailInput = form.querySelector('input[name="email"]');
      var hp = form.querySelector('input[name="company"]');
      var btn = form.querySelector('button[type="submit"]');
      var email = ((emailInput && emailInput.value) || "").trim();
      if (!email || !emailInput.checkValidity()) {
        setStatus(form, "Please enter a valid email address.", "");
        if (emailInput) emailInput.focus();
        return;
      }
      if (btn) btn.disabled = true;
      setStatus(form, "Subscribing...", "");

      fetch(ENDPOINT, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          email: email,
          campaign: form.getAttribute("data-campaign") || "site-form",
          company: hp ? hp.value : "",
        }),
      })
        .then(function (res) {
          if (!res.ok) throw new Error("status " + res.status);
          form.reset();
          setStatus(form, "You are in. Check your inbox to confirm.", "ok");
          if (typeof window.gtag === "function") {
            window.gtag("event", "newsletter_signup", {
              method: "site_form",
              placement: form.getAttribute("data-campaign") || "site-form",
            });
          }
        })
        .catch(function () {
          setStatus(form, "That did not go through.", "error");
          if (btn) btn.disabled = false;
        });
    });
  }

  var forms = document.querySelectorAll("form[data-newsletter-signup]");
  for (var i = 0; i < forms.length; i++) bind(forms[i]);
})();
