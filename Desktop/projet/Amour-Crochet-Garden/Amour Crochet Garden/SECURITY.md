# Politique de sécurité – Amour Crochet Garden

## Conformité NIS2 (directive UE 2022/2555)

Ce site met en œuvre des mesures de cybersécurité alignées avec la directive NIS2 et les bonnes pratiques OWASP/CIS.

---

## 1. Gestion des risques

- **Configuration** : secrets et clés via variables d’environnement (`.env`), jamais en dur
- **Validation des entrées** : limite de taille, regex pour les emails, types de champs
- **Protection des données** : SumUp gère les paiements ; aucune donnée bancaire stockée en propre
- **Cookies / RGPD** : bandeau de consentement ; cookies analytiques uniquement après acceptation
- **Pages légales** : confidentialité, cookies, mentions, livraison, retours, FAQ

---

## 2. Contrôles d’accès

- **Authentification admin** : bcrypt pour le hachage des mots de passe
- **Sessions** : cookies HttpOnly, SameSite=Lax, Secure en production
- **Limitation des tentatives** : 5 tentatives / 15 min sur la page de login admin
- **Protection CSRF** : jetons CSRF sur tous les formulaires (contact, panier, login admin)

---

## 3. En-têtes de sécurité

- **Content-Security-Policy (CSP)** : restriction des sources de scripts, styles, images
- **Strict-Transport-Security (HSTS)** : 2 ans en production (HTTPS)
- **X-Frame-Options** : SAMEORIGIN (anti-clickjacking)
- **X-Content-Type-Options** : nosniff (anti-MIME sniffing)
- **Referrer-Policy** : strict-origin-when-cross-origin
- **Permissions-Policy** : restriction des API navigateur sensibles

---

## 4. Gestion des incidents

- **Journaux d’audit** : `logs/security.log` (rétention 90 jours)
- **Événements enregistrés** : ADMIN_LOGIN_OK, ADMIN_LOGIN_FAIL, ADMIN_LOGIN_RATE_LIMIT, ADMIN_LOGIN_CSRF_FAIL, ADMIN_LOGOUT
- **Surveillance** : surveiller les échecs de connexion et les dépassements de rate limit

---

## 5. Chiffrement et données sensibles

- **HTTPS** : obligatoire en production (définir `HTTPS_ONLY=true`)
- **Clé secrète** : minimum 32 caractères, générée avec `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- **Base de données** : en production, privilégier PostgreSQL avec chiffrement au repos

---

## 6. Upload de fichiers

- **Extensions autorisées** : .jpg, .jpeg, .png, .gif, .webp
- **Validation** : magie bytes (signature fichier) pour éviter les fichiers malveillants
- **Taille maximale** : `MAX_UPLOAD_SIZE_MB` (valeur par défaut : 5 Mo)

---

## 7. Chaîne d’approvisionnement

- **Dépendances** : `uv lock` / `pyproject.toml` pour fixer les versions
- **Mises à jour** : `uv lock --upgrade` périodiquement
- **Audit** : `uv pip compile` et revue des CVE connues

---

## 8. Production – checklist

- [ ] `SUMUP_API_KEY` et `SUMUP_MERCHANT_CODE` configurés pour les paiements
- [ ] `SECRET_KEY` : ≥ 32 caractères uniques
- [ ] `DEBUG=false`
- [ ] `HTTPS_ONLY=true` si le site est servi en HTTPS
- [ ] `PRODUCTION=1` pour activer la validation stricte
- [ ] Passerelle reverse (nginx, etc.) avec TLS 1.2+
- [ ] Sauvegardes régulières de la base de données
- [ ] Surveillance des logs `logs/security.log`

---

## Signalement de vulnérabilités

En cas de vulnérabilité de sécurité, contactez : `contact@amourcrochetgarden.fr`
