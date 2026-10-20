// Lineup editor: live counters, row highlighting and a single captain.
// The server validates everything again; this only gives instant feedback.
(function () {
  const form = document.getElementById("lineup-form");
  if (!form) return;

  const min = Number(form.dataset.min);
  const max = Number(form.dataset.max);
  const rows = Array.from(form.querySelectorAll("[data-row]"));
  const starterCount = form.querySelector('[data-count="STARTER"]');
  const subCount = form.querySelector('[data-count="SUBSTITUTE"]');
  const captainLabel = form.querySelector("[data-captain]");

  function roleOf(row) {
    const checked = row.querySelector("[data-role-input]:checked");
    return checked ? checked.value : "";
  }

  function refresh() {
    let starters = 0;
    let subs = 0;
    let captain = "—";
    rows.forEach(function (row) {
      const role = roleOf(row);
      row.classList.toggle("is-starter", role === "STARTER");
      row.classList.toggle("is-substitute", role === "SUBSTITUTE");
      if (role === "STARTER") starters += 1;
      if (role === "SUBSTITUTE") subs += 1;

      const captainInput = row.querySelector("[data-captain-input]");
      if (!role && captainInput.checked) captainInput.checked = false;
      if (captainInput.checked) captain = row.dataset.name;
    });
    starterCount.textContent = starters;
    subCount.textContent = subs;
    const ok = starters >= min && starters <= max;
    starterCount.classList.toggle("is-ok", ok);
    starterCount.classList.toggle("is-bad", !ok);
    captainLabel.textContent = captain;
  }

  form.addEventListener("change", function (event) {
    const target = event.target;
    if (target.matches("[data-captain-input]") && target.checked) {
      // Only one captain: unmark the others, and list the captain.
      form.querySelectorAll("[data-captain-input]").forEach(function (other) {
        if (other !== target) other.checked = false;
      });
      const row = target.closest("[data-row]");
      if (!roleOf(row)) {
        const starter = row.querySelector('[data-role-input][value="STARTER"]');
        if (starter) starter.checked = true;
      }
    }
    refresh();
  });

  refresh();
})();
