// Live regions: refresh parts of a page without reloading it.
//
// Markup:
//   <div data-live-url="/matches/<id>/live/" data-live-interval="10"
//        data-live-ws="/ws/matches/<id>/">            (WebSocket optional)
//   ... <div data-live-region="score">...</div> (anywhere on the page)
//
// The endpoint answers JSON: {version, interval, regions: {name: html}}.
// "interval" (seconds) comes from the server, so the page speeds up when
// a match goes live and stops once it is finished (interval 0).
//
// When the WebSocket is available, any message triggers an immediate
// refresh; polling keeps running as a safety net. Without it (e.g. no
// consumer deployed), the page simply keeps polling.
(function () {
  "use strict";

  const MAX_BACKOFF = 60000;
  const WS_POLL_INTERVAL = 60000;
  const WS_MAX_ATTEMPTS = 3;

  document.querySelectorAll("[data-live-url]").forEach(setUp);

  function setUp(root) {
    const url = root.dataset.liveUrl;
    let interval = Number(root.dataset.liveInterval || 0) * 1000;
    let version = null;
    let timer = null;
    let failures = 0;
    let socket = null;
    let socketOpen = false;

    function schedule(ms) {
      clearTimeout(timer);
      if (ms > 0) timer = setTimeout(refresh, ms);
    }

    // Do not replace a region the user is interacting with (focused field,
    // open cancel form): try again on the next tick.
    function isBusy(region) {
      return (
        region.contains(document.activeElement) ||
        region.querySelector(".collapse.show, .collapsing") !== null
      );
    }

    function apply(data) {
      if (data.version === version) return;
      let complete = true;
      Object.entries(data.regions || {}).forEach(function ([name, html]) {
        document
          .querySelectorAll('[data-live-region="' + name + '"]')
          .forEach(function (region) {
            if (isBusy(region)) {
              complete = false;
              return;
            }
            region.innerHTML = html;
          });
      });
      if (complete) version = data.version;
    }

    async function refresh() {
      if (document.hidden) {
        schedule(interval || MAX_BACKOFF);
        return;
      }
      try {
        const response = await fetch(url, {
          headers: { Accept: "application/json" },
          cache: "no-store",
          credentials: "same-origin",
        });
        if (!response.ok) throw new Error("HTTP " + response.status);
        const data = await response.json();
        failures = 0;
        apply(data);
        interval = Number(data.interval || 0) * 1000;
        if (!interval) {
          stop();
          return;
        }
        schedule(socketOpen ? Math.max(interval, WS_POLL_INTERVAL) : interval);
      } catch (error) {
        failures += 1;
        const base = interval || 10000;
        schedule(Math.min(base * 2 ** failures, MAX_BACKOFF));
      }
    }

    function stop() {
      clearTimeout(timer);
      if (socket) socket.close();
      socket = null;
    }

    function connect(attempt) {
      const path = root.dataset.liveWs;
      if (!path || !("WebSocket" in window) || attempt >= WS_MAX_ATTEMPTS) {
        return;
      }
      const scheme = location.protocol === "https:" ? "wss://" : "ws://";
      try {
        socket = new WebSocket(scheme + location.host + path);
      } catch (error) {
        return;
      }
      let opened = false;
      socket.addEventListener("open", function () {
        opened = socketOpen = true;
      });
      socket.addEventListener("message", refresh);
      socket.addEventListener("close", function () {
        socketOpen = false;
        if (!interval) return; // match closed: nothing more to listen to
        const next = opened ? 0 : attempt + 1;
        setTimeout(function () {
          connect(next);
        }, Math.min(1000 * 2 ** (next + 1), MAX_BACKOFF));
      });
    }

    document.addEventListener("visibilitychange", function () {
      if (!document.hidden && interval) refresh();
    });

    if (interval) {
      connect(0);
      schedule(interval);
    }
  }
})();
