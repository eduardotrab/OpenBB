/* FinScope motion: numbers count up once when they first appear.
   Dash renders components after load, so a MutationObserver finds them.
   Skipped entirely when the user prefers reduced motion. Local file, no CDN. */
(function () {
  "use strict";
  var DURACAO = 600;
  var reduzir = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function formatar(valor, casas) {
    return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
  }

  function animar(el) {
    if (el.dataset.animado) { return; }
    el.dataset.animado = "1";
    var alvo = parseFloat(el.dataset.valor);
    var casas = parseInt(el.dataset.casas || "0", 10);
    if (reduzir || !isFinite(alvo)) { return; }
    var inicio = null;
    var final = formatar(alvo, casas);
    var terminou = false;
    function passo(agora) {
      if (terminou) { return; }
      if (inicio === null) { inicio = agora; }
      var t = Math.min((agora - inicio) / DURACAO, 1);
      var suave = 1 - Math.pow(1 - t, 3); // ease-out cubic
      el.textContent = formatar(alvo * suave, casas);
      if (t < 1) { window.requestAnimationFrame(passo); } else { terminou = true; }
    }
    window.requestAnimationFrame(passo);
    // Frames pause in background tabs: the final value must land anyway.
    window.setTimeout(function () { terminou = true; el.textContent = final; }, DURACAO + 50);
  }

  function varrer(raiz) {
    if (raiz.querySelectorAll) {
      raiz.querySelectorAll(".fs-numero[data-valor]").forEach(animar);
    }
  }

  new MutationObserver(function (mudancas) {
    mudancas.forEach(function (m) { m.addedNodes.forEach(varrer); });
  }).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", function () { varrer(document); });
})();
