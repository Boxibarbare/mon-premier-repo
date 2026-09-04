# Déploiement Hostinger — Amour Crochet Garden

Guide pas à pas pour mettre le site en ligne sur un **VPS Hostinger (KVM)**.

> **Important** : ce projet est une app **FastAPI (Python)**. Un hébergement web mutualisé (WordPress / PHP) **ne convient pas**. Il faut un **VPS** avec accès root.

---

## 1. Quel KVM choisir ?

| Plan | Specs | Pour qui ? |
|------|--------|------------|
| **KVM 1** | 1 vCPU · 4 Go RAM · 50 Go NVMe | Test / budget serré |
| **KVM 2** ★ | 2 vCPU · 8 Go RAM · 100 Go NVMe | **Recommandé** pour la boutique |
| KVM 4 | 4 vCPU · 16 Go RAM · 200 Go | Trafic élevé / plusieurs sites |

### Recommandation : **KVM 2**

Pour Amour Crochet Garden (catalogue, panier, SumUp, e-mails, admin) :

- **KVM 2** donne de la marge (Python + Nginx + SSL + sauvegardes)
- **KVM 1** fonctionne aussi au démarrage, mais est plus juste si tu ajoutes PostgreSQL ou du trafic

À la commande Hostinger :

1. [hostinger.fr/vps-hosting](https://www.hostinger.fr/vps-hosting) → **KVM 2**
2. Localisation : **France** ou Europe (latence)
3. OS : **Ubuntu 24.04 LTS** (ou 22.04)
4. Domaine : lie ton domaine (ex. `amourcrochetgarden.fr`)

---

## 2. Avant de déployer (checklist)

- [ ] Domaine pointé vers l’IP du VPS (enregistrements **A** `@` et `www`)
- [ ] Compte **SumUp** + clé API + code marchand
- [ ] SMTP prêt (Gmail app password ou mail Hostinger)
- [ ] Mentions légales complétées (SIRET, adresse, responsable) dans Admin ou `legal.py`
- [ ] Mot de passe admin **fort** (≥ 12 caractères)
- [ ] Nouvelle `SECRET_KEY` générée (ne pas réutiliser celle du PC)

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 3. Première connexion au VPS

Dans le panneau Hostinger → VPS → **SSH** (ou terminal local) :

```bash
ssh root@TON_IP_VPS
```

Mets à jour le système :

```bash
apt update && apt upgrade -y
apt install -y nginx certbot python3-certbot-nginx git curl ufw
```

### Pare-feu

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```

### Créer un utilisateur (recommandé)

```bash
adduser deploy
usermod -aG sudo deploy
# puis reconnecte-toi en deploy
```

---

## 4. Installer Python & UV

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # ou redémarre la session SSH

# Vérifier
uv --version
python3 --version   # 3.11+ idéalement
```

Si Python est trop vieux :

```bash
apt install -y python3.12 python3.12-venv
```

---

## 5. Déployer le code

### Option A — Git (recommandé)

```bash
mkdir -p /var/www
cd /var/www
git clone https://github.com/TON_COMPTE/Amour-Crochet-Garden.git amour-crochet
cd amour-crochet
# Si le repo a un sous-dossier "Amour Crochet Garden" :
# cd "Amour Crochet Garden"
```

### Option B — Upload (SFTP / FileZilla)

Envoie tout le projet dans `/var/www/amour-crochet/`  
**Sauf** : `.env` local, `__pycache__`, `logs/`, `*.db` de test (sauf si tu veux garder les données).

Puis :

```bash
cd /var/www/amour-crochet
uv sync
```

---

## 6. Configuration production (`.env`)

```bash
cp .env.example .env
nano .env
```

Exemple **production** :

```env
SECRET_KEY=colle_ici_la_cle_generee_48_chars_minimum
DATABASE_URL=sqlite+aiosqlite:///./amour_crochet.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=MotDePasseTresLongEtUnique!
CONTACT_EMAIL=contact@amourcrochetgarden.fr
MAX_UPLOAD_SIZE_MB=5

DEBUG=false
MOCK_PAYMENTS=false
MOCK_EMAILS=false
HTTPS_ONLY=true
PRODUCTION=1
ALLOWED_HOSTS=amourcrochetgarden.fr,www.amourcrochetgarden.fr

SUMUP_API_KEY=sup_sk_...
SUMUP_MERCHANT_CODE=MC...

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ton@gmail.com
SMTP_PASSWORD=mot_de_passe_application
SMTP_FROM=ton@gmail.com
SMTP_USE_TLS=true
ORDER_NOTIFY_EMAIL=ton@gmail.com
```

Sécurise le fichier :

```bash
chmod 600 .env
```

---

## 7. Lancer l’app avec systemd

Crée le service :

```bash
sudo nano /etc/systemd/system/amour-crochet.service
```

Contenu (adapte le chemin et l’utilisateur) :

```ini
[Unit]
Description=Amour Crochet Garden
After=network.target

[Service]
User=deploy
Group=deploy
WorkingDirectory=/var/www/amour-crochet
EnvironmentFile=/var/www/amour-crochet/.env
ExecStart=/home/deploy/.local/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Active :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now amour-crochet
sudo systemctl status amour-crochet
```

Logs :

```bash
sudo journalctl -u amour-crochet -f
```

---

## 8. Nginx + HTTPS

```bash
sudo nano /etc/nginx/sites-available/amour-crochet
```

```nginx
server {
    listen 80;
    server_name amourcrochetgarden.fr www.amourcrochetgarden.fr;

    client_max_body_size 8M;

    location /static/ {
        alias /var/www/amour-crochet/static/;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Active le site :

```bash
sudo ln -s /etc/nginx/sites-available/amour-crochet /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

SSL (Let's Encrypt) :

```bash
sudo certbot --nginx -d amourcrochetgarden.fr -d www.amourcrochetgarden.fr
```

Certbot configure le renouvellement automatique.

---

## 9. Droits fichiers (uploads)

```bash
sudo mkdir -p /var/www/amour-crochet/static/uploads
sudo mkdir -p /var/www/amour-crochet/logs
sudo chown -R deploy:deploy /var/www/amour-crochet
```

---

## 10. Vérifications finales

1. Ouvre `https://ton-domaine.fr` → page d’accueil
2. `/admin` → connexion avec le **nouveau** mot de passe
3. Ajoute un produit test + photo
4. Passe une petite commande SumUp réelle (ou 0,50 €)
5. Vérifie les e-mails client + admin
6. Complète les **mentions légales** (SIRET, adresse)
7. Ajoute les réseaux sociaux dans Admin → Paramètres
8. Remplis le texte « À propos » dans les paramètres

---

## 11. Mises à jour du site

```bash
cd /var/www/amour-crochet
git pull
uv sync
sudo systemctl restart amour-crochet
```

---

## 12. Sauvegardes

À faire régulièrement (cron ou panneau Hostinger) :

- fichier `.env`
- base `amour_crochet.db`
- dossier `static/uploads/`

Exemple copie locale :

```bash
cp amour_crochet.db backups/amour_$(date +%F).db
```

---

## Problèmes fréquents

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| 502 Bad Gateway | App arrêtée | `systemctl status amour-crochet` |
| Cookies / login KO | `HTTPS_ONLY` / proxy | Vérifier `X-Forwarded-Proto` dans Nginx |
| SumUp KO | Clés / mock | `MOCK_PAYMENTS=false`, clés valides |
| E-mails KO | SMTP | Mot de passe d’application Gmail |
| 403 Host | `ALLOWED_HOSTS` | Ajouter le domaine exact |
| App refuse de démarrer | `PRODUCTION=1` + mauvais `.env` | Mot de passe admin faible, `DEBUG=true`, etc. |

---

## Récap choix Hostinger

| Élément | Choix |
|---------|--------|
| Produit | **VPS KVM** (pas d’hébergement mutualisé) |
| Plan | **KVM 2** (recommandé) |
| OS | Ubuntu 24.04 LTS |
| Reverse proxy | Nginx |
| SSL | Certbot / Let's Encrypt |
| Process | systemd + uvicorn |
