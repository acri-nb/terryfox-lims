# TerryFox LIMS, version 2

Synthèse à l'intention du consortium · 25 août 2026

---

## Où nous en sommes

La version 2 tourne en production. Les dix demandes formulées en réunion y sont, y compris
la découpe par spécimen réclamée par Daniel, qui était de loin la plus lourde. La V1 reste
consultable en lecture seule pour comparer ou retrouver des données d'avant la bascule.

Les 1 329 cas, les 1 550 commentaires et les 42 comptes ont traversé dix migrations sans
qu'une ligne se perde. La répartition des tiers vaut toujours 552 A, 682 B et 95 FAIL,
exactement comme au premier jour. Ce n'est pas de la chance : chaque migration compare ces
chiffres avant et après, et s'annule d'elle-même si l'un d'eux bouge sans avoir été
annoncé. Le cas s'est présenté une fois, sur la base réelle, et la restauration automatique
a fait son travail.

---

## Les demandes du consortium

### Identifiants et types de spécimen

L'ACC est désormais attribué par le LIMS. La biobanque ne le saisit plus. Le compteur ne
réutilise jamais un numéro libéré : les 169 numéros libres entre 1 et 1498 le restent,
puisqu'un ACC retiré peut déjà figurer sur une étiquette de congélateur, et le réattribuer
ferait porter le même identifiant à deux patients différents.

Le Biobank ID devient le champ par lequel on recherche, ce qu'il était déjà dans les faits.
Cette demande a entraîné une conséquence qui n'était pas évidente : l'unique champ de
recherche de la page projet interrogeait le nom du cas, devenu une chaîne générée par le
système. Sans modification, taper « N-BBN 440 » n'aurait rien renvoyé, et la demande aurait
été satisfaite sur le papier seulement. Le champ interroge maintenant les deux
identifiants, et une recherche transverse à tous les projets a été ajoutée dans la barre de
navigation.

Quant aux « trois types de spécimen » demandés, ils se sont révélés être exactement la
découpe réclamée par Daniel. Un seul concept nouveau à introduire dans l'interface au lieu
de deux.

### Cas prioritaires

Un indicateur oui/non, posé à la création à la discrétion de la biobanque. Les cas marqués
remontent en tête de chaque liste : un cas urgent que le défilement fait sortir de l'écran
vide la demande de sa substance. Le repérage visuel se fait par un filet ambre et un
fanion, jamais par une ligne entièrement colorée, le rouge signalant l'échec et non
l'urgence.

### Changement de statut en lot

Le besoin exprimé par Mathieu était de supprimer l'aller-retour par fichier CSV. Des cases
à cocher figurent maintenant à côté de chaque cas, avec sélection par plage, et quarante
cas passent d'un statut à l'autre en trois clics.

Deux points de conception méritent d'être signalés. La grille de cartes a dû laisser place
à un tableau : cocher quarante lignes parmi cent vingt-huit rangées de cartes, sans tri ni
sélection par plage, aurait remplacé l'aller-retour CSV par pire. Et l'opération s'annule,
en respectant le travail fait entre-temps : un spécimen modifié après coup n'est pas
rétabli. Une modification de masse sans retour possible aurait été un piège.

### Re-soumission

Quand un séquençage échoue, le bouton de re-soumission ouvre une nouvelle tentative sous le
même ACC et archive la précédente. Rien n'est recopié : les commentaires, les couvertures
et les statuts restent physiquement attachés à la tentative archivée, ce qui exclut toute
perte pendant une copie. Un report sélectif permet de conserver les spécimens encore bons,
utile quand seul l'ARN a échoué et que le normal n'a pas à être reséquencé.

Les tentatives archivées sortent des listes mais restent consultables par leur adresse, en
lecture seule et signalées comme telles. Un ancien lien ou un commentaire doit continuer de
mener quelque part.

L'interface distingue explicitement la re-soumission, qui suppose un nouveau prélèvement,
du top-up, qui relance le séquençage du même spécimen. Sans cette distinction, les deux
gestes se confondent et l'historique se remplit de fausses tentatives.

### Exports

Deux niveaux, par projet et pour l'ensemble du consortium. Le fichier principal donne une
ligne par cas, avec un bloc de colonnes par spécimen. Ce format a été retenu parce qu'un PI
croise ce fichier avec sa feuille clinique au moyen d'une RECHERCHEV sur le Biobank ID :
un fichier à une ligne par spécimen aurait triplé son effectif sans qu'il s'en aperçoive.
La granularité fine existe, dans un fichier séparé.

