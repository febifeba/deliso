# dfd_analytic_bulk — documentation technique

Module Odoo 19.0. Éditeur DorFAdoo. Destiné à Deliso (Groupe Delhez),
hébergé en on-premise chez Burniaux.

**Convention :** le code, les commentaires et les chaînes source sont en
anglais ; la documentation et les traductions sont en français.

---

## 1. Ce que le module résout

Deliso reçoit des factures fournisseurs Peppol de 30 à 50 lignes, à imputer
sur un ou deux chantiers. L'imputation n'est jamais prévisible depuis le
fournisseur ni depuis le compte général : le même fournisseur sur le même
compte 604 part sur le chantier 1 aujourd'hui, le chantier 2 demain, ou se
répartit entre les deux. Les *modèles de distribution analytique* d'Odoo ne
répondent donc pas au cas.

Le module ajoute un bouton **« Imputer les lignes »** qui pose en un geste,
sur toutes les lignes de produit d'un document :

- une **distribution analytique**, éventuellement répartie en pourcentages ;
- sur une facture en brouillon, un **compte comptable** et des **taxes**.

Et un second problème, du même encodage : une facture Peppol qui arrive avec
ses cent lignes, à laquelle on lie ensuite un bon de commande par la saisie
automatique, se retrouve avec **cent lignes de plus**. Le module ajoute une
**poubelle au-dessus de la liste des lignes**, qui vide l'onglet d'un clic.

---

## 2. Arborescence

```
addons/dfd_analytic_bulk/
├── __manifest__.py                       dépend de account, purchase,
│                                         sale_management, analytic
├── models/
│   ├── dfd_analytic_bulk_mixin.py        (293 l.) le cœur, sans aucun champ
│   ├── dfd_analytic_bulk_header_mixin.py  (35 l.) ajoute le champ d'en-tête
│   ├── dfd_analytic_bulk_line_mixin.py    (38 l.) la case à cocher des lignes
│   ├── account_move.py                   (104 l.) factures, et la poubelle
│   ├── purchase_order.py                  (21 l.) commandes d'achat
│   ├── sale_order.py                      (16 l.) commandes de vente
│   └── account_analytic_line.py           (37 l.) move_id, pour le pivot
├── wizard/
│   ├── dfd_analytic_bulk_apply.py        (163 l.) l'assistant
│   └── dfd_analytic_bulk_apply_views.xml
├── views/                                 un fichier par modèle
├── security/ir.model.access.csv           accès au modèle transitoire
├── i18n/fr.po                             traductions
└── tests/test_dfd_analytic_bulk.py       (650 l.) 45 tests
```

Le rapport tests / code est volontairement supérieur à 1 : la logique touche
à la comptabilité d'un client, sur une base qu'on ne peut pas rejouer.

---

## 3. Architecture : deux mixins, et pourquoi

```
dfd.analytic.bulk.mixin              AUCUN champ. Le bouton et la logique.
        │
        ├── account.move             hérite de celui-là SEULEMENT
        │
        └── dfd.analytic.bulk.header.mixin
                │                    + analytic.mixin → champ d'en-tête
                ├── purchase.order
                └── sale.order
```

**L'asymétrie est délibérée et verrouillée par deux tests.** Un champ
`analytic_distribution` en en-tête d'`account.move` fait planter le
formulaire :

```
TypeError: Cannot read properties of undefined (reading 'fields')
    at InvoiceExtractFormRenderer.getBoxType
    at InvoiceExtractFormRenderer.onFocusFieldWidget
    at AnalyticDistribution.focus
    at AnalyticDistribution.focusToSelector
    at AnalyticDistribution.patched
```

Le widget se donne le focus en se rendant, et le module Enterprise
`account_invoice_extract` — la numérisation des factures — intercepte ce
focus pour surligner la zone correspondante du document scanné. Il cherche le
champ dans sa table de correspondance et ne l'y trouve pas.

Éprouvé le 25 août 2026 sur une staging Odoo 19 Enterprise. Le même champ en
en-tête d'une commande d'achat ne pose aucun problème : les achats n'ont pas
de numérisation. **Retirer ce champ a également remis en service la saisie
analytique standard ligne par ligne**, qui cassait elle aussi.

