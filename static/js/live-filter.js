/* Filtrage en direct.
 *
 * Les filtres etaient des formulaires GET ordinaires : choisir un chef de
 * projet, cliquer sur "Filter", puis cliquer sur "Clear" pour revenir en
 * arriere. Trois gestes pour une question qui n'en vaut qu'un.
 *
 * Le script rejoue la meme requete GET en arriere-plan et remplace les seules
 * regions marquees data-live-region. Le serveur reste seul juge de ce qui est
 * filtre : rien n'est trie ni masque dans le navigateur, ce qui serait faux
 * des que la liste est paginee -- on ne masquerait alors que la page affichee
 * en laissant croire que le reste ne correspond pas.
 *
 * Sans JavaScript, le bouton d'envoi est toujours la et le formulaire
 * fonctionne exactement comme avant.
 */
(function () {
  'use strict';

  // Assez court pour suivre la frappe, assez long pour ne pas lancer une
  // requete par caractere.
  var DELAI_FRAPPE = 250;

  if (!window.fetch || !window.AbortController || !window.URLSearchParams) {
    return;  // Le formulaire nu reste fonctionnel.
  }

  function chacun(liste, action) {
    Array.prototype.forEach.call(liste, action);
  }

  function estTexte(champ) {
    return champ.tagName === 'INPUT' &&
           ['text', 'search', 'number', 'date', ''].indexOf(champ.type) !== -1;
  }

  function regions() {
    return document.querySelectorAll('[data-live-region]');
  }

  /** Le formulaire porte-t-il au moins un filtre ? */
  function filtre(form) {
    var pose = false;
    new FormData(form).forEach(function (valeur) {
      if (valeur !== '') { pose = true; }
    });
    return pose;
  }

  /** L'adresse que le formulaire produirait s'il etait envoye. */
  function adresse(form) {
    var params = new URLSearchParams();
    new FormData(form).forEach(function (valeur, cle) {
      // Un champ vide n'apporte rien et rend l'adresse illisible.
      if (valeur !== '') { params.append(cle, valeur); }
    });
    var requete = params.toString();
    return window.location.pathname + (requete ? '?' + requete : '');
  }

  /**
   * Vide tous les champs.
   *
   * form.reset() ne convient pas : il restaure les valeurs INITIALES du HTML,
   * qui sur une page deja filtree sont precisement celles du filtre. Le bouton
   * n'aurait alors aucun effet.
   */
  function vider(form) {
    chacun(form.querySelectorAll('input, select'), function (champ) {
      if (champ.type === 'checkbox' || champ.type === 'radio') {
        champ.checked = false;
      } else if (champ.tagName === 'SELECT') {
        champ.selectedIndex = 0;
      } else if (champ.type !== 'hidden') {
        champ.value = '';
      }
    });
  }

  function occupe(actif) {
    chacun(regions(), function (region) {
      if (actif) { region.setAttribute('aria-busy', 'true'); }
      else { region.removeAttribute('aria-busy'); }
    });
  }

  function equiper(form) {
    if (!regions().length) { return; }

    var minuteur = null;
    var encours = null;
    var raz = form.querySelector('[data-live-clear]');

    // Le bouton d'envoi n'a plus de role une fois le script actif.
    chacun(form.querySelectorAll('[data-live-submit]'), function (bouton) {
      bouton.hidden = true;
    });

    function etatRaz() {
      if (raz) { raz.hidden = !filtre(form); }
    }

    function appliquer() {
      if (encours) { encours.abort(); }
      encours = new AbortController();

      var cible = adresse(form);
      occupe(true);

      fetch(cible, {
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        signal: encours.signal
      })
        .then(function (reponse) {
          if (!reponse.ok) { throw new Error('HTTP ' + reponse.status); }
          return reponse.text();
        })
        .then(function (html) {
          var recu = new DOMParser().parseFromString(html, 'text/html');
          chacun(regions(), function (ancienne) {
            var neuve = recu.getElementById(ancienne.id);
            if (neuve) { ancienne.replaceWith(neuve); }
          });
          // L'adresse suit le filtre : la page se recharge, se partage et
          // s'ajoute aux signets comme avant.
          window.history.replaceState(null, '', cible);
          etatRaz();
          // Les scripts qui s'accrochent au contenu remplace -- la selection
          // en lot, par exemple -- doivent pouvoir se rebrancher.
          document.dispatchEvent(new CustomEvent('lims:filtre'));
        })
        .catch(function (erreur) {
          if (erreur.name === 'AbortError') { return; }
          // Plutot que de laisser l'ecran fige sur un resultat perime, on rend
          // la main au formulaire ordinaire.
          occupe(false);
          form.submit();
        });
    }

    form.addEventListener('input', function (evenement) {
      if (!estTexte(evenement.target)) { return; }
      etatRaz();
      window.clearTimeout(minuteur);
      minuteur = window.setTimeout(appliquer, DELAI_FRAPPE);
    });

    form.addEventListener('change', function (evenement) {
      if (estTexte(evenement.target)) { return; }  // deja vu par 'input'
      etatRaz();
      window.clearTimeout(minuteur);
      appliquer();
    });

    // Entree, ou le bouton chez qui le script vient de se lancer.
    form.addEventListener('submit', function (evenement) {
      evenement.preventDefault();
      window.clearTimeout(minuteur);
      appliquer();
    });

    if (raz) {
      raz.addEventListener('click', function (evenement) {
        evenement.preventDefault();
        vider(form);
        window.clearTimeout(minuteur);
        appliquer();
      });
    }

    etatRaz();
  }

  chacun(document.querySelectorAll('form[data-live-filter]'), equiper);
})();