Deux précautions ont été prises contre des erreurs de lecture difficiles à détecter. Les
tentatives archivées occupent leur propre fichier plutôt qu'une colonne d'état, car une
erreur de filtre gonflerait un effectif publié. Et chaque fichier annexe porte le couple
(ACC, tentative) comme clé de jointure, le document d'accompagnement expliquant pourquoi :
joindre sur le seul ACC après une re-soumission dupliquerait les lignes de la première
tentative sur la seconde.

L'export consortium réunit les données de tous les groupes. Il est réservé aux
administrateurs et journalisé. Les PI conservent l'export de leur projet.

### Prévention des doublons

Deux régimes différents, délibérément. L'ACC est verrouillé par une contrainte de base de
données : il est généré par le système, la garantie ne coûte rien. Le Biobank ID fait
l'objet d'un contrôle souple, qui signale le conflit en nommant le cas concerné et son
projet, puis laisse passer si l'on confirme. Le raisonnement figure au chapitre des
arbitrages.

### Projet « Referred Cases »

Créé, avec un type distinct qui le sépare des projets de recherche. Les cas référés par un
médecin n'appartiennent à aucun projet de la phase 1, et les mélanger fausserait les
effectifs rapportés par les PI.

### Statuts en trois étapes

Les dix statuts demandés sont en place, regroupés par biobanque, séquençage et
bio-informatique. Le regroupement porte l'ordre du travail : une liste déroulante groupée
apprend qu'un contrôle qualité précède la préparation de librairie, ce que dix pastilles de
couleurs différentes n'apprennent à personne.

Une difficulté n'apparaissait pas dans la demande. Les statuts « incomplete » et
« unknown » de la V1, qui concernaient 469 cas, soit 35 % de la base, n'ont aucun
équivalent dans la nouvelle nomenclature. L'examen des données a partiellement tranché :
385 des 428 cas « incomplete » disposent de leurs deux couvertures ADN sans valeur d'ARN,
et leurs commentaires mentionnent des relances de séquençage. Ces cas signifient donc « ARN
encore en attente », ce que le modèle par spécimen exprime naturellement. Ils portent un
statut de transition, invisible à la saisie mais présent dans les filtres, sans quoi
personne ne pourrait retrouver les cas qu'on lui demande de reclasser.

### Spécimens séparés dans un cas

C'est la demande de Daniel, et la plus structurante du chantier : tumeur et normal doivent
être des entités distinctes à l'intérieur d'un cas, la tumeur elle-même se divisant en ADN
et en ARN, chacune suivie indépendamment bien qu'elles partagent un identifiant de cas.

Les trois entités correspondent exactement aux trois colonnes de couverture qui existaient
déjà, ce qui a rendu la migration sans perte et laissé le calcul du tier intact. La
vérification le confirme : aucun écart entre les couvertures des 3 955 spécimens créés et
les colonnes d'origine, et une répartition des tiers identique au chiffre près.

Le statut descend donc au niveau du spécimen, mais l'écran continue de parler en cas. Un
seul menu déroulant fait avancer les trois d'un coup, le réglage par spécimen restant
accessible en dessous. S'en tenir au suivi par spécimen aurait fait passer le geste le plus
fréquent du système de un menu à trois.

Un ajustement a été nécessaire en cours de route. La première version du calcul faisait
apparaître 1 315 cas comme « analyse terminée », contre 855 auparavant, parce qu'elle
ignorait les spécimens en attente de classement. Les cas « incomplete » se déclaraient donc
terminés, ce qu'un PI aurait lu comme un travail achevé. Le statut d'un cas reflète
désormais le spécimen le moins avancé parmi ceux dont l'état est connu, et les spécimens en
attente sont comptés séparément, avec un filtre dédié.

### Refonte visuelle

La refonte est sobre par choix, sans effets, avec une police lisible et des identifiants en
chasse fixe pour qu'ACC-0142 ne se confonde plus avec ACC-0412. Un point mérite d'être
signalé : aucune combinaison de vert, d'ambre et de rouge ne reste distinguable pour une
personne daltonienne, quel que soit le réglage. Le tier affiche donc toujours sa lettre à
côté de sa couleur.

L'affichage sur téléphone a été repris en fin de chantier. Le problème était structurel et
non cosmétique : la feuille de style ne prévoyait rien pour les petits écrans, et certaines
pages réclamaient trois fois la largeur disponible. Un contrôle automatique empêche
désormais le défaut de revenir.

---

## Trois arbitrages qui méritent d'être connus

