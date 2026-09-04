"""HTML + plain-text templates for transactional emails."""

from __future__ import annotations

import html


# Brand palette (aligned with static/css/style.css)
_BG = "#FDFBF7"
_SURFACE = "#FFFFFF"
_TEXT = "#2C2825"
_MUTED = "#6B6560"
_ACCENT = "#B8864A"
_ACCENT_LIGHT = "#E8DCC8"
_SUCCESS = "#4A7C59"
_SUCCESS_BG = "#E8F0EB"
_BORDER = "#E8E2D9"


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _money(amount: float) -> str:
    return f"{amount:.2f} €"


def _format_items_text(items: list[dict]) -> str:
    lines = []
    for item in items:
        name = item.get("product_name") or item.get("name") or "Article"
        qty = int(item.get("quantity") or item.get("qty") or 1)
        price = float(item.get("unit_price") or item.get("price") or 0)
        lines.append(f"  • {name} × {qty} — {_money(price * qty)}")
    return "\n".join(lines) if lines else "  • (aucun article)"


def _format_totals_text(*, subtotal: float, shipping_fee: float, total: float) -> str:
    shipping = "Offerte" if shipping_fee <= 0 else _money(shipping_fee)
    return (
        f"Sous-total : {_money(subtotal)}\n"
        f"Livraison : {shipping}\n"
        f"Total payé : {_money(total)}"
    )


def _items_rows_html(items: list[dict]) -> str:
    if not items:
        return (
            '<tr><td colspan="3" style="padding:12px 16px;color:#6B6560;'
            'font-size:14px;">Aucun article</td></tr>'
        )
    rows: list[str] = []
    for item in items:
        name = _e(item.get("product_name") or item.get("name") or "Article")
        qty = int(item.get("quantity") or item.get("qty") or 1)
        price = float(item.get("unit_price") or item.get("price") or 0)
        line_total = _money(price * qty)
        rows.append(
            f'<tr>'
            f'<td style="padding:14px 16px;border-bottom:1px solid {_BORDER};'
            f'color:{_TEXT};font-size:14px;line-height:1.4;">{name}</td>'
            f'<td style="padding:14px 12px;border-bottom:1px solid {_BORDER};'
            f'color:{_MUTED};font-size:14px;text-align:center;">× {qty}</td>'
            f'<td style="padding:14px 16px;border-bottom:1px solid {_BORDER};'
            f'color:{_TEXT};font-size:14px;text-align:right;white-space:nowrap;">'
            f"{line_total}</td>"
            f"</tr>"
        )
    return "".join(rows)


