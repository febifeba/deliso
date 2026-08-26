# Tableau de bord « Analytique chantiers »

Corriger le rapport de Jérôme Krannen. **Aucun développement** : c'est un
Odoo Spreadsheet, tout se fait dans l'interface.

---

## Le constat

Le tableau n'est pas un développement. C'est un `spreadsheet.dashboard`, et
son contenu réel est une **source de type liste** sur
`account.analytic.line`, remplie de formules `ODOO.LIST`. Il n'y a **aucun
tableau croisé** dedans, donc aucune consolidation : chaque ligne affichée
est une écriture analytique.

S'il paraît agrégé, c'est uniquement parce que les factures fournisseurs
actuelles — issues de la reprise, 16 134 pièces — ont presque toutes une
seule ligne. Une facture, une écriture, une ligne à l'écran.

Le jour où Peppol apporte des factures de 30 à 50 lignes, le tableau en
affichera 30 à 50 par facture. **Le problème est dans le tableau de bord, pas
dans les factures** : aucune façon de les imputer ne le corrigera.

---

## Deux pièges vérifiés dans le source d'Odoo 19

### La colonne du chantier n'a pas le même nom d'une base à l'autre

`account.analytic.plan._strict_column_name()` :

```python
return 'account_id' if self == project_plan else f"x_plan{self.id}_id"
```

**Le premier plan analytique occupe la colonne standard `account_id`. Tous
les autres reçoivent `x_plan<id>_id`.**

Deliso n'ayant qu'un seul plan, « Chantiers » vit dans `account_id`. C'est ce
qui explique pourquoi l'ancienne version enregistrée du tableau de bord
référence un `x_plan2_id` introuvable dans la base de test.

> **Conséquence directe :** un tableau croisé construit sur la base de test
> peut casser en production si les deux n'ont pas le même nombre de plans.
> Vérifier la colonne réelle des deux côtés avant de livrer.

### `auto_account_id` ne peut pas servir de regroupement

Le champ qui paraît naturel ne convient pas :

```python
auto_account_id = fields.Many2one(
    comodel_name='account.analytic.account',
    string='Analytic Account',
    compute='_compute_auto_account',   # @api.depends_context('analytic_plan_id')
    inverse='_inverse_auto_account',
    search='_search_auto_account',
)
```

Il est **calculé et dépendant du contexte** — il rend le compte du plan qu'on
lui désigne — et n'est **stocké nulle part**. Un tableau croisé a besoin
d'une colonne réelle en base pour regrouper.

Il reste parfaitement valable dans le **domaine**, où Odoo sait le traduire.
C'est en **regroupement** qu'il ne tient pas.

---

## Les champs utiles d'`account.analytic.line`

| Champ | Contenu | Module |
|---|---|---|
| `account_id` | le chantier, **si « Chantiers » est le premier plan** | `analytic` |
| `general_account_id` | le compte général — 604, 611… | `account` |
| `move_line_id` | l'écriture comptable d'origine | `account` |
| `amount` | le montant | `analytic` |
| `date`, `partner_id` | date et fournisseur | `analytic` |

---

## Le correctif

Remplacer la feuille de liste par un **tableau croisé dynamique** sur
`account.analytic.line`, qui additionne au lieu d'énumérer. Le détail reste
sur une seconde feuille, pour descendre à la ligne quand un total surprend.

**Travailler sur une copie.** Un Spreadsheet n'a pas d'historique de versions
sur lequel revenir.

### 1. Le même domaine que la liste existante

Sinon les totaux ne correspondront pas :

```
auto_account_id.plan_id != false
AND move_line_id.journal_id.type = 'purchase'
```

Seules les écritures rattachées à un plan analytique, et seulement celles du
journal d'achat.

### 2. Les lignes et la mesure

| Rôle | Champ |
|---|---|
| Ligne, niveau 1 | `account_id` — le chantier *(à vérifier, voir le piège)* |
| Ligne, niveau 2 | le numéro de facture, via `move_line_id` |
| Mesure | `amount` |

**Regrouper par chantier ET par facture, jamais par facture seule.** Une
facture répartie 60/40 sur deux chantiers doit rendre **deux** lignes. Une
seule ligne par facture additionnerait les deux chantiers et ferait perdre au
rapport l'information pour laquelle il existe.

| Cas | Lignes affichées |
|---|---|
| Facture de 50 lignes, un seul chantier | 1 |
| Facture de 50 lignes, réparties sur deux chantiers | 2 |

### 3. Le compte général : une question à trancher

Ajouté comme niveau de regroupement, une facture qui touche trois comptes
différents redonne trois lignes. Strictement une ligne par facture et par
chantier impose de l'abandonner — ou de le renvoyer sur la feuille de détail.

*Jérôme veut-il compter par chantier, ou savoir ce qu'il a acheté ?*

### 4. Rebrancher les deux filtres globaux

Le tableau porte un filtre **Date** et un filtre **Chantier**. Un filtre
global **ne s'applique pas tout seul** à une nouvelle source : il faut le
rattacher explicitement au tableau croisé.

L'oubli ne fait aucun bruit — le tableau ignore les filtres en silence, et
Jérôme lit des totaux faux sans savoir pourquoi.

### 5. Garder le détail

Ne pas supprimer la feuille de liste. La renommer **Détail** et la laisser
derrière le tableau croisé : c'est la piste d'audit qui relie l'analytique à
la comptabilité.

### 6. Vérifier un total

Prendre un chantier, comparer la somme du tableau croisé au total de la même
sélection sur la feuille Détail. S'ils divergent, le domaine ou un filtre n'a
pas suivi.

---

## Les deux moitiés du problème

| La moitié | Le remède | Le coût |
|---|---|---|
| Imputer 50 lignes sur un ou deux chantiers | le module `dfd_analytic_bulk` | développement |
| Lire un rapport qui ne se déplie pas | ce tableau croisé | une demi-heure de souris |

**Livrer l'une sans l'autre déçoit.** Les factures seront proprement
imputées, et le rapport affichera quand même cinquante lignes par facture.

---

## Ce qui reste à établir sur les vraies bases

Ce document est écrit à partir de l'inspection consignée dans la
spécification du 25 août 2026 et des sources d'Odoo 19.0. **Le tableau de
bord lui-même n'a pas été rouvert depuis.** À vérifier :

- le contenu réel du JSON des deux rapports, et en quoi ils diffèrent ;
- la colonne du plan de chaque côté — `account_id` ou `x_plan<id>_id` ;
- si une facture Peppol longue existe déjà dans la base, ou si personne n'a
  encore vu le problème en vrai.
