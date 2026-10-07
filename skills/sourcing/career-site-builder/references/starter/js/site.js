/*
  Progressive enhancement only. Every job, location and page is already in the
  HTML that build_site.py writes, so a crawler, an AI agent or a phone with
  JavaScript off still sees everything. This file adds filtering and polish.
*/
(function () {
  "use strict";
  document.documentElement.classList.add("js");

  /* Mobile navigation */
  var toggle = document.querySelector(".nav-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  /* Gentle reveal on scroll, skipped entirely for reduced motion */
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var revealables = document.querySelectorAll(".reveal");
  if (!reduce && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-visible"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -10% 0px" });
    revealables.forEach(function (el) { io.observe(el); });
  } else {
    revealables.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* Job search: filters the list build_site.py already rendered */
  var results = document.getElementById("job-results");
  var form = document.getElementById("job-search");
  if (!results || !form || !window.JOBS) { return; }

  var status = document.getElementById("job-status");
  var params = new URLSearchParams(window.location.search);
  ["q", "where", "cat"].forEach(function (k) {
    var field = form.elements[k];
    if (field && params.get(k)) { field.value = params.get(k); }
  });

  function norm(s) { return (s || "").toString().toLowerCase().trim(); }

  function render() {
    var q = norm(form.elements.q && form.elements.q.value);
    var where = norm(form.elements.where && form.elements.where.value);
    var cat = norm(form.elements.cat && form.elements.cat.value);
    status.textContent = "Searching...";
    var hits = window.JOBS.filter(function (j) {
      var text = norm(j.title + " " + j.category_label + " " + j.summary);
      var place = norm(j.city + " " + j.region + " " + j.postal_code);
      return (!q || text.indexOf(q) !== -1) &&
             (!where || place.indexOf(where) !== -1) &&
             (!cat || norm(j.category) === cat);
    });
    results.innerHTML = "";
    hits.forEach(function (j) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = j.url; a.textContent = j.title;
      var meta = document.createElement("p");
      meta.className = "job-meta";
      [j.city + ", " + j.region, j.pay_label, j.schedule].forEach(function (t) {
        var span = document.createElement("span"); span.textContent = t; meta.appendChild(span);
      });
      li.appendChild(a); li.appendChild(meta); results.appendChild(li);
    });
    status.textContent = hits.length
      ? hits.length + (hits.length === 1 ? " job" : " jobs") + " match your search."
      : "No jobs match that search yet. Try a nearby city, a broader role, or join the talent community below and we will tell you when one opens.";
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var p = new URLSearchParams();
    ["q", "where", "cat"].forEach(function (k) {
      if (form.elements[k] && form.elements[k].value) { p.set(k, form.elements[k].value); }
    });
    history.replaceState(null, "", "?" + p.toString());
    render();
  });
  render();
})();
