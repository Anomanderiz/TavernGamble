from shiny import App, ui, render, reactive
from datetime import datetime
import random
import pandas as pd
from pathlib import Path

# --- Game constants ---
LOSS_CHANCE = 0.10          # 10% chance to suffer a loss
LOSS_PERCENTAGE = -10       # -10% result when loss happens
MIN_PROFIT_PERCENT = 20     # 20% minimum profit
MAX_PROFIT_PERCENT = 200    # 200% maximum profit


# ========================= UI =========================

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.title("The Gilded Tankard — Tavern Management System"),
        ui.tags.link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Spectral:wght@400;600&display=swap",
        ),
        # JS handler to rotate the wheel image
        ui.tags.script(
            """
            document.addEventListener('DOMContentLoaded', function() {
              if (window.Shiny) {
                Shiny.addCustomMessageHandler('spin_wheel', function(message) {
                  var el = document.getElementById('wheel-disc');
                  if (!el) return;
                  el.style.transform = 'translate(-50%, -50%) rotate(' + message.angle + 'deg)';
                });
              }
            });
            """
        ),
        ui.tags.style(
            """
            body {
              background: radial-gradient(circle at top, #262321 0, #0f0d0b 55%);
              color: #fce7b2;
              min-height: 100vh;
            }

            ::selection {
              background: #f97316;
              color: #ffffff;
            }
            ::-moz-selection {
              background: #f97316;
              color: #ffffff;
            }

            .app-shell {
              max-width: 1200px;
              margin: 0 auto 2rem auto;
              padding: 0 1.5rem 2rem 1.5rem;
            }

            /* ---------- HEADER ---------- */

            .app-header {
              background: #171311;
              border-bottom: 1px solid #5a3c18;
              box-shadow: 0 10px 30px rgba(0,0,0,0.8);
              padding: 0.8rem 0;
              margin-bottom: 1.5rem;
            }

            .app-header-inner {
              max-width: 1200px;
              margin: 0 auto;
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 0 1.5rem;
            }

            .brand-block {
              display: flex;
              align-items: center;
              gap: 0.75rem;
            }

            .brand-icon {
              width: 34px;
              height: 34px;
              border-radius: 50%;
              border: 2px solid #f5b63a;
              display: flex;
              align-items: center;
              justify-content: center;
              background: radial-gradient(circle at 30% 0%, #ffeeca, #f6b53b);
              box-shadow: 0 0 14px rgba(0,0,0,0.9);
              font-size: 1.1rem;
            }

            .brand-text-main {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.18em;
              font-size: 1.1rem;
              color: #f4d191;
            }

            .brand-text-sub {
              font-family: 'Spectral', serif;
              font-size: 0.8rem;
              letter-spacing: 0.18em;
              text-transform: uppercase;
              color: #d0a45c;
            }

            .header-tagline {
              font-family: 'Spectral', serif;
              text-transform: uppercase;
              letter-spacing: 0.16em;
              font-size: 0.75rem;
              color: #f9d474;
            }

            /* ---------- PANELS ---------- */

            .main-grid {
              display: grid;
              grid-template-columns: 1.1fr 1.7fr;
              gap: 1.5rem;
            }

            .left-stack {
              display: flex;
              flex-direction: column;
              gap: 1.2rem;
            }

            .glass-panel {
              background: radial-gradient(circle at top, #211b16 0, #14100e 65%);
              border-radius: 12px;
              border: 1px solid #6b4a20;
              box-shadow: 0 14px 32px rgba(0,0,0,0.9);
              padding: 1.1rem 1.2rem;
            }

            .panel-header {
              display: flex;
              align-items: center;
              gap: 0.55rem;
              margin-bottom: 0.9rem;
            }

            .panel-glyph {
              width: 24px;
              height: 24px;
              border-radius: 50%;
              border: 1px solid #f5b63a;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 0.9rem;
              background: radial-gradient(circle at 30% 0%, #fef3d0, #f4b337);
              color: #43230b;
            }

            .panel-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.18em;
              font-size: 0.86rem;
              color: #f8e0a8;
            }

            .panel-caption {
              font-family: 'Spectral', serif;
              font-size: 0.78rem;
              color: #d6b47a;
            }

            .field-label {
              font-family: 'Spectral', serif;
              font-size: 0.82rem;
              margin-bottom: 0.25rem;
              color: #fdf3cd;
            }

            .help-text {
              font-family: 'Spectral', serif;
              font-size: 0.75rem;
              color: #ffffff !important;
              margin-top: 0.25rem;
            }

            .form-control {
              background-color: #16120f;
              border-radius: 8px;
              border: 1px solid #4c3620;
              color: #fce7b2;
            }

            .form-control:focus {
              border-color: #f1b13b;
              box-shadow: 0 0 0 1px #f1b13b;
            }

            /* ---------- NARRATIVE FLAIR RADIO ---------- */

            .shiny-input-radiogroup {
              margin-top: 0.5rem;
            }

            .shiny-input-radiogroup .radio {
              margin-bottom: 0.4rem;
            }

            .shiny-input-radiogroup label {
              width: 100%;
              display: flex;
              align-items: center;
              gap: 0.5rem;
              padding: 0.55rem 0.75rem;
              border-radius: 10px;
              background: #18100d;
              border: 1px solid #5f4020;
              color: #fef3d5;
              font-family: 'Spectral', serif;
              font-size: 0.84rem;
              cursor: pointer;
              justify-content: center;
              text-align: center;
            }

            .shiny-input-radiogroup label:hover {
              border-color: #f59e0b;
            }

            .shiny-input-radiogroup input[type="radio"] {
              margin-right: 0.45rem;
            }

            /* ---------- WHEEL ---------- */

            .wheel-panel {
              padding: 1.1rem 1.3rem 1.2rem 1.3rem;
            }

            .wheel-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.2em;
              font-size: 0.9rem;
              text-align: center;
              margin-bottom: 0.8rem;
              color: #f9dfaa;
            }

            .wheel-shell {
              background: radial-gradient(circle at center, rgba(255,208,120,0.22), transparent 60%);
              border-radius: 14px;
              padding: 1.0rem 1.0rem 0.9rem 1.0rem;
              border: 1px solid #6b4a20;
            }

            .wheel-wrapper {
              position: relative;
              width: 500;
              height: 600;
              margin: 0.3rem auto 0.2rem auto;
              display: flex;
              justify-content: center;
              align-items: center;
            }

            .wheel-halo {
              position: absolute;
              width: 360px;
              height: 360px;
              border-radius: 50%;
              background: radial-gradient(circle at center, rgba(255,203,120,0.25), transparent 60%);
              filter: blur(4px);
            }

            /* Image wheel */
            .wheel {
              position: absolute;
              top: 50%;
              left: 50%;
              width: 280px;                 /* tweak up/down if you want it bigger/smaller */
              height: 280px;
              transform-origin: 50% 50%;
              transform: translate(-50%, -50%) rotate(0deg);
              transition: transform 4s cubic-bezier(0.22, 0.61, 0.36, 1);
              border: none;                 /* no extra ring – the PNG *is* the wheel */
              border-radius: 50%;
              box-shadow: 0 0 32px rgba(0,0,0,0.9);
            }

            .wheel-pointer,
            .wheel-pointer-pin {
              z-index: 5;
            }

            .wheel-pointer {
              position: absolute;
              top: -3px;
              left: 50%;
              transform: translateX(-50%);
              width: 0;
              height: 0;
              border-left: 10px solid transparent;
              border-right: 10px solid transparent;
              border-bottom: 22px solid #fef3c7;
              filter: drop-shadow(0 3px 6px rgba(0,0,0,0.9));
            }

            .wheel-pointer-pin {
              position: absolute;
              top: 16px;
              left: 50%;
              transform: translateX(-50%);
              width: 11px;
              height: 11px;
              border-radius: 50%;
              border: 2px solid #4b2c08;
              background: radial-gradient(circle at 30% 0%, #fef3c7, #fbbf24);
            }

            .wheel-center-button {
              position: absolute;
              width: 110px;
              height: 110px;
              border-radius: 50%;
              border: 2px solid rgba(68,41,13,0.9);
              background: radial-gradient(circle at 30% 0%, #fff5d1, #f5b037);
              display: flex;
              align-items: center;
              justify-content: center;
              cursor: pointer;
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.16em;
              font-size: 0.7rem;
              color: #3a2410;
              text-align: center;
              box-shadow: 0 0 20px rgba(0,0,0,1);
              z-index: 6;
            }

            .wheel-center-button:hover {
              filter: brightness(1.05);
            }

            .wheel-center-button.btn {
              border: none;
              background: transparent;
              box-shadow: none;
            }

            .wheel-center-text {
              line-height: 1.4;
            }

            .loss-warning {
              font-family: 'Spectral', serif;
              text-align: center;
              font-size: 0.78rem;
              color: #fda4af;
              margin-top: 0.4rem;
            }

            .status-text {
              margin-top: 0.45rem;
              font-family: 'Spectral', serif;
              font-size: 0.85rem;
              color: #fef3c7;
              text-align: center;
            }

            /* ---------- TABLES ---------- */

            table {
              font-size: 0.8rem;
              font-family: 'Spectral', serif;
              background-color: #18100d;
              color: #ffffff;
            }

            table thead tr th {
              background-color: #1a130f !important;
              color: #f9deb1 !important;
              border-bottom: 1px solid #46301a !important;
            }

            table tbody tr td {
              background-color: #18100d !important;
              border-color: #3b2816 !important;
              color: #ffffff !important;
            }

            .table-striped > tbody > tr:nth-of-type(odd) > td {
              background-color: #201612 !important;
            }

            .ledger-footer-text {
              font-family: 'Spectral', serif;
              font-size: 0.78rem;
              color: #b89c6f;
              margin-top: 0.3rem;
              text-align: center;
              font-style: italic;
            }

            .section-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.18em;
              font-size: 0.86rem;
              margin-bottom: 0.8rem;
              color: #f9dfaa;
            }

            /* ---------- MODAL ---------- */

            .modal-content {
              border-radius: 14px;
              border: 1px solid #f59e0b;
              background: radial-gradient(circle at top, #201713 0, #120e0c 65%);
              box-shadow: 0 18px 45px rgba(0,0,0,0.95);
            }

            .modal-header {
              border-bottom: none;
              padding-bottom: 0;
            }

            .modal-body {
              padding-top: 0;
            }

            .results-modal {
              font-family: 'Spectral', serif;
              color: #fef3d5;
            }

            .results-title {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.18em;
              font-size: 1.0rem;
              text-align: center;
              margin-bottom: 0.25rem;
              color: #fde68a;
            }

            .results-subtitle {
              font-size: 0.78rem;
              text-align: center;
              margin-bottom: 0.75rem;
              color: #facc85;
            }

            .results-warning {
              width: 40px;
              height: 40px;
              border-radius: 50%;
              border: 2px solid #f97316;
              display: flex;
              align-items: center;
              justify-content: center;
              color: #fed7aa;
              margin: 0 auto 0.5rem auto;
              font-size: 1.2rem;
            }

            .results-row {
              display: flex;
              justify-content: space-between;
              font-size: 0.86rem;
              margin-bottom: 0.25rem;
            }

            .results-label {
              color: #fef3d5;
            }

            .results-value {
              font-weight: 600;
            }

            .results-muted {
              font-size: 0.78rem;
              color: #a3a3c2;
              text-align: right;
            }

            .results-divider {
              border-bottom: 1px solid #31201a;
              margin: 0.6rem 0 0.6rem 0;
            }

            .results-netbox {
              margin-top: 0.4rem;
              padding: 0.65rem 0.75rem;
              border-radius: 10px;
              border: 1px solid #5f4020;
              background: radial-gradient(circle at top, #241812 0, #18100d 70%);
            }

            .results-net-label {
              font-size: 0.75rem;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              color: #f97316;
            }

            .results-net-value {
              font-size: 0.95rem;
              color: #fef3d5;
            }

            .results-final-label {
              font-size: 0.78rem;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              color: #fcd34d;
            }

            .results-final-value {
              font-size: 1.05rem;
              color: #facc15;
            }

            .btn-record {
              width: 100%;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              font-family: 'Cinzel Decorative', serif;
              font-size: 0.8rem;
              border-radius: 999px;
              border: 1px solid #f97316;
              background: linear-gradient(135deg, #f97316, #f59e0b);
              color: #1f140c;
              margin-top: 0.8rem;
            }

            .btn-record:hover {
              filter: brightness(1.04);
            }
            """
        ),
    ),

    ui.div(
        {"class": "app-header"},
        ui.div(
            {"class": "app-header-inner"},
            ui.div(
                {"class": "brand-block"},
                ui.div("🍺", class_="brand-icon"),
                ui.div(
                    ui.div("THE GILDED TANKARD", class_="brand-text-main"),
                    ui.div("TAVERN MANAGEMENT SYSTEM", class_="brand-text-sub"),
                ),
            ),
            ui.div("MAY FORTUNE FLAVOUR YOUR BREW", class_="header-tagline"),
        ),
    ),

    ui.div(
        {"class": "app-shell"},
        ui.div(
            {"class": "main-grid"},
            # LEFT COLUMN
            ui.div(
                {"class": "left-stack"},
                ui.div(
                    {"class": "glass-panel"},
                    ui.div(
                        {"class": "panel-header"},
                        ui.div("🪙", class_="panel-glyph"),
                        ui.div(
                            ui.div("TREASURY INVESTMENT", class_="panel-title"),
                            ui.div("Gold Pieces (gp) to invest", class_="panel-caption"),
                        ),
                    ),
                    ui.div("Gold Pieces (gp) to invest", class_="field-label"),
                    ui.input_numeric(
                        "investment",
                        label=None,
                        value=0,
                        min=0,
                        step=10,
                    ),
                    ui.div(
                        "*Optional: Enter 0 to test fortune without gold.",
                        class_="help-text",
                    ),
                ),
                ui.div(
                    {"class": "glass-panel"},
                    ui.div(
                        {"class": "panel-header"},
                        ui.div("✨", class_="panel-glyph"),
                        ui.div(
                            ui.div("NARRATIVE FLAIR", class_="panel-title"),
                            ui.div(
                                "How well did you describe the tavern's atmosphere this tenday?",
                                class_="panel-caption",
                            ),
                        ),
                    ),
                    ui.input_radio_buttons(
                        "flair",
                        None,
                        choices={
                            "Passable: 5%": "5",
                            "Good: 10%": "10",
                            "Excellent: 15%": "15",
                        },
                        selected="5",
                    ),
                ),
            ),

            # RIGHT COLUMN – WHEEL + EARNINGS
            ui.div(
                ui.div(
                    {"class": "glass-panel wheel-panel"},
                    ui.div("WHEEL OF FORTUNE", class_="wheel-title"),
                    ui.div(
                        {"class": "wheel-shell"},
                        ui.div(
                            {"class": "wheel-wrapper"},
                            ui.div({"class": "wheel-halo"}),
                            ui.tags.img(
                                id="wheel-disc",
                                src="Wheel.png",  # served from static_assets
                                class_="wheel",
                            ),
                            ui.div({"class": "wheel-pointer"}),
                            ui.div({"class": "wheel-pointer-pin"}),
                            ui.input_action_button(
                                "spin",
                            ui.HTML("<span class='wheel-center-text'>SPIN<br>FOR GOLD</span>"),
                            class_="wheel-center-button",
                            ),
                        ),
                        ui.div("Beware the Loss sector!", class_="loss-warning"),
                    ),
                    ui.div(ui.output_text("status"), class_="status-text"),
                ),
                ui.br(),
                ui.div(
                    {"class": "glass-panel"},
                    ui.div("THE EARNINGS", class_="section-title"),
                    ui.output_table("latest_summary"),
                ),
            ),
        ),

        ui.br(),

        ui.div(
            {"class": "glass-panel"},
            ui.div("THE TAVERN LEDGER", class_="section-title"),
            ui.output_table("ledger_table"),
            ui.div(ui.output_text("ledger_message"), class_="ledger-footer-text"),
        ),
    ),
)