Certaines demandes se contredisaient, ou se heurtaient à la réalité de la donnée. Voici
comment elles ont été tranchées.

**Le Biobank ID n'est pas verrouillé, et c'est délibéré.** La demande était de bloquer les
doublons. En regardant les données, P08_CRC utilise des numéros nus de 5 à 849 et P09_BC_EV
de 102 à 850 : les deux projets partagent un même espace de numérotation. Qu'il n'y ait
aucune collision aujourd'hui relève du hasard. Le jour où P09 enregistre son patient 300
alors que P08 en a déjà un, une contrainte stricte empêcherait la technicienne de saisir le
véritable identifiant du patient. Le LIMS signale donc le conflit en nommant le cas
concerné et son projet, puis laisse passer si l'on confirme. L'ACC, lui, est verrouillé
pour de bon.

**Un cas n'a pas forcément trois spécimens.** P10_Prostate n'a aucune valeur d'ARN sur ses
32 cas. Lui en fabriquer un troisième l'aurait laissé « en attente de Tumeur (ARN) »
indéfiniment, et 32 cas auraient semblé bloqués pour toujours. Vous avez tranché que le
protocole n'en prévoit pas ; ce projet fonctionne donc à deux spécimens. Les douze autres
en ont trois. À la création, le type se coche.

**La re-soumission reprend le même ACC alors que les doublons sont interdits.** Les deux
demandes s'excluaient telles quelles. La solution retenue fait porter l'unicité sur la
tentative en cours : un seul cas actif par ACC, les tentatives archivées partageant
librement le numéro. Le personnel garde un identifiant unique par patient, et l'historique
des échecs reste attaché là où il s'est produit.

---

## Ce que nous avons trouvé en ouvrant le capot

Une partie du travail n'était dans aucune demande. L'audit préalable a montré que la base
tenait à peu de chose.

Il n'existait aucune sauvegarde. Ni tâche planifiée, ni copie ailleurs que sur le disque de
la machine. Le seul exemplaire hors serveur était celui du dépôt git, dont les deux
dernières mises à jour étaient espacées de neuf mois. Une panne disque ou une fausse
manœuvre aurait coûté jusqu'à neuf mois de saisie.

Supprimer un projet emportait ses cas. Nous l'avons mesuré sur P06 : le projet plus ses
256 cas et leurs commentaires, derrière une simple page de confirmation, sans corbeille et
sans sauvegarde pour revenir. Les suppressions sont désormais réversibles et la
confirmation exige de recopier le nom du projet.

L'import CSV effaçait des données. Une cellule vide dans un fichier partiellement rempli
remplaçait la valeur existante par du vide, et comme le tier se recalcule à chaque
enregistrement, les cas concernés basculaient silencieusement en FAIL. Une cellule vide
signifie maintenant « inchangé ».

Le dépôt public contenait la base et la clé secrète de l'application. Vous avez choisi de
garder le dépôt ouvert, ce qui se défend : les mots de passe sont hachés de façon robuste
et il n'y a pas eu d'incident. Sortir la base de l'arbre git, qui était de toute façon
nécessaire pour la protéger, a réglé la publication des données sans rien changer à
l'ouverture du code.

Enfin, le dépôt ne pouvait pas avoir de tests : une ancienne migration empêchait de créer
une base à partir de zéro. Une fois corrigée, la suite de tests est devenue possible. Elle
compte 91 tests aujourd'hui.

---

## Ce qui reste à faire

**Reclasser 439 cas.** La V1 ne distinguait pas les trois spécimens, et 469 cas y portaient
un statut sans équivalent dans la nouvelle nomenclature. La donnée nous a appris que ces
cas signifiaient le plus souvent « ARN encore en attente », mais l'établir cas par cas
demande le jugement de la biobanque. Ils sont marqués, filtrables, et l'outil de changement
en lot existe précisément pour les traiter par paquets.

**Une décision en suspens.** La clé secrète de l'application figure dans le dépôt public.
La faire tourner n'est pas une réinitialisation de mots de passe : chacun se reconnecte une
fois avec le sien. Sans cela, quelqu'un disposant de cette clé pourrait fabriquer une
session valide sans connaître aucun mot de passe. Le coût est d'une reconnexion pour 42
personnes ; la décision vous revient.

**Une limite technique.** L'archive V1 est accessible depuis le réseau interne. Pour une
adresse publique, il faudra une intervention sur le proxy de CAIR, qui n'est pas administré
depuis cette machine.

---

*Le détail de chaque décision, avec les mesures qui l'appuient, figure dans le rapport
complet (`RAPPORT_V2.md`).*
