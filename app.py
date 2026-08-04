"""
app.py
──────
PaintQuote Pro — Flask application entry point.
Run with:  python app.py
"""

import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import logging
import os
import json
import uuid
from datetime import datetime

from flask import (
    Flask, render_template, request, jsonify,
    send_file, redirect, url_for, flash
)

# ── Bootstrap config first (loads .env) ───────────────────────────────────────
import config
config.print_startup_banner()

from database import (
    init_db, create_quote, get_quote, get_all_quotes,
    add_chat_message, get_chat_history, update_chat_message_status,
    add_to_approval_queue, get_pending_approvals, get_all_approvals,
    resolve_approval, get_approval_by_id, get_approval_by_token
)
from calculator      import calculate_quote
from negotiator      import negotiate_response
from pdf_generator   import generate_quote_pdf
from email_notifier  import send_approval_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

init_db()

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

# ── Helper ────────────────────────────────────────────────────────────────────

def _pending_approvals_count() -> int:
    try:
        return sum(1 for a in get_all_approvals() if a["status"] == "pending")
    except Exception:
        return 0


# ── Page routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html",
                           pending_count=_pending_approvals_count())


@app.route("/dashboard")
def dashboard():
    quotes = get_all_quotes()
    approvals = get_all_approvals()
    pending_approval_count = sum(1 for a in approvals if a["status"] == "pending")
    approved_count = sum(1 for a in approvals if a["status"] == "approved")
    total_value = sum(q.get("total_cost", 0) for q in quotes)
    return render_template(
        "dashboard.html",
        quotes=quotes,
        pending_approval_count=pending_approval_count,
        approved_count=approved_count,
        total_value=total_value,
        pending_count=_pending_approvals_count()
    )


@app.route("/quote/<int:quote_id>")
def view_quote(quote_id):
    quote = get_quote(quote_id)
    if not quote:
        return render_template("404.html"), 404
    chat_history   = get_chat_history(quote_id)
    quote_breakdown = json.loads(quote.get("breakdown", "{}"))
    rooms_data     = json.loads(quote.get("rooms", "[]"))
    return render_template(
        "quote_detail.html",
        quote=quote,
        chat_history=chat_history,
        quote_breakdown=quote_breakdown,
        rooms_data=rooms_data,
        pending_count=_pending_approvals_count()
    )


@app.route("/approval-queue")
@app.route("/approval_queue")       # keep old URL working
def approval_queue():
    approvals    = get_all_approvals()
    pending_count = sum(1 for a in approvals if a["status"] == "pending")
    return render_template(
        "approval_queue.html",
        approvals=approvals,
        pending_count=pending_count
    )


@app.route("/email-approved")
def email_approved():
    approval_id = request.args.get("id", "")
    return render_template("email_approved.html", approval_id=approval_id,
                           pending_count=_pending_approvals_count())


# ── API: Calculate & Save Quote ───────────────────────────────────────────────

@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    client_name = data.get("client_name", "").strip()
    if not client_name:
        return jsonify({"error": "Client name is required"}), 400

    rooms      = data.get("rooms", [])
    paint_grade = data.get("paint_grade", "premium")
    extras     = data.get("extras", {})

    if not rooms:
        return jsonify({"error": "At least one room is required"}), 400

    try:
        result = calculate_quote(rooms, paint_grade, extras)
        result.update({
            "client_name": client_name,
            "paint_grade": paint_grade,
            "extras":      extras,
            "rooms":       rooms,
            "created_at":  datetime.now().isoformat(),
        })
        quote_id = create_quote(result)
        result["id"] = quote_id
    except Exception as exc:
        logger.error("Calculator/DB error: %s", exc)
        return jsonify({"error": str(exc)}), 500

    logger.info(f"Quote #{quote_id} created for {client_name} — ₹{result['total_cost']:,.0f}")
    return jsonify(result)


# ── API: Chat / Negotiate ─────────────────────────────────────────────────────

