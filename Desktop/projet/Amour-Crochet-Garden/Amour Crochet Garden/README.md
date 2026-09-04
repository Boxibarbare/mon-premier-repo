# Amour Crochet Garden

Site e-commerce artisanal pour **Amour Crochet Garden** — créations au crochet faites main.

- Catalogue, panier, checkout SumUp
- E-mails de confirmation (SMTP)
- Admin (produits, événements, commandes, feedback, parrainage)
- Pages légales RGPD + bandeau cookies

---

## Prérequis

- [UV](https://docs.astral.sh/uv/)
- Python 3.11+

## Installation (local)

```bash
make install
# ou: uv sync

cp .env.example .env
# Éditer .env : SECRET_KEY (obligatoire, ≥ 32 caractères), admin, SumUp, SMTP…
```

Générer une clé secrète :

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Lancement

```bash
make dev    # développement (reload)
make run    # production locale
```

- Site : http://127.0.0.1:8000  
- Admin : http://127.0.0.1:8000/admin  

## Configuration utile

| Variable | Rôle |
|----------|------|
| `SECRET_KEY` | Signature des sessions (≥ 32 car., obligatoire) |
| `DEBUG` | `true` en local, `false` en prod |
| `MOCK_PAYMENTS` | `true` = paiement simulé (dev) |
| `MOCK_EMAILS` | `false` = vrais e-mails SMTP même en dev |
| `HTTPS_ONLY` | `true` en production HTTPS |
| `PRODUCTION=1` | Garde-fous stricts (prod) |
| `ALLOWED_HOSTS` | Domaines autorisés (prod) |
| `SUMUP_*` | Paiement SumUp |
| `SMTP_*` | E-mails |

Voir aussi [SECURITY.md](SECURITY.md).

## Paiement (SumUp)

1. [me.sumup.com](https://me.sumup.com) → API Keys  
2. Renseigner `SUMUP_API_KEY` et `SUMUP_MERCHANT_CODE` dans `.env`

## E-mails

Après paiement confirmé : confirmation client + alerte admin.  
Configurer SMTP dans `.env`. Test depuis **Admin → Paramètres**.

## Mise en ligne (Hostinger)

Guide complet pas à pas (choix du KVM, Nginx, SSL, systemd) :

→ **[HOSTINGER.md](HOSTINGER.md)**

**Résumé** : prendre un **VPS KVM 2** (Ubuntu), pas un hébergement mutualisé.

## Avant d’ouvrir au public

- [ ] Mentions légales : SIRET, adresse, responsable de publication
- [ ] Mot de passe admin fort
- [ ] `DEBUG=false`, `MOCK_*=false`, `HTTPS_ONLY=true`, `PRODUCTION=1`
- [ ] Texte « À propos » + réseaux sociaux (Admin → Paramètres)
- [ ] Test commande réelle SumUp + e-mails
- [ ] Rotation des secrets si jamais exposés

## Structure

```
app/           # FastAPI (routes, modèles, sécurité, e-mails)
static/        # CSS, images, uploads
templates/     # Pages publiques + admin
HOSTINGER.md   # Déploiement VPS
SECURITY.md    # Mesures de sécurité
```

## Commandes Make

| Commande | Description |
|----------|-------------|
| `make install` | Dépendances |
| `make dev` | Serveur + reload |
| `make run` | Serveur prod |
| `make lint` | Ruff |
| `make format` | Formatage |

## Stack

FastAPI · SQLAlchemy · SQLite · Jinja2 · SumUp · SMTP · Loguru
