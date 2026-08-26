# TerryFox LIMS — version 2

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

## Ce qui a changé pour les utilisateurs

La biobanque ne saisit plus d'identifiant. Le LIMS attribue l'ACC, et la recherche porte
désormais sur le Biobank ID, celui que les gens ont réellement en main. Une barre de
recherche transverse a été ajoutée : jusqu'ici, retrouver un cas dont on ignorait le projet
obligeait à les ouvrir un par un.

Un cas contient maintenant trois entités suivies séparément : le normal, l'ADN tumoral et
l'ARN tumoral. Chacune a son statut et sa couverture. L'écran continue pourtant de parler
en cas, avec un seul menu déroulant pour faire avancer les trois d'un coup, parce que
c'est le geste le plus fréquent du système et qu'il aurait été absurde de le tripler.

Les changements de statut en masse se font par cases à cocher, comme Mathieu le demandait.
Quarante cas passent d'un statut à l'autre en trois clics, l'opération est journalisée
ligne par ligne, et elle s'annule. L'annulation respecte le travail fait entre-temps : un
spécimen modifié après coup n'est pas rétabli.

La re-soumission ouvre une nouvelle tentative sous le même ACC et archive la précédente
avec ses commentaires et ses couvertures. Rien n'est recopié, donc rien ne peut se perdre
dans la copie.

Les exports existent à deux niveaux, par projet et pour l'ensemble du consortium. Le
fichier principal donne une ligne par cas, format qui se croise directement avec une
feuille clinique par RECHERCHEV sur le Biobank ID.

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
pour de bon : il est généré par le système, la contrainte ne coûte rien.

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

## L'interface

L'ancienne mise en forme datait de 2013 et se voyait : une ombre et un effet de survol sur
chaque carte, y compris celles qui ne sont pas cliquables. Le contraste des pastilles se
situait entre 2,1 et 3,8 pour 1, sous le seuil d'accessibilité de 4,5. Plus gênant, les
couleurs mentaient : le tier A s'affichait en rouge et l'échec en gris, si bien qu'un PI
survolant son projet voyait un mur de rouge et lisait une catastrophe.

La refonte corrige tout cela. Elle est sobre par choix, sans effets, avec une police
lisible et des identifiants en chasse fixe pour qu'ACC-0142 ne se confonde plus avec
ACC-0412. Un point mérite d'être signalé : aucune combinaison de vert, d'ambre et de rouge
ne reste distinguable pour une personne daltonienne, quel que soit le réglage. Le tier
affiche donc toujours sa lettre à côté de sa couleur.

L'affichage sur téléphone a été repris en fin de chantier. Le problème était structurel et
non cosmétique : la feuille de style ne prévoyait tout simplement rien pour les petits
écrans, et certaines pages réclamaient trois fois la largeur disponible. Un contrôle
automatique empêche désormais le défaut de revenir.

## Ce qui reste à faire

**Reclasser 439 cas.** La V1 ne distinguait pas les trois spécimens, et 469 cas y portaient
un statut sans équivalent dans la nouvelle nomenclature. La donnée nous a appris que ces
cas signifiaient le plus souvent « ARN encore en attente », mais l'établir cas par cas
demande le jugement de la biobanque. Ils sont marqués, filtrables, et l'outil de
changement en lot existe précisément pour les traiter par paquets.

**Une décision en suspens.** La clé secrète de l'application figure dans le dépôt public.
La faire tourner n'est pas une réinitialisation de mots de passe : chacun se reconnecte une
fois avec le sien. Sans cela, quelqu'un disposant de cette clé pourrait fabriquer une
session valide sans connaître aucun mot de passe. Le coût est d'une reconnexion pour 42
personnes ; la décision vous revient.

**Une limite technique.** L'archive V1 est accessible depuis le réseau interne. Pour une
adresse publique, il faudra une intervention sur le proxy de CAIR, qui n'est pas
administré depuis cette machine.

---

*Le détail de chaque décision, avec les mesures qui l'appuient, figure dans le rapport
complet (`RAPPORT_V2.md`).*