@app.route("/api/negotiate", methods=["POST"])
def api_negotiate():
    try:
        data = request.get_json(force=True)
        quote_id       = data.get("quote_id")
        client_message = data.get("message", "").strip()

        if not client_message:
            return jsonify({"error": "Empty message"}), 400

        quote = get_quote(quote_id)
        if not quote:
            return jsonify({"error": "Quote not found"}), 404

        chat_history = get_chat_history(quote_id)

        # Save client message immediately
        add_chat_message(quote_id, "client", client_message)

        # Get AI/rule response
        response = negotiate_response(quote, client_message, chat_history)
        requires_approval = response.get("requires_approval", False)

        if requires_approval:
            secure_token = str(uuid.uuid4())

            msg_id = add_chat_message(
                quote_id, "agent",
                response["reply"],
                response.get("suggested_price"),
                response.get("action"),
                approval_status="pending"
            )

            aq_id = add_to_approval_queue(
                quote_id=quote_id,
                chat_message_id=msg_id,
                client_message=client_message,
                ai_suggested_reply=response["reply"],
                suggested_price=response.get("suggested_price"),
                trade_off=response.get("trade_off", ""),
                secure_token=secure_token
            )

            email_ok, email_err = send_approval_email(
                quote=quote,
                client_message=client_message,
                ai_reply=response["reply"],
                suggested_price=response.get("suggested_price"),
                trade_off=response.get("trade_off", ""),
                approval_id=aq_id,
                secure_token=secure_token
            )

            return jsonify({
                "status":           "pending_approval",
                "message":          "Your message has been received. The contractor will review and respond shortly.",
                "requires_approval": True,
                "email_sent":       email_ok,
                "email_error":      email_err if not email_ok else "",
                "approval_id":      aq_id,
            })

        else:
            add_chat_message(
                quote_id, "agent",
                response["reply"],
                response.get("suggested_price"),
                response.get("action"),
                approval_status="sent"
            )
            return jsonify({
                "status":           "sent",
                "reply":            response["reply"],
                "suggested_price":  response.get("suggested_price"),
                "action":           response.get("action"),
                "trade_off":        response.get("trade_off", ""),
                "requires_approval": False,
            })
    except Exception as exc:
        logger.exception("Error in /api/negotiate:")
        return jsonify({"error": str(exc)}), 500


# ── API: In-App Approval Actions ──────────────────────────────────────────────

@app.route("/api/approve_message", methods=["POST"])
def api_approve_message():
    try:
        data       = request.get_json(force=True)
        aq_id      = data.get("approval_id")
        dad_response = data.get("dad_response", "").strip()

        aq = get_approval_by_id(aq_id)
        if not aq:
            return jsonify({"error": "Not found"}), 404
        if aq["status"] != "pending":
            return jsonify({"error": "Already resolved"}), 400

        final_reply = dad_response if dad_response else aq["ai_suggested_reply"]
        update_chat_message_status(aq["chat_message_id"], "sent", final_reply)
        resolve_approval(aq_id, "approved", dad_response)

        return jsonify({"status": "approved", "reply": final_reply})
    except Exception as exc:
        logger.exception("Error in /api/approve_message:")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/reject_message", methods=["POST"])
def api_reject_message():
    try:
        data       = request.get_json(force=True)
        aq_id      = data.get("approval_id")
        dad_response = data.get("dad_response", "").strip()

        aq = get_approval_by_id(aq_id)
        if not aq:
            return jsonify({"error": "Not found"}), 404
        if aq["status"] != "pending":
            return jsonify({"error": "Already resolved"}), 400

        update_chat_message_status(aq["chat_message_id"], "rejected")

        if dad_response:
            add_chat_message(aq["quote_id"], "agent", dad_response,
                             approval_status="sent")

        resolve_approval(aq_id, "rejected", dad_response)
        return jsonify({"status": "rejected"})
    except Exception as exc:
        logger.exception("Error in /api/reject_message:")
        return jsonify({"error": str(exc)}), 500


