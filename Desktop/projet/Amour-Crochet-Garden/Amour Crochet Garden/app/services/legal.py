"""Legal / info page content (French)."""

from __future__ import annotations

import html


def _pages(contact_email: str) -> dict[str, dict]:
    email = html.escape(contact_email or "contact@amourcrochetgarden.fr", quote=True)
    return {
        "faq": {
            "title": "FAQ",
            "subtitle": "Les réponses aux questions les plus fréquentes",
            "active": "faq",
            "html": f"""
<h2>Commandes &amp; paiement</h2>
<details class="faq-item" open>
  <summary>Comment passer commande&nbsp;?</summary>
  <p>Ajoutez vos créations au panier, cliquez sur «&nbsp;Commander&nbsp;», renseignez vos coordonnées de livraison, puis réglez en ligne de façon sécurisée.</p>
</details>
<details class="faq-item">
  <summary>Quels moyens de paiement acceptez-vous&nbsp;?</summary>
  <p>Le paiement s’effectue en ligne via SumUp (carte bancaire et autres moyens disponibles selon votre pays). Aucune donnée bancaire n’est stockée sur notre site.</p>
</details>
<details class="faq-item">
  <summary>Puis-je modifier ou annuler ma commande&nbsp;?</summary>
  <p>Contactez-nous rapidement à <a href="mailto:{email}">{email}</a> avec votre référence de commande. Une fois la préparation commencée, une modification peut ne plus être possible.</p>
</details>

<h2>Livraison</h2>
<details class="faq-item">
  <summary>Quels sont les frais de livraison&nbsp;?</summary>
  <p><strong>5&nbsp;€</strong> pour les commandes inférieures à 50&nbsp;€. <strong>Livraison offerte</strong> dès 50&nbsp;€ d’achat (sous-total articles).</p>
</details>
<details class="faq-item">
  <summary>Quels sont les délais&nbsp;?</summary>
  <p>Chaque pièce est faite main. Comptez en général quelques jours à quelques semaines selon le stock et la charge de travail. Nous vous recontactons après paiement pour confirmer le délai et organiser l’envoi ou le retrait.</p>
</details>

<h2>Produits</h2>
<details class="faq-item">
  <summary>Les créations sont-elles uniques&nbsp;?</summary>
  <p>Oui&nbsp;: la plupart sont réalisées à la main. Les couleurs et les détails peuvent légèrement varier&nbsp;: c’est tout le charme de l’artisanat.</p>
</details>
<details class="faq-item">
  <summary>Comment entretenir un article en crochet&nbsp;?</summary>
  <p>Lavage délicat à la main à l’eau tiède, séchage à plat. Évitez le sèche-linge et l’eau trop chaude.</p>
</details>

<h2>Contact</h2>
<details class="faq-item">
  <summary>Comment vous joindre&nbsp;?</summary>
  <p>Utilisez le formulaire de contact du site, ou écrivez-nous à <a href="mailto:{email}">{email}</a>. Nous vous répondons dans les meilleurs délais.</p>
</details>
""",
        },
        "livraison": {
            "title": "Livraison",
            "subtitle": "Frais, délais et modalités d’envoi",
            "active": "livraison",
            "html": f"""
<p>Cette page décrit les modalités de livraison des commandes passées sur <strong>Amour Crochet Garden</strong>.</p>

<h2>Zone de livraison</h2>
<p>Nous livrons principalement en <strong>France métropolitaine</strong>. Pour la Belgique, le Luxembourg, la Suisse ou une autre destination, contactez-nous avant de commander à <a href="mailto:{email}">{email}</a>.</p>

<h2>Frais de livraison</h2>
<ul>
  <li><strong>5&nbsp;€</strong> si le sous-total des articles est inférieur à 50&nbsp;€</li>
  <li><strong>Offerte</strong> dès 50&nbsp;€ d’achat (sous-total articles)</li>
</ul>
<p>Les frais sont calculés automatiquement dans le panier et à l’étape de livraison.</p>

<h2>Délais</h2>
<p>Les créations sont artisanales. Après confirmation du paiement&nbsp;:</p>
<ul>
  <li><strong>article en stock</strong>&nbsp;: préparation et envoi sous quelques jours ouvrés en moyenne</li>
  <li><strong>article à réaliser</strong>&nbsp;: le délai vous est communiqué par e-mail</li>
</ul>
<p>Nous vous contactons après paiement pour organiser la livraison ou, le cas échéant, un retrait.</p>

<h2>Suivi</h2>
<p>Un e-mail de confirmation de paiement vous est envoyé. Les informations de suivi (lorsqu’elles sont disponibles) vous sont communiquées dès l’expédition.</p>

<h2>Retrait</h2>
<p>Un retrait en main propre peut être proposé selon les événements ou sur accord. Indiquez-le dans votre message ou contactez-nous.</p>

<h2>Problème de livraison</h2>
<p>Colis endommagé, non reçu ou erreur&nbsp;: contactez-nous sous 48&nbsp;h à <a href="mailto:{email}">{email}</a> avec votre référence de commande et, si possible, des photos.</p>
""",
        },
        "retours": {
            "title": "Retours &amp; échanges",
            "subtitle": "Droit de rétractation et conditions",
            "active": "retours",
            "html": f"""
<p>Conformément au droit de la consommation, vous disposez d’un droit de rétractation pour les achats à distance, sous réserve des exceptions légales.</p>

<h2>Délai de rétractation</h2>
<p>Vous disposez de <strong>14 jours</strong> à compter de la réception de votre commande pour exercer votre droit de rétractation, sans avoir à justifier de motif.</p>

<h2>Exceptions</h2>
<p>Le droit de rétractation ne s’applique pas notamment aux biens confectionnés selon les spécifications du consommateur ou nettement personnalisés (créations sur mesure).</p>

<h2>Conditions de retour</h2>
<ul>
  <li>articles non portés / non utilisés, dans leur état d’origine</li>
  <li>retour dans un emballage adapté</li>
  <li>joindre la référence de commande et vos coordonnées</li>
</ul>

<h2>Procédure</h2>
<ol>
  <li>Écrivez à <a href="mailto:{email}">{email}</a> pour signaler votre demande de retour</li>
  <li>Attendez notre confirmation avant de renvoyer le colis</li>
  <li>Après réception et contrôle, le remboursement est effectué sous 14 jours</li>
</ol>

<h2>Frais de retour</h2>
<p>Sauf produit défectueux ou erreur de notre part, les frais de retour restent à votre charge.</p>

<h2>Échanges</h2>
<p>Les échanges sont étudiés au cas par cas (disponibilité, couleur, modèle). Contactez-nous pour en discuter.</p>
""",
        },
        "confidentialite": {
            "title": "Politique de confidentialité",
            "subtitle": "Protection de vos données personnelles (RGPD)",
            "active": "confidentialite",
            "html": f"""
<p><strong>Amour Crochet Garden</strong> s’engage à protéger vos données personnelles conformément au Règlement général sur la protection des données (RGPD) et à la loi Informatique et Libertés.</p>

<h2>Responsable du traitement</h2>
<p>Amour Crochet Garden — contact&nbsp;: <a href="mailto:{email}">{email}</a></p>

<h2>Données collectées</h2>
<ul>
  <li><strong>Commande</strong>&nbsp;: nom, prénom, e-mail, téléphone (optionnel), adresse postale, contenu du panier</li>
  <li><strong>Contact</strong>&nbsp;: nom, e-mail, message</li>
  <li><strong>Technique</strong>&nbsp;: cookies nécessaires au fonctionnement (session, panier), et cookies analytiques uniquement avec votre consentement</li>
</ul>

<h2>Finalités</h2>
<ul>
  <li>traiter et livrer vos commandes</li>
  <li>envoyer la confirmation de paiement et vous recontacter</li>
  <li>répondre à vos messages</li>
  <li>assurer la sécurité du site et, le cas échéant, mesurer l’audience (avec consentement)</li>
</ul>

<h2>Base légale</h2>
<ul>
  <li>exécution du contrat (commande)</li>
  <li>intérêt légitime (sécurité, réponses aux messages)</li>
  <li>consentement (cookies non essentiels / mesure d’audience)</li>
</ul>

<h2>Destinataires</h2>
<p>Vos données sont destinées à Amour Crochet Garden. Le paiement est traité par le prestataire <strong>SumUp</strong>&nbsp;; nous ne stockons pas vos données bancaires. Des sous-traitants techniques (hébergement, envoi d’e-mails) peuvent intervenir dans le respect du RGPD.</p>

<h2>Durée de conservation</h2>
<ul>
  <li>données de commande&nbsp;: durée nécessaire à la gestion commerciale et aux obligations légales</li>
  <li>messages de contact&nbsp;: le temps du traitement de votre demande</li>
  <li>cookies&nbsp;: selon la durée indiquée dans la <a href="/cookies">politique cookies</a></li>
</ul>

<h2>Vos droits</h2>
<p>Vous disposez des droits d’accès, de rectification, d’effacement, de limitation, d’opposition et de portabilité. Pour les exercer&nbsp;: <a href="mailto:{email}">{email}</a>.</p>
<p>Vous pouvez également introduire une réclamation auprès de la CNIL (<a href="https://www.cnil.fr" target="_blank" rel="noopener noreferrer">www.cnil.fr</a>).</p>

<h2>Sécurité</h2>
<p>Nous mettons en œuvre des mesures raisonnables pour protéger vos données (HTTPS en production, accès administrateur protégé, aucun stockage de données de carte bancaire).</p>
""",
        },
        "cookies": {
            "title": "Politique cookies",
            "subtitle": "Quels cookies utilisons-nous et pourquoi",
            "active": "cookies",
            "html": f"""
<p>Cette page complète la <a href="/confidentialite">politique de confidentialité</a> et explique l’usage des cookies sur le site.</p>

<h2>Qu’est-ce qu’un cookie&nbsp;?</h2>
<p>Un cookie est un petit fichier déposé sur votre appareil lors de la visite d’un site. Il permet de faire fonctionner le site ou de mesurer l’audience.</p>

<h2>Cookies nécessaires (toujours actifs)</h2>
<ul>
  <li><strong>Session</strong>&nbsp;: panier, sécurité, connexion administrateur — indispensables au fonctionnement</li>
  <li><strong>Préférence de consentement</strong>&nbsp;: mémorise votre choix cookies</li>
</ul>
<p>Ces cookies ne nécessitent pas votre consentement.</p>

<h2>Cookies analytiques (sur consentement)</h2>
<ul>
  <li>mesure anonymisée / agrégée des pages vues pour améliorer le site</li>
</ul>
<p>Ils ne sont déposés <strong>qu’après votre acceptation</strong> via le bandeau cookies.</p>

<h2>Gérer vos choix</h2>
<p>Vous pouvez accepter, refuser les cookies optionnels, ou modifier votre choix à tout moment via le lien «&nbsp;Gérer les cookies&nbsp;» en bas de page.</p>

<h2>Durée</h2>
<ul>
  <li>session&nbsp;: durée de la session (24&nbsp;h maximum)</li>
  <li>consentement&nbsp;: jusqu’à 6 mois</li>
</ul>

<p>Questions&nbsp;: <a href="mailto:{email}">{email}</a></p>
""",
        },
        "mentions-legales": {
            "title": "Mentions légales",
            "subtitle": "Informations légales du site",
            "active": "mentions",
            "html": f"""
<h2>Éditeur</h2>
<p>
<strong>Ouxiang Ji</strong> — entreprise individuelle (micro-entreprise)<br>
Nom commercial&nbsp;: Amour Crochet Garden<br>
SIRET&nbsp;: 823&nbsp;361&nbsp;381&nbsp;00028<br>
13, allée Gabrielle d’Estrées, 75019 Paris<br>
E-mail&nbsp;: <a href="mailto:{email}">{email}</a><br>
Responsable de la publication&nbsp;: Ouxiang Ji
</p>

<h2>Hébergement</h2>
<p>
Hostinger Operations, UAB — Švitrigailos str. 34, LT-03230 Vilnius, Lituanie<br>
<a href="https://www.hostinger.fr" target="_blank" rel="noopener noreferrer">www.hostinger.fr</a>
</p>

<h2>Propriété intellectuelle</h2>
<p>Les contenus du site (textes, photos, logo, créations) sont protégés. Toute reproduction non autorisée est interdite.</p>

<h2>Contact</h2>
<p><a href="mailto:{email}">{email}</a></p>
""",
        },
    }


def get_legal_page(slug: str, contact_email: str) -> dict | None:
    return _pages(contact_email).get(slug)