Tests de non-régression : `test_invoice_carries_no_header_field` et
`test_orders_carry_the_header_field`.

---

## 4. Points d'extension

Le mixin déclare quatre méthodes. Une seule est obligatoire.

| Méthode | Obligatoire | Rôle |
|---|---|---|
| `_dfd_target_lines()` | **oui** | les lignes que le bouton peut écrire |
| `_dfd_check_writable()` | non | refuser d'écrire sur ce document |
| `_dfd_header_distribution()` | non | la distribution posée en en-tête |
| `_dfd_supports_accounting_fields()` | non | accepter compte et taxes |

### Ajouter un modèle

1. Hériter de `dfd.analytic.bulk.mixin` — ou de
   `dfd.analytic.bulk.header.mixin` si un champ d'en-tête y est sans danger.
2. Redéfinir `_dfd_target_lines()`.
3. Ajouter le modèle à `ALLOWED_MODELS` dans
   `models/dfd_analytic_bulk_mixin.py`. **Sans ça l'assistant refuse** — un
   oubli ferme la porte, il ne l'ouvre pas.
4. Ajouter le bouton dans une vue.

### `display_type` se lit à l'envers selon le modèle

C'est pour cette raison que `_dfd_target_lines()` est redéfini modèle par
modèle plutôt qu'écrit une fois pour toutes.

| Modèle | Une ligne de produit | Une section ou une note |
|---|---|---|
| `account.move.line` | `'product'` | `'line_section'`, `'line_note'` |
| `purchase.order.line` | **rien** | `'line_section'`, `'line_note'` |
| `sale.order.line` | **rien** | `'line_section'`, `'line_note'` |

Filtrer partout sur `not display_type` viderait les factures de toutes leurs
lignes.

---

## 5. Le flux

```
Bouton « Imputer les lignes »
   │
   ├─ _dfd_check_writable()          refuse une période verrouillée
   ├─ _dfd_target_lines()            lignes de produit
   ├─ _dfd_header_distribution()     distribution d'en-tête, si le modèle en a
   │
   ├─ en-tête rempli + aucune ligne imputée + pas de compte/taxes possibles
   │      └─ _dfd_apply(mode='overwrite')      écriture directe, un clic
   │
   └─ sinon
          └─ assistant dfd.analytic.bulk.apply
                 └─ action_apply() → _dfd_apply(distribution, mode,
                                                account, taxes)
```

### La règle « vide = on ne touche pas »

Un champ laissé vide dans l'assistant n'est pas écrit sur les lignes. C'est
ce qui permet de corriger une taxe sans défaire les comptes, ou un compte
sans défaire une ventilation analytique posée à la main
(`test_account_alone_leaves_the_analytic_alone`).

### La portée ne gouverne que l'analytique

*N'affecter que les lignes vides* / *tout écraser* ne s'applique qu'à
`analytic_distribution`. Un compte comptable est obligatoire sur toute ligne :
aucune n'est jamais vide, la notion n'y voudrait rien dire. Renseigné, il
s'applique partout.

---

## 6. Les décisions et leurs raisons

### Compte et taxes : brouillon seulement

`account.move._dfd_supports_accounting_fields()` rend `True` uniquement si
`state == 'draft'`. Deux raisons distinctes :

- **Les taxes** : Odoo refuse de toute façon — *« You cannot modify the taxes
  related to a posted journal item »*.
- **Le compte** : celui-là passerait, mais le changer sur une ligne lettrée
  **délettre la pièce**, donc défait un rapprochement bancaire que personne
  n'a demandé.

Une facture Peppol qui vient d'arriver est de toute façon en brouillon.

### Le garde-fou sur les périodes verrouillées

`account.move._dfd_check_writable()` appelle `_check_fiscal_lock_dates()` sur
les pièces postées. **Ce garde-fou est écrit à la main, et il n'a pas
d'équivalent natif :** `_get_lock_date_protected_fields()` ne liste que
`balance`, `tax_line_id`, `tax_ids`, `tax_tag_ids`, `account_id`,
`journal_id`, `amount_currency`, `currency_id` et `partner_id`.
`analytic_distribution` n'y figure pas.