# ========================= SERVER =========================

def server(input, output, session):
    rotation = reactive.Value(0.0)
    last_result = reactive.Value(None)
    ledger = reactive.Value([])

    @reactive.effect
    @reactive.event(input.spin)
    def _spin_wheel():
        investment = float(input.investment() or 0.0)
        flair_pct = int(input.flair() or "0")

        # Determine loss vs profit
        is_loss = random.random() < LOSS_CHANCE
        loss_degrees = 360 * LOSS_CHANCE
        profit_degrees = 360 - loss_degrees

        if is_loss:
            result_pct = LOSS_PERCENTAGE
            margin = 2
            target_angle = margin + random.random() * (loss_degrees - 2 * margin)
        else:
            u = random.random()
            result_pct = MIN_PROFIT_PERCENT + u * (MAX_PROFIT_PERCENT - MIN_PROFIT_PERCENT)
            target_angle = loss_degrees + u * profit_degrees

        # Rotate wheel so target is under pointer (pointer is at 90°)
        extra_spins = 360 * random.randint(4, 7)
        final_rot = rotation() + extra_spins + (90 - target_angle)
        rotation.set(final_rot)
        session.send_custom_message("spin_wheel", {"angle": final_rot})

        # Earnings maths
        base_profit = investment * (result_pct / 100.0)
        base_outcome = investment + base_profit
        flair_bonus_gp = base_outcome * (flair_pct / 100.0)
        final_with_flair = base_outcome + flair_bonus_gp
        net_profit = final_with_flair - investment

        state = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "investment": investment,
            "wheel_pct": result_pct,
            "flair_pct": flair_pct,
            "base_outcome": base_outcome,
            "flair_bonus_gp": flair_bonus_gp,
            "net_profit": net_profit,
            "final_amount": final_with_flair,
        }

        last_result.set(state)
        ledger.set([state] + ledger())

        # --- Tenday Results modal ---
        sign = "+" if result_pct >= 0 else ""
        wheel_str = f"{sign}{result_pct:.1f}%"
        flair_str = f"+{flair_pct}%"

        modal_body = ui.div(
            {"class": "results-modal"},
            ui.div("!", class_="results-warning"),
            ui.div("TENDAY RESULTS", class_="results-title"),
            ui.div("The wheel has spoken!", class_="results-subtitle"),
            ui.div(
                {"class": "results-row"},
                ui.span("Initial Investment:", class_="results-label"),
                ui.span(f"{investment:.0f} gp", class_="results-value"),
            ),
            ui.div(
                {"class": "results-row"},
                ui.span("Wheel Result:", class_="results-label"),
                ui.span(wheel_str, class_="results-value"),
            ),
            ui.div(
                {"class": "results-row"},
                ui.span("Base Outcome:", class_="results-label"),
                ui.span(f"{base_outcome:.0f} gp", class_="results-value"),
            ),
            ui.div(
                {"class": "results-row"},
                ui.span("Narrative Flair Bonus:", class_="results-label"),
                ui.span(flair_str, class_="results-value"),
            ),
            ui.div(
                {"class": "results-muted"},
                f"(Added {flair_bonus_gp:.0f} gp to gross total)",
            ),
            ui.div(class_="results-divider"),
            ui.div(
                {"class": "results-netbox"},
                ui.div(
                    ui.span("NET PROFIT", class_="results-net-label"),
                    ui.span(f"{net_profit:.0f} gp", class_="results-net-value"),
                ),
                ui.div(
                    {
                        "style": (
                            "margin-top:0.35rem; "
                            "display:flex; justify-content:space-between;"
                        )
                    },
                    ui.span("FINAL AMOUNT", class_="results-final-label"),
                    ui.span(f"{final_with_flair:.0f} gp", class_="results-final-value"),
                ),
            ),
        )

        modal = ui.modal(
            modal_body,
            title=None,
            easy_close=True,
            footer=ui.modal_button("Record in Ledger", class_="btn btn-record"),
            size="m",
        )
        ui.modal_show(modal)

    # Status text
    @render.text
    def status():
        res = last_result()
        if res is None:
            return "The ledger is empty. Spin the wheel to record business."

        pct = res["wheel_pct"]
        net = res["net_profit"]
        flair_pct = res["flair_pct"]

        if pct < 0:
            return (
                f"Loss of {pct:.1f}% — down roughly {abs(net):.1f} gp, "
                f"even with {flair_pct}% narrative flair."
            )
        else:
            return (
                f"Gain of {pct:.1f}% — about {net:.1f} gp profit after a {flair_pct}% flair bonus."
            )

    # Latest spin summary
    @render.table
    def latest_summary():
        res = last_result()
        cols = [
            "Investment (gp)",
            "Fortune wheel",
            "Flair",
            "Net profit (gp)",
            "Final amount (gp)",
        ]

        if res is None:
            return pd.DataFrame(columns=cols)

        row = {
            "Investment (gp)": round(res["investment"], 1),
            "Fortune wheel": f"{res['wheel_pct']:.1f}%",
            "Flair": f"+{res['flair_pct']}%",
            "Net profit (gp)": round(res["net_profit"], 1),
            "Final amount (gp)": round(res["final_amount"], 1),
        }
        return pd.DataFrame([row], columns=cols)

    # Ledger table
    @render.table
    def ledger_table():
        rows = ledger()
        cols = [
            "Date",
            "Investment (gp)",
            "Fortune wheel",
            "Flair",
            "Net profit (gp)",
            "Final amount (gp)",
        ]

        if not rows:
            return pd.DataFrame(columns=cols)

        display_rows = [
            {
                "Date": r["date"],
                "Investment (gp)": round(r["investment"], 1),
                "Fortune wheel": f"{r['wheel_pct']:.1f}%",
                "Flair": f"+{r['flair_pct']}%",
                "Net profit (gp)": round(r["net_profit"], 1),
                "Final amount (gp)": round(r["final_amount"], 1),
            }
            for r in rows
        ]
        return pd.DataFrame(display_rows, columns=cols)

    # Ledger footer
    @render.text
    def ledger_message():
        if not ledger():
            return "The ledger is empty. Spin the wheel to record business."
        return ""


assets_dir = Path(__file__).parent / "assets"
app = App(app_ui, server, static_assets=assets_dir)

