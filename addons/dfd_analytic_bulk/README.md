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

Il est **toujours visible**, même quand rien n'est encore saisi. Le masquer tant
que l'en-tête est vide paraissait propre, et rendait la fonction introuvable à
qui ne la connaissait pas déjà : sur une commande, personne ne devine qu'il faut
d'abord remplir un champ pour faire apparaître un bouton. Sans distribution à
recopier, le bouton ouvre simplement l'écran qui la demande.

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

### Deux chantiers sur une même facture : cocher les lignes

Une colonne **Sélectionner** s'ajoute aux lignes des quatre documents. Cochées,
seules ces lignes sont écrites ; rien de coché veut dire toutes les lignes — le
cas ordinaire reste un clic.

La colonne est **facultative et masquée**, et réservée au même groupe que le
bouton : qui en a besoin l'active une fois depuis le sélecteur de colonnes, pour
lui seul, et elle reste. Personne d'autre ne voit apparaître une case à cocher
dans ses factures.

**Pourquoi un champ et pas les cases natives d'Odoo.** Les cases de sélection
d'une vue liste n'existent que dans une liste ouverte en plein écran, jamais
dans une liste imbriquée d'un formulaire : `ListRenderer` les lit dans
`allowSelectors`, qui vaut `False` par défaut et n'est passé à `True` que par le
contrôleur de liste et la fenêtre de choix d'enregistrements — jamais par le
champ x2many. Même chose pour `multi_edit`, qui vient du contrôleur de liste.
Dans une facture, il n'y a donc rien à cocher, et rien à multi-éditer.

**Une facture à deux chantiers se fait en deux passes.** On coche les lignes du
premier et on applique ; puis on applique le second à ce qui reste, en portée
*n'affecter que les lignes vides* — la seconde passe ne demande aucune case.

Les cases sont **vidées une fois honorées** : sans ça, traiter le second
chantier commencerait par décocher vingt-cinq cases, c'est-à-dire par le travail
qu'on cherchait justement à éviter. Elles ne survivent pas non plus à une
duplication de document (`copy=False`) : une copie à moitié cochée imputerait la
mauvaise moitié.

### Sur une facture en brouillon : le compte et les taxes aussi

L'assistant porte deux champs de plus, **facultatifs** : un **compte comptable**
et des **taxes**. Une facture Peppol de matériaux, c'est souvent le même 604 et
la même TVA sur les cinquante lignes.

**Un champ laissé vide n'est pas touché.** C'est ce qui permet de corriger une
taxe sans défaire les comptes, ou un compte sans défaire une ventilation
analytique posée à la main.

La **portée** — lignes vides seulement / tout écraser — ne gouverne que
l'analytique. Un compte comptable est obligatoire sur toute ligne : aucune n'est
jamais vide, « n'affecter que les lignes vides » n'y voudrait rien dire.
Renseigné, il s'applique partout, et l'écran l'annonce.

**Brouillon seulement, et pour deux raisons distinctes.** Odoo refuse de toute
façon de modifier les taxes d'une pièce comptabilisée — *« You cannot modify the
taxes related to a posted journal item »*. Le compte, lui, passerait, mais le
changer sur une ligne lettrée **délettre la pièce** : ça défait un rapprochement
bancaire sans que personne ne l'ait demandé. Une facture qui vient d'arriver est
de toute façon en brouillon.

Contrairement à l'analytique, ces deux champs **sont** protégés par les dates de
verrouillage : `_get_lock_date_protected_fields()` liste `account_id`, `tax_ids`
et `tax_tag_ids`. Le garde-fou écrit à la main plus bas ne concerne qu'elle.

**Une réserve à connaître :** forcer une taxe court-circuite la **position
fiscale**. Si le client en utilise — intracommunautaire, autoliquidation — la
taxe imposée ne sera pas remappée. C'est l'intérêt de l'outil autant que son
danger.

Les commandes d'achat et de vente n'ont **pas** ces deux champs : leurs lignes
n'ont pas de compte comptable, il n'apparaît qu'à la facturation. Le champ
`tax_ids` y existe sous le même nom, donc l'étendre plus tard coûterait peu.

**Un champ `analytic_distribution` en en-tête des commandes** d'achat et de
vente, et d'elles seules. Au moment de commander, on sait pour quel chantier on
achète : le champ le conserve, et si aucune ligne n'est encore imputée, le
bouton écrit directement sans rien demander. Il complète `project_id` sans le
remplacer — laissé vide, le comportement natif reprend la main.

**Sur une facture, il n'y a pas de champ d'en-tête**, et c'est délibéré : voir
« Pourquoi pas de champ sur les factures » plus bas. La distribution s'y saisit
dans l'écran de confirmation, qui s'ouvre donc à chaque fois.

## La poubelle : vider les lignes d'un coup

Une facture Peppol arrive avec ses cent lignes déjà lues dans le XML. Lier
ensuite un bon de commande — par la **saisie automatique** — ne les remplace
pas : il **ajoute** les lignes de la commande en dessous. Le document porte
alors deux fois la même marchandise, et la seule sortie native est la petite
poubelle de fin de ligne, cent fois.