Conséquence à connaître : **le bouton est plus strict que la multi-édition
native de la vue liste**, qui laisse passer. C'est un choix, pas un oubli, et
il se retire en supprimant cette méthode. Les deux champs comptables, eux,
sont protégés nativement — l'asymétrie vient d'Odoo.

### Le contrôle multi-sociétés

`analytic_distribution` ne porte pas `check_company`. Le module vérifie donc
lui-même qu'aucun compte analytique d'une autre société n'est posé
(`_dfd_check_analytic_company`). `account_id` et `tax_ids` portent
`check_company=True` : Odoo s'en charge, aucun garde-fou de notre part.

### Les clés de distribution

Une clé est un ou plusieurs identifiants de compte analytique **joints par des
virgules**, un par plan. Odoo sait les lire avec
`analytic.mixin._get_analytic_account_ids_from_distributions`, mais cette
méthode vit sur le mixin — qu'`account.move` ne porte plus depuis la
séparation. Le module les relit sur place.

### Ce que le module ne touche pas

- **La génération des `account.analytic.line`.** Elles restent produites 1
  pour 1 depuis les `account.move.line` par `_inverse_analytic_distribution`.
  C'est la piste d'audit qui relie l'analytique à la comptabilité.
- Aucune surcharge de `_post`, du moteur analytique, ni de `create`/`write`
  sur `account.move.line`.
- Aucun champ ajouté aux lignes de facture, de commande ou de vente. Aucun
  `sudo()`, aucun SQL.
- **`account.move` n'acquiert ni colonne, ni index GIN, ni table de
  relation.** Le module se désinstalle sans laisser de trace sur les factures.

### La seule colonne que le module ajoute ailleurs

`account.analytic.line.move_id` — la pièce comptable d'origine, en `related`
stocké sur `move_line_id.move_id`, en lecture seule, avec un index partiel.

