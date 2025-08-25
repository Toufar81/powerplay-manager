;(function () {
  function onReady(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }
  onReady(function () {
    // Najdi první dva nested inline bloky (Domácí/Hosté) a dej jim CSS třídy pro dvousloupcové zobrazení
    var groups = document.querySelectorAll(
      '#grp-content #game_form .inline-group.nested-inline,\
       #content-main #game_form .inline-group.nested-inline,\
       #game_form .inline-group.nested-inline'
    );
    if (groups.length >= 2) {
      groups[0].classList.add('line-col-left');
      groups[1].classList.add('line-col-right');
    }
  });
})();