D'où un bouton **au-dessus de la liste des lignes**, dans l'onglet lui-même :
il agit sur cet onglet, il se lit à côté de ce qu'il vide. Il ne va pas dans
l'en-tête.

- Tout ce que l'onglet montre part : lignes de produit, sections,
  sous-sections et notes — le domaine exact d'`invoice_line_ids`.
- Les lignes de taxe, la contrepartie fournisseur, l'arrondi et l'escompte ne
  sont pas touchés à la main : Odoo les recalcule depuis ce qui reste.
- **Brouillon seulement.** L'écran cache le bouton ailleurs, et la méthode le
  refuse une seconde fois.
- Le bouton disparaît quand il n'y a plus rien à supprimer : il ne propose
  jamais de vider le vide.
- Une **confirmation** s'ouvre avant. Cent lignes en un clic, sans retour,
  méritent une question.

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
  `create`/`write` sur `account.move.line`. Aucun champ ajouté aux lignes de
  facture, de commande ou de vente. Pas de `sudo()`, pas de SQL.
- **Il ajoute en revanche une colonne à `account.analytic.line`** : `move_id`,
  la pièce comptable d'origine. Voir « Le rapport de Jérôme » plus bas.
  Elle ne crée ni ne modifie aucune écriture analytique, elle recopie une
  valeur qui existe déjà.

**Désinstallable sans laisser de trace.** Vérifié en désinstallant réellement
le module sur une copie du banc, le 26 août 2026 : `move_id` et les trois
champs d'en-tête disparaissent de PostgreSQL avec leurs index. Odoo appelle
`ir.model.fields._drop_column()` pour tout champ stocké dont le module s'en
va — un `ALTER TABLE ... DROP COLUMN`, sans condition.

## Ce qui était déjà natif — à ne pas réécrire

À lire avant de rouvrir ce module dans deux ans.

| Déjà là | Détail |
|---|---|
| `purchase.order.project_id`, `sale.order.project_id` | Renseigné, toute ligne créée **ensuite** reçoit `analytic_distribution = {compte du projet : 100}`. Les lignes existantes ne sont pas recalculées. |
| Multi-édition des écritures | La vue liste `account.move.line` porte `multi_edit="1"` et la colonne `analytic_distribution` y est déclarée avec `'multi_edit': true`. Sélectionner N lignes, éditer une fois, appliquer aux N. **Uniquement en plein écran** : ni les cases de sélection ni `multi_edit` n'existent dans une liste imbriquée d'un formulaire, donc jamais depuis la facture. |
| Modèles de distribution analytique | `account.analytic.distribution.model`, appliqués par fournisseur, produit, catégorie. Inutilisables ici, l'imputation n'étant pas prévisible. |

**Pourquoi le champ d'en-tête existe malgré `project_id` :** chez Deliso les
chantiers ne sont pas des projets. Il y a **un seul plan analytique**
(« Chantiers ») et **81 comptes analytiques** qui sont les chantiers, contre
seulement 15 `project.project` qui sont des artefacts (« Services sur site »,
« Modele », « TEST2 »…). Faire marcher la cascade native supposerait de créer
81 projets miroir, qui pollueraient l'app Projet sans rien apporter. Le champ
d'en-tête n'est donc pas un confort : c'est le mécanisme principal.

## Le rapport de Jérôme : une colonne, et rien de plus

Le tableau de bord « Analytique chantiers » (`spreadsheet.dashboard`) n'est pas
un développement, c'est un Odoo Spreadsheet. Son contenu réel est une **source
de type liste** sur `account.analytic.line`, sans aucun pivot, remplie de
formules `ODOO.LIST(...)` — donc **une ligne par écriture analytique, aucune
consolidation**.

S'il paraît consolidé aujourd'hui, c'est seulement parce que les factures
fournisseurs actuelles ont presque toutes une seule ligne. Le jour où Peppol
en apporte à 50 lignes, la liste en affichera 50 par facture — et ce module,
qui les impute toutes, en fabrique justement cinquante là où l'en-tête n'en
produisait qu'une.

Le correctif est **un tableau croisé** dans le tableau de bord : lignes =
chantier + pièce, mesure = montant. Manipulation Odoo Spreadsheet, pas de
développement.

**Sauf qu'un tableau croisé ne peut pas regrouper par facture**, et c'est la
seule raison d'être de `move_id`. Trois constats, exécutés sur les deux bases
Deliso le 26 août 2026 :

| Regroupement demandé | Résultat |
|---|---|
| `['account_id', 'move_line_id']` | passe, mais rend **une ligne par ligne de facture** — le défaut qu'on veut supprimer |
| `['move_line_id.move_id']` | `ValueError: Property name 'move_id' has to be used on a property field` |
| `['auto_account_id']` | `ValueError: Cannot convert ... to SQL because it is not stored` |

`read_group`, la méthode qu'un tableau croisé appelle en RPC, **refuse les
chemins pointés** : elle lit `move_line_id.move_id` comme la syntaxe d'un champ
*propriété*. Et `account.analytic.line` ne porte aucun champ stocké désignant
la **pièce** — seulement `move_line_id`, qui est la *ligne* d'écriture.