# ── API: Email-Based Approval (via links in email) ────────────────────────────

@app.route("/api/email-approve/<int:approval_id>")
def api_email_approve(approval_id):
    """Dad clicks 'Approve' button in email."""
    token = request.args.get("token", "")
    aq    = get_approval_by_token(token)

    if not aq or aq["id"] != approval_id:
        return render_template("email_action_error.html",
                               error="Invalid or expired approval link."), 403

    if aq["status"] != "pending":
        # Already resolved — still redirect to success so Dad isn't confused
        return redirect(url_for("email_approved", id=approval_id))

    # Approve using the AI reply
    final_reply = aq["ai_suggested_reply"]
    update_chat_message_status(aq["chat_message_id"], "sent", final_reply)
    resolve_approval(approval_id, "approved", "")

    logger.info("Email approval: AQ #%d approved by Dad", approval_id)
    return redirect(url_for("email_approved", id=approval_id))


@app.route("/api/email-reject/<int:approval_id>", methods=["GET"])
def api_email_reject_form(approval_id):
    """Dad clicks 'Reject' button in email — show a form."""
    token = request.args.get("token", "")
    aq    = get_approval_by_token(token)

    if not aq or aq["id"] != approval_id:
        return render_template("email_action_error.html",
                               error="Invalid or expired rejection link."), 403

    if aq["status"] != "pending":
        return render_template("email_action_error.html",
                               error="This request has already been resolved."), 400

    # Fetch the associated quote for display
    quote = get_quote(aq["quote_id"])
    return render_template(
        "email_reject_form.html",
        aq=aq,
        quote=quote,
        token=token
    )


@app.route("/api/email-reject/<int:approval_id>", methods=["POST"])
def api_email_reject_submit(approval_id):
    """Dad submits his custom response after rejecting."""
    token = request.form.get("token", "")
    aq    = get_approval_by_token(token)

    if not aq or aq["id"] != approval_id:
        return render_template("email_action_error.html",
                               error="Invalid or expired link."), 403

    if aq["status"] != "pending":
        return render_template("email_action_error.html",
                               error="Already resolved."), 400

    dad_response = request.form.get("dad_response", "").strip()

    update_chat_message_status(aq["chat_message_id"], "rejected")
    if dad_response:
        add_chat_message(aq["quote_id"], "agent", dad_response,
                         approval_status="sent")
    resolve_approval(approval_id, "rejected", dad_response)

    logger.info("Email rejection: AQ #%d rejected by Dad", approval_id)
    return render_template("email_reject_success.html", quote_id=aq["quote_id"])


# ── API: Chat History & Quotes ────────────────────────────────────────────────

@app.route("/api/chat_history/<int:quote_id>")
def api_chat_history(quote_id):
    """Returns only messages visible to the client (sent ones)."""
    history = get_chat_history(quote_id)
    visible = [
        msg for msg in history
        if msg["role"] == "client" or msg.get("approval_status") == "sent"
    ]
    return jsonify(visible)


@app.route("/api/quote/<int:quote_id>/pdf")
def api_pdf(quote_id):
    quote = get_quote(quote_id)
    if not quote:
        return "Quote not found", 404
    try:
        pdf_path = generate_quote_pdf(quote)
        return send_file(pdf_path, as_attachment=True,
                         download_name=f"PaintQuote_{quote_id}_{quote.get('client_name','').replace(' ','_')}.pdf")
    except Exception as exc:
        logger.error("PDF generation error: %s", exc)
        return f"PDF generation failed: {exc}", 500


@app.route("/api/quotes")
def api_quotes():
    return jsonify(get_all_quotes())


@app.route("/api/approvals")
def api_approvals():
    return jsonify(get_all_approvals())


# ── Error pages ───────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=config.DEBUG, port=5000, host="0.0.0.0")
