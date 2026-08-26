# Imputer les lignes — guide d'utilisation

Pour Deliso. Odoo 19.

---

## À quoi ça sert

Une facture fournisseur Peppol arrive avec trente, quarante ou cinquante
lignes. Elles concernent un chantier, parfois deux. Jusqu'ici, il fallait
ouvrir chaque ligne et poser le chantier à la main.

Un bouton **Imputer les lignes** fait le travail d'un coup.

Il se trouve en haut de l'écran, à côté de *Confirmer* et *Annuler*, sur les
factures fournisseurs, les factures clients, les commandes d'achat et les
commandes de vente.

---

## Sur une facture

**1. Ouvrez la facture** et cliquez **Imputer les lignes**.

**2. Une fenêtre s'ouvre et vous annonce ce qu'elle va faire.** Par exemple :

> Les 47 lignes de produit recevront la distribution analytique.

ou, si certaines lignes portent déjà un chantier :

> 3 des 47 lignes de produit sont déjà imputées. Qu'en faire ?

**3. Choisissez le chantier.** Vous pouvez en mettre **plusieurs avec des
pourcentages** — 60 % sur Bullange, 40 % sur Burg-Reuland. La somme doit faire
100 %.

**4. Cliquez Appliquer.**

---

## Votre travail à la main n'est jamais écrasé

C'est la protection la plus importante du bouton.

Si vous aviez déjà imputé trois lignes à la main, la fenêtre vous le dit et
vous laisse choisir :

| Choix | Effet |
|---|---|
| **N'affecter que les lignes vides** *(par défaut)* | vos trois lignes sont conservées telles quelles |
| **Écraser toutes les lignes** | tout est remplacé, y compris vos trois lignes |

Le premier choix est celui coché d'avance. Rien ne disparaît sans que vous
l'ayez demandé.

---

## Poser aussi un compte et une TVA

Sur une facture **en brouillon**, la fenêtre offre deux champs de plus :

- **Compte comptable** — le 604, le 611…
- **Taxes** — le taux de TVA

Une facture de matériaux, c'est souvent le même compte et la même TVA sur
toutes les lignes. Ces deux champs vous évitent de les reprendre une par une.

> **Un champ laissé vide n'est pas touché.**
>
> Si vous ne remplissez que la TVA, les comptes et les chantiers de vos lignes
> restent exactement comme ils étaient. Vous pouvez donc corriger une seule
> chose sans risquer d'en défaire une autre.

Attention : le compte et la TVA s'appliquent à **toutes** les lignes de
produit, sans le choix « lignes vides seulement ». Une ligne a toujours un
compte — il n'y en a jamais de vide.

---

## Ce que le bouton ne touche jamais

- Les **sections** et les **notes** de votre facture.
- Les lignes de **TVA** et la ligne du **fournisseur** en bas de la facture.
- Les lignes d'**escompte** et d'**arrondi**.

Seules les lignes de produit sont modifiées.

---

## Sur une facture déjà comptabilisée

Le compte et la TVA **disparaissent de la fenêtre**. Ce n'est pas un oubli :

- Odoo refuse de modifier la TVA d'une pièce comptabilisée, quoi qu'on fasse.
- Changer le compte d'une ligne déjà lettrée **défait le lettrage**, donc un
  rapprochement bancaire.

Le chantier, lui, reste modifiable — sauf si la période est **verrouillée**.
Dans ce cas le bouton refuse et vous le dit.

---

## Sur une commande d'achat ou de vente

Un champ **Distribution analytique** est disponible directement dans l'en-tête
de la commande. C'est utile : au moment de commander, vous savez déjà pour
quel chantier vous achetez.

Rempli, un clic sur **Imputer les lignes** pose le chantier sur toutes les
lignes sans rien demander. Laissé vide, le bouton ouvre la fenêtre habituelle.

Les commandes n'ont pas de compte comptable sur leurs lignes : il n'apparaît
qu'au moment de facturer.

---

## Le bouton n'apparaît pas ?

C'est une question de droits. Le bouton est réservé aux personnes autorisées
à gérer la **comptabilité analytique**. Demandez à votre administrateur de
vérifier que ce droit vous est accordé, et que l'option est activée dans les
paramètres de comptabilité.

---

## À savoir : Odoo sait déjà faire une partie de ça

Dans la vue des **écritures comptables**, on peut sélectionner plusieurs
lignes, modifier la colonne analytique une fois, et l'appliquer à toutes.
C'est une fonction standard, elle existait avant ce module.

Ce que le bouton apporte en plus :

- il travaille **depuis la facture**, pas depuis les écritures comptables ;
- il accepte une **répartition en pourcentages** sur plusieurs chantiers ;
- il **protège votre travail manuel** au lieu de l'écraser ;
- il pose aussi le **compte** et la **TVA** en même temps.

---

## Une question, un problème

Écrivez à **support@dorfadoo.be**.
