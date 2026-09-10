"""Rendu HTML et envoi des mails (alerte et recap)."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

from flight_watch.core.digest import DigestData
from flight_watch.core.models import Offer

logger = logging.getLogger(__name__)


class MailerError(RuntimeError):
    """Envoi de mail impossible (config manquante ou erreur SMTP)."""


def send_email(subject: str, html_body: str) -> None:
    host = os.environ.get("SMTP_HOST")
    port_raw = os.environ.get("SMTP_PORT", "587")
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("MAIL_FROM") or username
    recipient = os.environ.get("MAIL_TO")

    if not all([host, username, password, sender, recipient]):
        raise MailerError(
            "Configuration SMTP incomplete (SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD/MAIL_TO manquant)"
        )

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise MailerError(f"SMTP_PORT invalide: {port_raw!r}") from exc

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content("Ce mail necessite un client compatible HTML.")
    message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise MailerError(f"Envoi SMTP echoue: {exc}") from exc

    logger.info("Email envoye: %s -> %s", subject, recipient)


def render_alert_email(offer: Offer) -> tuple[str, str]:
    subject = f"{offer.price_eur:.0f} EUR - {offer.destination} - depart {offer.depart_date.isoformat()}"
    html = f"""\
<html>
  <body style="font-family: sans-serif;">
    <h2>Bon plan {offer.destination} : {offer.price_eur:.0f} EUR</h2>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
      <tr><th align="left">Prix</th><td>{offer.price_eur:.0f} EUR</td></tr>
      <tr><th align="left">Trajet</th><td>{offer.origin} -&gt; {offer.destination} ({offer.depart_date.isoformat()} -&gt; {offer.return_date.isoformat()}, {offer.nights} nuits)</td></tr>
      <tr><th align="left">Compagnies</th><td>{offer.airlines_label}</td></tr>
      <tr><th align="left">Escales</th><td>{offer.stops_label}</td></tr>
      <tr><th align="left">Duree</th><td>{offer.duration_label}</td></tr>
      <tr><th align="left">Source</th><td>{offer.source}</td></tr>
    </table>
    <p><a href="{offer.google_flights_link}">Verifier sur Google Flights</a></p>
  </body>
</html>
"""
    return subject, html


def render_digest_email(digest: DigestData, today_iso: str) -> tuple[str, str]:
    subject = f"Recap veille de vols - {today_iso}"

    rows_lowest = "".join(
        f"<tr><td>{dest}</td><td>{price:.0f} EUR</td><td>{depart}</td><td>{seen}</td></tr>"
        for dest, (price, depart, seen) in sorted(digest.lowest_by_destination.items())
    ) or '<tr><td colspan="4">Aucune donnee</td></tr>'

    rows_month = "".join(
        f"<tr><td>{dest}</td><td>{month}</td><td>{price:.0f} EUR</td><td>{depart}</td></tr>"
        for (dest, month), (price, depart) in sorted(digest.lowest_by_destination_month.items())
    ) or '<tr><td colspan="4">Aucune donnee</td></tr>'

    def fmt_trend(trend: tuple[float, float] | None) -> str:
        if trend is None:
            return "?"
        delta_eur, delta_pct = trend
        return f"{delta_eur:+.0f} EUR ({delta_pct:+.1f}%)"

    rows_trend = "".join(
        f"<tr><td>{dest}</td><td>{fmt_trend(trend)}</td></tr>"
        for dest, trend in sorted(digest.trends.items())
    ) or '<tr><td colspan="2">Aucune donnee</td></tr>'

    html = f"""\
<html>
  <body style="font-family: sans-serif;">
    <h2>Recap veille de vols - {today_iso}</h2>
    <h3>Prix le plus bas observe par destination</h3>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
      <tr><th>Destination</th><th>Prix</th><th>Date de depart</th><th>Vu le</th></tr>
      {rows_lowest}
    </table>
    <h3>Prix le plus bas par mois de depart</h3>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
      <tr><th>Destination</th><th>Mois</th><th>Prix</th><th>Date de depart</th></tr>
      {rows_month}
    </table>
    <h3>Tendance sur les {14} derniers jours</h3>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
      <tr><th>Destination</th><th>Evolution</th></tr>
      {rows_trend}
    </table>
  </body>
</html>
"""
    return subject, html
