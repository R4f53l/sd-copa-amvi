// Match sheet: narrow each player list to the selected team.
// Players of the event's team are offered for most roles; "opponent"
// roles (e.g. the goalkeeper facing a penalty) list the other team.
(function () {
  const form = document.getElementById("event-form");
  if (!form) return;

  const teamInputs = form.querySelectorAll('input[name="team"]');
  const playerSelects = form.querySelectorAll("select[data-opponent]");
  if (!teamInputs.length || !playerSelects.length) return;

  function selectedTeam() {
    const checked = form.querySelector('input[name="team"]:checked');
    return checked ? checked.value : null;
  }

  function filterPlayers() {
    const team = selectedTeam();
    playerSelects.forEach(function (select) {
      const opponent = select.dataset.opponent === "1";
      Array.from(select.options).forEach(function (option) {
        const optionTeam = option.dataset.team;
        if (!optionTeam || !team) {
          option.hidden = false;
          return;
        }
        const sameTeam = optionTeam === team;
        option.hidden = opponent ? sameTeam : !sameTeam;
      });
      const current = select.options[select.selectedIndex];
      if (current && current.hidden) select.value = "";
    });
  }

  teamInputs.forEach(function (input) {
    input.addEventListener("change", filterPlayers);
  });
  filterPlayers();
})();
