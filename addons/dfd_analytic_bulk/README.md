# dfd_analytic_bulk

Poser une distribution analytique **en en-tête** d'un document, et l'appliquer
d'un geste à toutes ses lignes de produit.

Odoo 19.0. Dépend de `account`, `purchase`, `sale_management`, `analytic`.

## Le besoin

Deliso reçoit des factures fournisseurs Peppol de 30 à 50 lignes, à imputer sur
un ou deux chantiers. L'imputation n'est jamais prévisible depuis le
fournisseur ni depuis le compte général : le même fournisseur sur le même
compte 604 part sur le chantier 1 aujourd'hui, le chantier 2 demain, ou se
répartit entre les deux. Les *modèles de distribution analytique* d'Odoo ne
répondent donc pas au cas.

## Ce que fait le module

**Un bouton « Imputer les lignes »** sur les factures, les commandes d'achat et
les commandes de vente, réservé au groupe `analytic.group_analytic_accounting`.
Il recopie une distribution analytique sur toutes les lignes de produit du
document.

- La distribution accepte une **répartition en pourcentages** sur plusieurs
  comptes — le 60/40 sur deux chantiers — là où la cascade native par projet ne
  pose qu'un seul compte à 100 %.
- Les lignes de section, de sous-section et de note sont ignorées.
- Sur une facture, les lignes de taxe, d'escompte, d'arrondi et la contrepartie
  fournisseur sont ignorées : seules les lignes dont `display_type` vaut
  `product` sont écrites.
- **Dès qu'une ligne porte déjà une imputation**, un écran de confirmation
  s'ouvre et annonce combien. Deux choix : *n'affecter que les lignes vides*
  (défaut) ou *tout écraser*. Une ventilation manuelle ne disparaît jamais sans
  que quelqu'un l'ait demandé.
- Un compte analytique appartenant à une autre société que le document est
  refusé. La base compte six sociétés et rien dans le widget ne l'empêche.

**Un champ `analytic_distribution` en en-tête des commandes** d'achat et de
vente, et d'elles seules. Au moment de commander, on sait pour quel chantier on
achète : le champ le conserve, et si aucune ligne n'est encore imputée, le
bouton écrit directement sans rien demander. Il complète `project_id` sans le
remplacer — laissé vide, le comportement natif reprend la main.

**Sur une facture, il n'y a pas de champ d'en-tête**, et c'est délibéré : voir
« Pourquoi pas de champ sur les factures » plus bas. La distribution s'y saisit
dans l'écran de confirmation, qui s'ouvre donc à chaque fois.

## Ce que le module ne fait pas

- **Il ne touche pas à la génération des `account.analytic.line`.** Elles
  restent produites 1 pour 1 depuis les `account.move.line` par Odoo. C'est la
  piste d'audit qui relie l'analytique à la comptabilité ; les regrouper
  casserait le drill-down, le recalcul et les rapports analytiques standard.
- **Il ne regroupe pas les lignes d'écriture.** Demande initiale du client,
  écartée avec lui : dans Odoo, les lignes de facture *sont* les lignes de
  l'écriture comptable.
- **Il ne touche à aucun rapport.** Voir plus bas.
- Aucune surcharge de `_post`, ni du moteur analytique, ni de
  `create`/`write` sur `account.move.line`. Aucun champ calculé stocké ajouté
  aux lignes. Pas de `sudo()`, pas de SQL. Désinstallable sans laisser de
  trace hors les trois champs d'en-tête.

## Ce qui était déjà natif — à ne pas réécrire

À lire avant de rouvrir ce module dans deux ans.

| Déjà là | Détail |
|---|---|
| `purchase.order.project_id`, `sale.order.project_id` | Renseigné, toute ligne créée **ensuite** reçoit `analytic_distribution = {compte du projet : 100}`. Les lignes existantes ne sont pas recalculées. |
| Multi-édition des écritures | La vue liste `account.move.line` porte `multi_edit="1"` et la colonne `analytic_distribution` y est déclarée avec `'multi_edit': true`. Sélectionner N lignes, éditer une fois, appliquer aux N. Colonne `optional="hide"` : à activer dans le sélecteur de colonnes. |
| Modèles de distribution analytique | `account.analytic.distribution.model`, appliqués par fournisseur, produit, catégorie. Inutilisables ici, l'imputation n'étant pas prévisible. |

**Pourquoi le champ d'en-tête existe malgré `project_id` :** chez Deliso les
chantiers ne sont pas des projets. Il y a **un seul plan analytique**
(« Chantiers ») et **81 comptes analytiques** qui sont les chantiers, contre
seulement 15 `project.project` qui sont des artefacts (« Services sur site »,
« Modele », « TEST2 »…). Faire marcher la cascade native supposerait de créer
81 projets miroir, qui pollueraient l'app Projet sans rien apporter. Le champ
d'en-tête n'est donc pas un confort : c'est le mécanisme principal.

