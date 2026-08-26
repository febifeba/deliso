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

---

## 2. Arborescence

```
addons/dfd_analytic_bulk/
├── __manifest__.py                       dépend de account, purchase,
│                                         sale_management, analytic
├── models/
│   ├── dfd_analytic_bulk_mixin.py        (261 l.) le cœur, sans aucun champ
│   ├── dfd_analytic_bulk_header_mixin.py  (35 l.) ajoute le champ d'en-tête
│   ├── account_move.py                    (53 l.) factures
│   ├── purchase_order.py                  (16 l.) commandes d'achat
│   └── sale_order.py                      (11 l.) commandes de vente
├── wizard/
│   ├── dfd_analytic_bulk_apply.py        (144 l.) l'assistant
│   └── dfd_analytic_bulk_apply_views.xml
├── views/                                 un fichier par modèle
├── security/ir.model.access.csv           accès au modèle transitoire
├── i18n/fr.po                             traductions
└── tests/test_dfd_analytic_bulk.py       (431 l.) 29 tests
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
- Aucun champ calculé stocké ajouté aux lignes. Aucun `sudo()`, aucun SQL.
- **`account.move` n'acquiert ni colonne, ni index GIN, ni table de
  relation.** Le module se désinstalle sans laisser de trace sur les factures.

### Une réserve

Forcer une taxe **court-circuite la position fiscale**. Si le client en
utilise — intracommunautaire, autoliquidation — la taxe imposée n'est pas
remappée. C'est l'intérêt de l'outil autant que son danger.

---

## 7. Sécurité

Le bouton est réservé au groupe `analytic.group_analytic_accounting`. **Le
masquage n'est pas un refus** : `action_apply()` revérifie le groupe, refuse
tout `res_model` absent d'`ALLOWED_MODELS`, et appelle `check_access('write')`
sur le document.

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
0 failed, 0 error(s) of 29 tests
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

La suite de tests est le filet : elle attrape ces six points.

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
