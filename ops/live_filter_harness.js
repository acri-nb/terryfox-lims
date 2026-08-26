/* Execute reellement static/js/live-filter.js contre un serveur vivant.
 *
 * Les tests de core/tests.py verifient le CONTRAT entre les gabarits et le
 * script : les bons attributs, les bons identifiants, presents dans toutes les
 * reponses. Ils ne repondent pas a la seule question qui compte pour
 * l'utilisateur -- est-ce que taper dans le champ retrecit la liste ? Il faut
 * pour cela executer le script, ce que fait ce harnais via jsdom.
 *
 * Appele par core/test_e2e_livefilter.py, qui se met de cote si node ou jsdom
 * manquent. LIMS_JSDOM pointe sur le module.
 *
 *   node ops/live_filter_harness.js <url> <sessionid> <script> <region> <champ> <valeur>
 */
const fs = require('fs');
const { JSDOM } = require(process.env.LIMS_JSDOM);

const [url, sid, scriptPath, region, champ, valeur] = process.argv.slice(2);
const entetes = { Cookie: 'sessionid=' + sid };

function compter(doc, sel) {
  const r = doc.querySelector(sel);
  return r ? r.querySelectorAll('tbody tr').length : -1;
}

(async () => {
  const html = await fetch(url, { headers: entetes }).then(r => r.text());
  const dom = new JSDOM(html, { url, runScripts: 'dangerously', pretendToBeVisual: true });
  const w = dom.window;

  // jsdom n'implemente pas fetch : on le branche sur celui de Node, en
  // reinjectant le cookie de session que le navigateur enverrait tout seul.
  const appels = [];
  w.fetch = (cible, opts = {}) => {
    const abs = new URL(cible, url).href;
    appels.push(abs);
    return fetch(abs, { ...opts, headers: { ...(opts.headers || {}), ...entetes } });
  };

  const avant = compter(w.document, region);
  const bouton = w.document.querySelector('[data-live-submit]');

  w.eval(fs.readFileSync(scriptPath, 'utf8'));

  const boutonMasque = bouton ? bouton.hidden : null;

  // On tape dans le champ comme le ferait un humain.
  const input = w.document.querySelector(champ);
  if (!input) { console.log(JSON.stringify({ erreur: 'champ introuvable: ' + champ })); return; }
  // Un humain place son curseur avant de taper : sans focus prealable,
  // activeElement reste <body> et la question du curseur ne se pose meme pas.
  input.focus();
  if (input.tagName === 'SELECT') {
    input.value = valeur;
    input.dispatchEvent(new w.Event('change', { bubbles: true }));
  } else {
    input.value = valeur;
    input.dispatchEvent(new w.Event('input', { bubbles: true }));
  }

  await new Promise(r => setTimeout(r, 1500));

  const apres = compter(w.document, region);
  console.log(JSON.stringify({
    lignes_avant: avant,
    lignes_apres: apres,
    bouton_masque: boutonMasque,
    requetes: appels,
    adresse: w.location.search,
    focus_conserve: w.document.activeElement === input,
  }));
})().catch(e => console.log(JSON.stringify({ erreur: String(e && e.stack || e) })));