## Le rapport de Jérôme : rien à développer ici

Le tableau de bord « Analytique chantiers » (`spreadsheet.dashboard`) n'est pas
un développement, c'est un Odoo Spreadsheet. Son contenu réel est une **source
de type liste** sur `account.analytic.line`, sans aucun pivot, remplie de
formules `ODOO.LIST(...)` — donc **une ligne par écriture analytique, aucune
consolidation**.

S'il paraît consolidé aujourd'hui, c'est seulement parce que les factures
fournisseurs actuelles ont presque toutes une seule ligne. Le jour où Peppol
en apporte à 50 lignes, la liste en affichera 50 par facture.

**Le correctif est dans le tableau de bord, pas dans le module** : remplacer la
feuille `ODOO.LIST` par un pivot sur `account.analytic.line` (lignes = compte
général + chantier, mesure = montant), en gardant éventuellement la liste
détaillée sur une seconde feuille. Manipulation Odoo Spreadsheet, une
demi-heure.

## Pourquoi pas de champ sur les factures

Un champ `analytic_distribution` en en-tête d'`account.move` **fait planter
l'écran**. Le widget se donne le focus en se rendant
(`AnalyticDistribution.patched` → `focusToSelector` → `focus`), et le module
Enterprise de numérisation des factures `account_invoice_extract` intercepte ce
focus pour surligner la zone correspondante du document scanné. Il cherche le
champ dans sa table de correspondance, ne l'y trouve pas, et lève :

    TypeError: Cannot read properties of undefined (reading 'fields')
        at InvoiceExtractFormRenderer.getBoxType

Éprouvé le 25 août 2026 sur une staging **Odoo 19 Enterprise**. Le même champ en
en-tête d'une commande d'achat ne pose aucun problème — les achats n'ont pas de
numérisation. C'est donc bien l'interaction avec `account_invoice_extract`, pas
le widget lui-même.

D'où l'asymétrie : `purchase.order` et `sale.order` héritent en plus de
`dfd.analytic.bulk.header.mixin`, qui porte le champ ; `account.move` n'hérite
que de `dfd.analytic.bulk.mixin`, qui ne porte aucun champ. Deux tests
verrouillent cette décision — `test_invoice_carries_no_header_field` et
`test_orders_carry_the_header_field`. **Si l'asymétrie vous paraît bizarre dans
deux ans, c'est ce paragraphe qu'il faut relire avant de la corriger.**

Bénéfice secondaire : `account.move` n'acquiert ni colonne, ni index GIN, ni
table de relation. Le module se désinstalle sans laisser la moindre trace sur
les factures.

## Un écart assumé avec la spécification

La spécification demandait de « laisser remonter l'erreur standard d'Odoo » sur
une période verrouillée. **Cette erreur n'existe pas.**
`account.move.line._get_lock_date_protected_fields()` ne protège que `balance`,
`tax_line_id`, `tax_ids`, `tax_tag_ids`, `account_id`, `journal_id`,
`amount_currency`, `currency_id` et `partner_id`. Écrire
`analytic_distribution` sur une pièce postée d'une période close passe donc
sans un mot chez Odoo — et `_inverse_analytic_distribution` régénère les
`account.analytic.line` au passage.

Le module pose donc **son propre garde-fou** : `_dfd_check_writable()` sur
`account.move` appelle `_check_fiscal_lock_dates()` pour les pièces postées.

Conséquence à connaître : **le bouton est plus strict que l'écran d'Odoo.** La
multi-édition native de la vue liste, elle, laisse toujours passer. Si ce
n'est pas ce que veut Deliso, la bascule tient en une méthode —
`_dfd_check_writable` dans `models/account_move.py`.

## Tests

    odoo-bin -d <base> -i dfd_analytic_bulk --test-enable --test-tags /dfd_analytic_bulk

18 tests. Couvrent : absence du champ sur les factures et présence sur les
commandes, lignes vides seulement, écrasement total, répartition en pourcentages,
exclusion des sections et notes, exclusion des lignes de taxe et de la
contrepartie, refus sur période verrouillée, tolérance sur pièce brouillon,
isolation multi-sociétés, compte analytique sans société, commandes d'achat et
de vente, refus d'un modèle non listé par le wizard.

## Un piège, si le module bouge

`display_type` ne se lit pas pareil d'un modèle à l'autre :

- sur `account.move.line`, une ligne de produit vaut `'product'` ;
- sur `purchase.order.line` et `sale.order.line`, une ligne ordinaire ne vaut
  **rien du tout**, et seules les sections et notes portent une valeur.

Filtrer partout sur `not display_type` viderait les factures de toutes leurs
lignes. C'est pour ça que `_dfd_analytic_target_lines()` est redéfini modèle
par modèle plutôt qu'écrit une fois dans le mixin.
