# Odoo 19 en local

Un Odoo 19.0 sur sa propre machine, pour développer et éprouver les modules de
ce dépôt sans déranger un serveur ni attendre personne.

## Une fois pour toutes

Installer **Docker Desktop**. Dans ses réglages, lui donner au moins **4 Go de
mémoire** — Odoo démarre avec moins, mais l'installation de la comptabilité
traîne.

## Démarrer

```bash
git clone https://github.com/febifeba/deliso.git
cd deliso/docker
docker compose up -d
```

Le premier démarrage télécharge les images : quelques minutes. Ensuite,
ouvrir <http://localhost:8069>.

## Créer la base

Au premier écran, Odoo demande de créer une base de données.

| Champ | Valeur |
|---|---|
| Master Password | (laisser vide) |
| Database Name | `deliso` |
| Email | `admin` |
| Password | `admin` |
| Language | Français (BE) |
| Country | Belgium |
| Demo data | **cocher** |

Les données de démonstration fournissent des contacts, des articles et un plan
comptable — de quoi essayer tout de suite sans rien saisir.

Le pays **Belgium** installe le plan comptable belge, celui de Deliso.

## Installer le module

Le module vit dans `addons/` du dépôt, monté dans le conteneur. Odoo ne le voit
pas encore : sa liste d'applications date de la création de la base.

1. **Activer le mode développeur** : Paramètres → tout en bas, *Activer le mode
   développeur*.
2. **Mettre à jour la liste** : Applications → menu *Mettre à jour la liste des
   applications* → *Mettre à jour*.
3. Chercher **`dfd`**, retirer le filtre *Applications* de la barre de
   recherche (le module n'en est pas une), puis **Installer**.

## Activer la comptabilité analytique

Sans elle, le champ et le bouton du module n'apparaissent nulle part.

Comptabilité → Configuration → Paramètres → section *Analytique* → cocher
**Comptabilité analytique**, puis *Enregistrer*.

Créer ensuite un plan analytique et deux ou trois comptes, qui tiendront lieu
de chantiers : Comptabilité → Configuration → *Plans analytiques*, puis
*Comptes analytiques*.

## Essayer

Créer une facture fournisseur de plusieurs lignes, renseigner **Distribution
analytique** dans l'en-tête — une répartition à 60/40 sur deux chantiers montre
ce que la cascade native par projet ne sait pas faire — puis cliquer
**Appliquer à toutes les lignes**.

Pour voir l'écran de confirmation, imputer d'abord une ligne à la main sur un
autre chantier : le module refuse d'écraser sans demander.

## Lancer les tests

Le serveur doit être arrêté, sinon deux Odoo se disputent la base.

```bash
docker compose stop odoo
docker compose run --rm odoo odoo \
  -d deliso -u dfd_analytic_bulk \
  --test-enable --test-tags /dfd_analytic_bulk \
  --stop-after-init --max-cron-threads=0 \
  --log-level=warn --log-handler=odoo.tests:INFO
docker compose start odoo
```

La dernière ligne du journal donne le verdict :

```
0 failed, 0 error(s) of 15 tests
```

## Après une modification du code

Python modifié → redémarrer : `docker compose restart odoo`.
Vues XML ou droits modifiés → mettre le module à jour :

```bash
docker compose stop odoo
docker compose run --rm odoo odoo -d deliso -u dfd_analytic_bulk --stop-after-init
docker compose start odoo
```

## Repartir de zéro

```bash
docker compose down -v
```

Efface la base et les fichiers joints. Les images restent.