Elle existe pour une raison unique : **un tableau croisé ne sait pas regrouper
par facture sans elle.** `read_group`, la méthode qu'un pivot appelle en RPC,
refuse les chemins pointés — elle lit `move_line_id.move_id` comme la syntaxe
d'un champ *propriété* et lève `ValueError: Property name 'move_id' has to be
used on a property field`. Et `account.analytic.line` ne porte aucun champ
stocké désignant la pièce : `move_line_id` est la *ligne* d'écriture, la
regrouper rend une ligne par ligne de facture.

`auto_account_id` ne peut pas remplir ce rôle non plus — il est calculé sans
être stocké, donc inconvertible en SQL. Il reste valable **en domaine**, où le
rapport de production s'en sert déjà : c'est en **regroupement** qu'il ne tient
pas.

Le champ est bâti exactement comme le `journal_id` qu'`account` ajoute au même
modèle. Il ne crée ni ne modifie aucune écriture analytique : il recopie une
valeur existante. À la mise à jour du module, Odoo le calcule sur l'existant.

**Il disparaît à la désinstallation**, colonne et index compris — vérifié en
désinstallant réellement le module sur une copie du banc le 26 août 2026.
`ir.model.fields._drop_column()` exécute un `ALTER TABLE ... DROP COLUMN` pour
tout champ stocké dont le module s'en va.

### La sélection de lignes : un champ, faute de cases natives

Les cases de sélection d'une vue liste **n'existent pas dans une liste
imbriquée d'un formulaire.** `ListRenderer.hasSelectors` les lit dans
`allowSelectors`, dont la valeur par défaut est `False` ; seuls le contrôleur de
liste (`list_controller.js`) et la fenêtre de choix d'enregistrements
(`select_create_dialog.js`) la passent à `True`. Le champ x2many, jamais. Même
mécanique pour `multi_edit`, qui vient de `archInfo` du contrôleur de liste.
Dans une facture ouverte, il n'y a donc **rien à cocher et rien à
multi-éditer** : la modification multiple d'Odoo n'est atteignable que par les
écritures comptables, en plein écran, ce qui n'est pas un chemin d'encodage.

D'où `dfd.analytic.bulk.line.mixin`, un seul champ `dfd_selected`, hérité par
`account.move.line`, `purchase.order.line` et `sale.order.line`.

`_dfd_lines_to_write()` est la seule porte : lignes cochées s'il y en a, toutes
les lignes éligibles sinon. `_dfd_target_lines()` continue de dire ce qui est
*éligible* — une section cochée reste ignorée, l'un ne remplace pas l'autre.

La colonne est `optional="hide"` et porte le groupe du bouton : elle n'apparaît
même pas dans le sélecteur de colonnes de qui ne peut pas s'en servir.

Les cases sont **vidées après écriture**, et `copy=False` les empêche de suivre
une duplication.

### La poubelle : où elle est, et ce qu'elle emporte

`action_dfd_clear_lines()` supprime tout `invoice_line_ids` — lignes de
produit, sections, sous-sections et notes, soit exactement ce que l'onglet
montre. Les lignes de taxe, la contrepartie fournisseur, l'arrondi et
l'escompte ne sont pas touchés à la main : Odoo les recalcule depuis ce qui
reste.

Le bouton est placé **dans l'onglet**, au-dessus de la liste, et non dans
l'en-tête : c'est un geste sur cet onglet, il se lit à côté de ce qu'il vide.

Trois garde-fous, dans cet ordre :

1. il disparaît de l'écran hors brouillon et quand la liste est déjà vide ;
2. une **confirmation** s'ouvre avant l'exécution ;
3. la méthode **refuse** un document non brouillon, indépendamment de
   l'écran — le masquage ne ferme rien.

### Une réserve

Forcer une taxe **court-circuite la position fiscale**. Si le client en
utilise — intracommunautaire, autoliquidation — la taxe imposée n'est pas
remappée. C'est l'intérêt de l'outil autant que son danger.

---

## 7. Sécurité

Le bouton **« Imputer les lignes »** est réservé au groupe
`analytic.group_analytic_accounting`. **Le masquage n'est pas un refus** :
`action_apply()` revérifie le groupe, refuse tout `res_model` absent
d'`ALLOWED_MODELS`, et appelle `check_access('write')` sur le document.

La **poubelle** ne porte pas de groupe : qui peut modifier une facture peut
déjà supprimer ses lignes une à une, le bouton ne fait qu'abréger le geste.
Ce qu'elle revérifie côté serveur, c'est l'**état** — un document non
brouillon est refusé même si l'écran a montré le bouton. La suppression
elle-même passe par `unlink()`, donc par les droits Odoo sur
`account.move.line`.

Sur un banc **Community**, la case « Comptabilité analytique » des paramètres
n'existe pas : le bloc est réservé à `account.group_account_user`,
qu'apporte `account_accountant` — un module Enterprise. Poser le groupe à la
main :

```bash
docker compose exec -T odoo odoo shell -d <base> \
  --db_host=db --db_user=odoo --db_password=odoo \
  --no-http --log-level=error <<'EOF'
u = env.ref('base.user_admin')
u.group_ids |= env.ref('analytic.group_analytic_accounting')
env.cr.commit()
EOF
```

---

## 8. Traductions

**Une entrée de code n'est retenue que si ses commentaires portent
`#. odoo-python`.** La référence `#: code:` ne suffit pas :
`CodeTranslations._load_python_translations` filtre sur ce commentaire et sur
lui seul. Sans lui, l'entrée est écartée **en silence** — pas d'erreur, pas
d'avertissement, juste une chaîne qui reste en anglais pendant que les
libellés de champs, qui passent par la base, sont correctement traduits.

```
#. module: dfd_analytic_bulk
#. odoo-python
#: code:addons/dfd_analytic_bulk/wizard/dfd_analytic_bulk_apply.py:0
msgid "You are not allowed to manage analytic accounting."
msgstr "Vous n'avez pas accès à la comptabilité analytique."
```

**Le libellé d'un champ hérité n'est pas traduit pour autant.**
`analytic_distribution` vient d'`analytic.mixin`, qu'Odoo traduit pour ses
propres modèles — pas pour les nôtres. Il faut une entrée
`field_<modèle>__analytic_distribution` par modèle qui le porte.

**Pourquoi `fr.po` et non `fr_BE.po` :** `get_base_langs('fr_BE')` rend
`['fr', 'fr_BE']`. Odoo charge `fr.po` puis `fr_BE.po` par-dessus. Un `fr.po`
sert donc tous les français — France, Belgique, Suisse, Canada — et rien dans
ce module n'appelle une tournure spécifiquement belge. Un `fr_BE.po` ne se
justifierait que pour surcharger un terme précis.

