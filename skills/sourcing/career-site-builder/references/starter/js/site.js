/*
  Progressive enhancement only. Every job, location and answer is already in the
  HTML that build_site.py writes, so a crawler, an AI agent or a phone with
  JavaScript off still sees everything. This file adds search, the menu and the
  preview dialog.
*/

/*
  The preview dialog. Links marked data-upsell open it instead of a page that
  this preview does not include. Edit the copy here; data-topic on the link
  fills {topic}.
*/
var UPSELL = {
  cta: { label: "See the full version", href: "https://www.fountain.com" },
  note: "Built with the Career Site Builder skill. Fountain Cue connects a page like this to your live jobs and your hiring workflow, so it stays current without anyone rebuilding it.",
  page: {
    title: "{topic} gets its own page",
    body: "In the full version, {topic} is a complete page written for your candidates: what the work involves, the schedules, the pay, the path up, and the open jobs in that area, all readable by search engines and AI assistants."
  },
  job: {
    title: "{topic}: the live job page",
    body: "In the full version, every open job has its own page with pay, schedule and requirements, marked up for job search results, and an Apply button that starts the application. Jobs appear and disappear as they open and close in your applicant tracking system."
  },
  location: {
    title: "Jobs in {topic}",
    body: "In the full version, every location has a page listing its open jobs, which is how candidates search: by town, and near me."
  },
  community: {
    title: "Join the talent community",
    body: "In the full version, candidates leave their number and the kind of work they want, and are told when a matching job opens near them."
  },
  status: {
    title: "Check your application",
    body: "In the full version, candidates see where their application stands without calling the store."
  }
};

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
    document.querySelectorAll(".nav-links a").forEach(function (a) {
      a.addEventListener("click", function () {
        document.body.classList.remove("nav-open");
        toggle.setAttribute("aria-expanded", "false");
      });
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

  /* Preview dialog */
  var dialog = document.getElementById("full-version");
  function fill(text, topic) { return text.replace(/\{topic\}/g, topic || "This page"); }
  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest("[data-upsell]") : null;
    if (!link || !dialog) { return; }
    e.preventDefault();
    var copy = UPSELL[link.getAttribute("data-upsell")] || UPSELL.page;
    var topic = link.getAttribute("data-topic") || link.textContent.trim();
    document.getElementById("upsell-title").textContent = fill(copy.title, topic);
    document.getElementById("upsell-body").textContent = fill(copy.body, topic);
    document.getElementById("upsell-note").textContent = UPSELL.note;
    var cta = document.getElementById("upsell-cta");
    cta.textContent = UPSELL.cta.label;
    cta.href = UPSELL.cta.href;
    if (typeof dialog.showModal === "function") { dialog.showModal(); } else { dialog.setAttribute("open", ""); }
  });
  if (dialog) {
    dialog.addEventListener("click", function (e) { if (e.target === dialog) { dialog.close(); } });
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
      if (j.url) {
        a.href = j.url;
      } else {
        a.href = "#full-version";
        a.setAttribute("data-upsell", "job");
        a.setAttribute("data-topic", j.title);
      }
      a.textContent = j.title;
      var meta = document.createElement("p");
      meta.className = "job-meta";
      [j.city + ", " + j.region, j.pay_label, j.schedule].forEach(function (t) {
        if (!t) { return; }
        var span = document.createElement("span"); span.textContent = t; meta.appendChild(span);
      });
      li.appendChild(a); li.appendChild(meta); results.appendChild(li);
    });
    results.removeAttribute("aria-busy");
    status.textContent = hits.length
      ? hits.length + (hits.length === 1 ? " job matches" : " jobs match") + " your search."
      : "No jobs match that search yet. Try a nearby city or a broader role, or join the talent community and hear when one opens.";
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var p = new URLSearchParams();
    ["q", "where", "cat"].forEach(function (k) {
      if (form.elements[k] && form.elements[k].value) { p.set(k, form.elements[k].value); }
    });
    history.replaceState(null, "", "?" + p.toString() + "#search");
    status.textContent = "Searching...";
    results.setAttribute("aria-busy", "true");
    document.getElementById("search").scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
    setTimeout(render, reduce ? 0 : 250);
  });
  if (params.toString()) {
    render();
  } else {
    /* First visit: show the first six, with every job still in the HTML */
    var items = results.querySelectorAll("li");
    if (items.length > 6) {
      items.forEach(function (li, i) { if (i >= 6) { li.hidden = true; } });
      var more = document.createElement("button");
      more.type = "button";
      more.className = "btn btn--ghost";
      more.textContent = "Show all " + items.length + " jobs";
      more.addEventListener("click", function () {
        items.forEach(function (li) { li.hidden = false; });
        more.remove();
      });
      results.insertAdjacentElement("afterend", more);
      form.addEventListener("submit", function () { more.remove(); });
    }
  }
})();