`ref` ne peut pas servir de repli : c'est la référence **fournisseur**. En
production, 62 valeurs de `ref` sont partagées par plusieurs pièces (« Solde »
sur dix factures, « Acompte » sur treize) et 55 pièces ont un `ref` qui varie
d'une ligne à l'autre. Regrouper dessus fusionnerait dix factures en une ligne.

D'où un `related` stocké, bâti exactement comme le `journal_id` qu'`account`
ajoute deux champs plus haut dans le même fichier :

```python
move_id = fields.Many2one(
    'account.move', related='move_line_id.move_id',
    store=True, readonly=True, index='btree_not_null',
)
```

Il est en **lecture seule** : il ne se saisit pas, il suit `move_line_id`. À la
mise à jour du module, Odoo le calcule sur l'existant — 5 526 écritures en
test, 6 412 en production, instantané.

`auto_account_id` reste parfaitement valable **en domaine**, et le rapport de
production s'en sert déjà. C'est en **regroupement** qu'il ne tient pas : il
n'est pas stocké. Ne pas le remplacer.

Le champ apparaît aussi en colonne facultative, masquée par défaut, dans la
liste des écritures analytiques — de quoi vérifier et regrouper sans ouvrir un
rapport.

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

**Le détour par l'assistant est éprouvé**, le 25 août 2026, sur la même staging
Odoo 19 Enterprise : le bouton s'affiche, l'assistant s'ouvre et applique, sans
la moindre erreur. Le module de numérisation greffe son intercepteur sur le
formulaire de facture, pas sur les boîtes de dialogue — le widget y est donc
hors de portée. Bénéfice constaté au passage : une fois le champ d'en-tête
retiré, **la saisie analytique standard ligne par ligne refonctionne**, alors
qu'elle cassait aussi tant que le champ était là.

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

Éprouvé deux fois, et les deux comptent :

- **Odoo 19.0 Community**, en local — la suite automatique ci-dessous.
- **Odoo 19.0 Enterprise**, sur une staging odoo.sh, le 25 août 2026 — à la
  main, parce que `account_invoice_extract` est un module Enterprise que le
  banc local ne peut pas installer. C'est là et seulement là qu'on pouvait
  découvrir la panne du champ d'en-tête, puis vérifier que l'assistant y
  échappe.

    odoo-bin -d <base> -i dfd_analytic_bulk --test-enable --test-tags /dfd_analytic_bulk

18 tests. Couvrent : absence du champ sur les factures et présence sur les
commandes, lignes vides seulement, écrasement total, répartition en pourcentages,
exclusion des sections et notes, exclusion des lignes de taxe et de la
contrepartie, refus sur période verrouillée, tolérance sur pièce brouillon,
isolation multi-sociétés, compte analytique sans société, commandes d'achat et
de vente, refus d'un modèle non listé par le wizard.

## Deux pièges, si le module bouge

### Les traductions de code exigent `#. odoo-python`

Une entrée de `i18n/fr.po` n'est retenue comme traduction Python que si ses
**commentaires** portent la ligne `#. odoo-python` :

```
#. module: dfd_analytic_bulk
#. odoo-python
#: code:addons/dfd_analytic_bulk/wizard/dfd_analytic_bulk_apply.py:0
msgid "You are not allowed to manage analytic accounting."
msgstr "Vous n'avez pas accès à la comptabilité analytique."
```

La référence `#: code:…` ne suffit pas : `CodeTranslations._load_python_translations`
filtre sur ce commentaire et sur lui seul. Sans lui, l'entrée est écartée **en
silence** — pas d'erreur, pas d'avertissement, juste une chaîne qui reste en
anglais à l'écran alors que les libellés de champs, eux, sont bien traduits.
C'est ce qui est arrivé le 25 août 2026, et ça ne se voit qu'à l'usage.

Les libellés de champs et les noms de modèles n'en ont pas besoin : ils passent
par la base, pas par ce filtre.

Autre chose à ne pas oublier : **le libellé d'un champ hérité n'est pas traduit
pour autant.** `analytic_distribution` vient d'`analytic.mixin`, qu'Odoo traduit
pour ses propres modèles — pas pour les nôtres. Il faut une entrée
`field_<modèle>__analytic_distribution` par modèle qui le porte.

Enfin, une correction de traduction ne prend effet qu'à la **mise à jour du
module**, pas à un simple redémarrage.

### `display_type` se lit à l'envers selon le modèle


`display_type` ne se lit pas pareil d'un modèle à l'autre :

- sur `account.move.line`, une ligne de produit vaut `'product'` ;
- sur `purchase.order.line` et `sale.order.line`, une ligne ordinaire ne vaut
  **rien du tout**, et seules les sections et notes portent une valeur.

Filtrer partout sur `not display_type` viderait les factures de toutes leurs
lignes. C'est pour ça que `_dfd_analytic_target_lines()` est redéfini modèle
par modèle plutôt qu'écrit une fois dans le mixin.