def _totals_html(*, subtotal: float, shipping_fee: float, total: float) -> str:
    shipping_label = "Offerte ✨" if shipping_fee <= 0 else _money(shipping_fee)
    shipping_color = _SUCCESS if shipping_fee <= 0 else _TEXT
    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
           style="margin-top:8px;">
      <tr>
        <td style="padding:6px 0;color:{_MUTED};font-size:14px;">Sous-total</td>
        <td style="padding:6px 0;color:{_TEXT};font-size:14px;text-align:right;">
          {_money(subtotal)}</td>
      </tr>
      <tr>
        <td style="padding:6px 0;color:{_MUTED};font-size:14px;">Livraison</td>
        <td style="padding:6px 0;color:{shipping_color};font-size:14px;text-align:right;">
          {shipping_label}</td>
      </tr>
      <tr>
        <td style="padding:14px 0 0;color:{_TEXT};font-size:16px;font-weight:600;
                   border-top:2px solid {_ACCENT_LIGHT};">Total payé</td>
        <td style="padding:14px 0 0;color:{_ACCENT};font-size:18px;font-weight:700;
                   text-align:right;border-top:2px solid {_ACCENT_LIGHT};">
          {_money(total)}</td>
      </tr>
    </table>
    """


def _address_html(address: str) -> str:
    lines = [_e(line) for line in address.strip().splitlines() if line.strip()]
    if not lines:
        return f'<span style="color:{_MUTED};">—</span>'
    return "<br>".join(lines)


def _wrap_layout(
    *,
    preheader: str,
    eyebrow: str,
    title: str,
    body_html: str,
    footer_note: str = "Amour Crochet Garden — créations crochet faites main avec amour.",
) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light">
  <title>{_e(title)}</title>
</head>
<body style="margin:0;padding:0;background-color:{_BG};font-family:Arial,Helvetica,sans-serif;
             color:{_TEXT};-webkit-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">
    {_e(preheader)}
  </div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
         style="background-color:{_BG};padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
               style="max-width:560px;">
          <!-- Header -->
          <tr>
            <td style="padding:0 0 24px;text-align:center;">
              <div style="display:inline-block;padding:10px 20px;background:{_SURFACE};
                          border-radius:999px;border:1px solid {_BORDER};
                          box-shadow:0 2px 12px rgba(44,40,37,0.06);">
                <span style="font-family:Georgia,'Times New Roman',serif;font-size:22px;
                             font-weight:600;color:{_TEXT};letter-spacing:0.02em;">
                  Amour Crochet Garden
                </span>
              </div>
            </td>
          </tr>
          <!-- Card -->
          <tr>
            <td style="background:{_SURFACE};border-radius:16px;border:1px solid {_BORDER};
                       box-shadow:0 4px 24px rgba(44,40,37,0.08);overflow:hidden;">
              <div style="height:4px;background:linear-gradient(90deg,{_ACCENT},{_ACCENT_LIGHT});">
              </div>
              <div style="padding:32px 28px 28px;">
                <p style="margin:0 0 8px;font-size:12px;font-weight:600;letter-spacing:0.12em;
                          text-transform:uppercase;color:{_ACCENT};">{_e(eyebrow)}</p>
                <h1 style="margin:0 0 20px;font-family:Georgia,'Times New Roman',serif;
                           font-size:28px;font-weight:600;line-height:1.25;color:{_TEXT};">
                  {_e(title)}
                </h1>
                {body_html}
              </div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:24px 8px 0;text-align:center;">
              <p style="margin:0;font-size:13px;line-height:1.6;color:{_MUTED};">
                {_e(footer_note)}
              </p>
              <p style="margin:8px 0 0;font-size:12px;color:{_ACCENT_LIGHT};">
                🧶 Merci de soutenir l'artisanat fait main
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _section_label(text: str) -> str:
    return (
        f'<p style="margin:24px 0 10px;font-size:12px;font-weight:600;letter-spacing:0.1em;'
        f'text-transform:uppercase;color:{_MUTED};">{_e(text)}</p>'
    )


def _info_box(content_html: str) -> str:
    return (
        f'<div style="background:{_BG};border:1px solid {_BORDER};border-radius:12px;'
        f'padding:16px 18px;font-size:14px;line-height:1.6;color:{_TEXT};">'
        f"{content_html}</div>"
    )


def build_customer_confirmation(
    *,
    customer_name: str,
    reference: str,
    subtotal: float,
    shipping_fee: float,
    total: float,
    shipping_address: str,
    items: list[dict],
) -> tuple[str, str]:
    first = (customer_name or "").strip() or "Bonjour"
    address_block = shipping_address.strip() or "—"

    text_body = (
        f"Bonjour {first},\n\n"
        "Merci pour votre commande ! Nous avons bien reçu votre paiement.\n\n"
        "Notre équipe prépare vos créations avec soin. "
        "Nous vous recontacterons très prochainement pour organiser "
        "la livraison ou le retrait.\n\n"
        f"Référence : {reference}\n\n"
        f"Adresse de livraison :\n{address_block}\n\n"
        "Votre commande :\n"
        f"{_format_items_text(items)}\n\n"
        f"{_format_totals_text(subtotal=subtotal, shipping_fee=shipping_fee, total=total)}\n\n"
        "À très bientôt,\n"
        "Amour Crochet Garden\n"
    )

    body_html = f"""
    <p style="margin:0 0 16px;font-size:16px;line-height:1.65;color:{_TEXT};">
      Bonjour <strong>{_e(first)}</strong>,
    </p>
    <div style="background:{_SUCCESS_BG};border-radius:12px;padding:16px 18px;
                margin-bottom:20px;border-left:4px solid {_SUCCESS};">
      <p style="margin:0;font-size:15px;line-height:1.6;color:{_TEXT};">
        ✓ <strong>Paiement confirmé</strong> — merci pour votre confiance !
      </p>
      <p style="margin:10px 0 0;font-size:14px;line-height:1.55;color:{_MUTED};">
        Nous préparons vos créations avec soin et vous recontacterons bientôt
        pour la livraison ou le retrait.
      </p>
    </div>
    <div style="text-align:center;margin-bottom:8px;">
      <span style="display:inline-block;background:{_ACCENT_LIGHT};color:{_ACCENT};
                   font-size:13px;font-weight:600;padding:8px 16px;border-radius:999px;
                   letter-spacing:0.04em;">
        Réf. {_e(reference)}
      </span>
    </div>
    {_section_label("Votre commande")}
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
           style="border:1px solid {_BORDER};border-radius:12px;overflow:hidden;
                  border-collapse:separate;">
      <tr style="background:{_BG};">
        <th align="left" style="padding:12px 16px;font-size:12px;font-weight:600;
            color:{_MUTED};text-transform:uppercase;letter-spacing:0.06em;">Article</th>
        <th style="padding:12px 12px;font-size:12px;font-weight:600;color:{_MUTED};
            text-transform:uppercase;letter-spacing:0.06em;">Qté</th>
        <th align="right" style="padding:12px 16px;font-size:12px;font-weight:600;
            color:{_MUTED};text-transform:uppercase;letter-spacing:0.06em;">Total</th>
      </tr>
      {_items_rows_html(items)}
    </table>
    {_totals_html(subtotal=subtotal, shipping_fee=shipping_fee, total=total)}
    {_section_label("Adresse de livraison")}
    {_info_box(_address_html(address_block))}
    <p style="margin:28px 0 0;font-size:15px;line-height:1.6;color:{_TEXT};">
      À très bientôt,<br>
      <span style="font-family:Georgia,'Times New Roman',serif;font-size:17px;
                   color:{_ACCENT};">L'équipe Amour Crochet Garden</span>
    </p>
    """

    html_body = _wrap_layout(
        preheader=f"Commande {reference} confirmée — merci {first} !",
        eyebrow="Confirmation de commande",
        title="Merci pour votre commande !",
        body_html=body_html,
    )
    return text_body, html_body


def build_admin_notification(
    *,
    customer_name: str,
    customer_email: str,
    customer_phone: str | None,
    reference: str,
    subtotal: float,
    shipping_fee: float,
    total: float,
    shipping_address: str,
    items: list[dict],
) -> tuple[str, str]:
    phone = customer_phone or "—"
    address_block = shipping_address.strip() or "—"

    text_body = (
        "Nouvelle commande payée 🎉\n\n"
        f"Référence : {reference}\n"
        f"Client : {customer_name}\n"
        f"Email : {customer_email}\n"
        f"Téléphone : {phone}\n\n"
        f"Adresse de livraison :\n{address_block}\n\n"
        "Articles :\n"
        f"{_format_items_text(items)}\n\n"
        f"{_format_totals_text(subtotal=subtotal, shipping_fee=shipping_fee, total=total)}\n\n"
        "Connectez-vous à l'admin pour voir le détail.\n"
    )

    body_html = f"""
    <p style="margin:0 0 20px;font-size:16px;line-height:1.65;color:{_TEXT};">
      Une nouvelle commande vient d'être payée.
    </p>
    <div style="text-align:center;margin-bottom:20px;">
      <span style="display:inline-block;background:{_ACCENT};color:#FFFFFF;
                   font-size:20px;font-weight:700;padding:12px 24px;border-radius:12px;">
        {_money(total)}
      </span>
      <p style="margin:10px 0 0;font-size:13px;color:{_MUTED};">
        Réf. {_e(reference)}
      </p>
    </div>
    {_section_label("Client")}
    {_info_box(
        f'<strong>{_e(customer_name)}</strong><br>'
        f'<a href="mailto:{_e(customer_email)}" style="color:{_ACCENT};'
        f'text-decoration:none;">{_e(customer_email)}</a><br>'
        f'<span style="color:{_MUTED};">{_e(phone)}</span>'
    )}
    {_section_label("Articles")}
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
           style="border:1px solid {_BORDER};border-radius:12px;overflow:hidden;
                  border-collapse:separate;">
      <tr style="background:{_BG};">
        <th align="left" style="padding:12px 16px;font-size:12px;font-weight:600;
            color:{_MUTED};">Article</th>
        <th style="padding:12px 12px;font-size:12px;font-weight:600;color:{_MUTED};">Qté</th>
        <th align="right" style="padding:12px 16px;font-size:12px;font-weight:600;
            color:{_MUTED};">Total</th>
      </tr>
      {_items_rows_html(items)}
    </table>
    {_totals_html(subtotal=subtotal, shipping_fee=shipping_fee, total=total)}
    {_section_label("Adresse de livraison")}
    {_info_box(_address_html(address_block))}
    <p style="margin:24px 0 0;font-size:14px;color:{_MUTED};">
      Consultez le détail dans l'espace admin → Commandes.
    </p>
    """

    html_body = _wrap_layout(
        preheader=f"Nouvelle commande {reference} — {_money(total)}",
        eyebrow="Alerte boutique",
        title="Nouvelle commande payée",
        body_html=body_html,
        footer_note="Notification automatique — Amour Crochet Garden Admin",
    )
    return text_body, html_body