**Une correction de traduction ne prend effet qu'à la mise à jour du
module**, pas à un redémarrage.

---

## 9. Installer, mettre à jour, tester

```bash
# installation
odoo-bin -d <base> -i dfd_analytic_bulk --stop-after-init

# mise à jour — après TOUTE modification de vue, modèle ou traduction
odoo-bin -d <base> -u dfd_analytic_bulk --stop-after-init

# tests
odoo-bin -d <base> -u dfd_analytic_bulk \
  --test-enable --test-tags /dfd_analytic_bulk \
  --stop-after-init --max-cron-threads=0 \
  --log-level=warn --log-handler=odoo.tests:INFO
```

Verdict attendu :

```
0 failed, 0 error(s) of 45 tests
```

Un Odoo 19 local en deux commandes : voir [`docker/README.md`](../docker/README.md).

---

## 10. Migration vers Odoo 20

À vérifier en priorité, dans cet ordre — ce sont les points sur lesquels ce
module s'appuie et qui ont déjà bougé entre versions :

1. **`account_invoice_extract`** intercepte-t-il toujours le focus ? Si Odoo
   corrige `getBoxType`, le champ d'en-tête redevient possible sur les
   factures et l'asymétrie des mixins peut disparaître. Les deux tests de
   non-régression tomberont : c'est le signal.
2. **`display_type`** garde-t-il ses valeurs et son asymétrie entre modèles ?
3. **`_get_lock_date_protected_fields()`** protège-t-il enfin
   `analytic_distribution` ? Si oui, `_dfd_check_writable()` devient
   redondant et doit être retiré.
4. **`account.account.company_ids`** — passé de `company_id` à un many2many
   en 19.0. Le domaine du champ `account_id` de l'assistant en dépend.
5. **`res.users.group_ids`** — renommé depuis `groups_id` en 19.0. Utilisé
   dans les tests.
6. **`check_access(operation)`** — a remplacé `check_access_rights` et
   `check_access_rule`.
7. **`read_group`** disparaît dès `saas~19.3` au profit de
   `formatted_read_group`, qui ne prend pas les mêmes arguments
   (`aggregates`, pas `fields`). Le module ne s'en sert nulle part ; deux
   tests l'appellent, pour épingler le refus des chemins pointés qui
   justifie `move_id`. À réécrire le jour où Deliso migre — le champ, lui,
   ne bouge pas.
8. **`account.analytic.line`** acquiert-il enfin un champ stocké désignant la
   pièce ? Si Odoo l'ajoute, `move_id` fait doublon et doit partir.

La suite de tests est le filet : elle attrape ces huit points.

---

## 11. Historique des versions

| Version | Ce qui a changé |
|---|---|
| 19.0.1.0.0 | première livraison : champ d'en-tête sur les trois modèles |
| 19.0.1.1.0 | **retrait du champ d'en-tête des factures** — il faisait planter l'écran ; scission des mixins |
| 19.0.1.1.1 | manifeste aligné sur la convention dFd |
| 19.0.1.2.0 | bouton visible même en-tête vide — il était introuvable sur les commandes |
| 19.0.1.2.1 | traductions réparées — le marqueur `#. odoo-python` manquait |
| 19.0.1.3.0 | compte comptable et taxes dans l'assistant, sur facture en brouillon |
| 19.0.1.3.1 | traductions de l'assistant complétées — un terme de vue se compare octet pour octet, balise `<small>` comprise |
| 19.0.1.3.2 | idem pour le titre du formulaire |
| 19.0.1.4.0 | `account.analytic.line.move_id` — la colonne stockée sans laquelle un tableau croisé ne peut pas regrouper par facture |
| 19.0.1.5.0 | la poubelle : vider les lignes d'une facture en un clic |
| 19.0.1.5.1 | l'assistant s'appelle « Appliquer aux lignes » — il ne fait plus que de l'analytique |
| 19.0.1.6.0 | sélection de lignes : deux chantiers sur une même facture, en deux passes |
