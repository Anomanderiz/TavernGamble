from shiny import App, ui, render, reactive
from datetime import datetime
import random

# --- Game constants from your prompt ---
LOSS_CHANCE = 0.10          # 10% chance to suffer a loss
LOSS_PERCENTAGE = -10       # -10% result when loss happens
MIN_PROFIT_PERCENT = 20     # 20% minimum profit
MAX_PROFIT_PERCENT = 200    # 200% maximum profit


# --- UI ---

app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.title("The Gilded Tankard — Tavern Manager"),
        ui.tags.link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Spectral:wght@400;600&display=swap",
        ),
        ui.tags.style(
            """
            body {
              background: radial-gradient(circle at top, #1f2937 0, #020617 55%);
              color: #fef3c7;
              min-height: 100vh;
            }

            .app-wrapper {
              max-width: 1100px;
              margin: 0 auto 2rem auto;
              padding: 0 1rem 2rem 1rem;
            }

            .app-header {
              background: rgba(15,23,42,0.92);
              border-bottom: 1px solid rgba(251,191,36,0.45);
              box-shadow: 0 15px 35px rgba(0,0,0,0.85);
              padding: 1.1rem 1.5rem;
              position: sticky;
              top: 0;
              z-index: 10;
              backdrop-filter: blur(14px);
            }

            .app-header-inner {
              display: flex;
              justify-content: space-between;
              align-items: center;
              max-width: 1100px;
              margin: 0 auto;
            }

            .app-title-block {
              display: flex;
              flex-direction: column;
            }

            .app-title {
              font-family: 'Cinzel Decorative', serif;
              font-size: 2rem;
              letter-spacing: 0.18em;
              text-transform: uppercase;
              color: #fbbf24;
              text-shadow: 0 0 18px rgba(251,191,36,0.6);
            }

            .app-subtitle {
              font-family: 'Spectral', serif;
              color: #fde68a;
              font-size: 0.9rem;
              text-transform: uppercase;
              letter-spacing: 0.25em;
              margin-top: 0.2rem;
            }

            .app-tagline {
              font-family: 'Spectral', serif;
              color: #fef3c7;
              font-style: italic;
              font-size: 0.95rem;
            }

            .glass-panel {
              background: rgba(15,23,42,0.88);
              border-radius: 18px;
              border: 1px solid rgba(251,191,36,0.28);
              box-shadow: 0 0 30px rgba(0,0,0,0.9);
              padding: 1.25rem 1.5rem;
              margin-bottom: 1rem;
              backdrop-filter: blur(12px);
            }

            h3 {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              color: #fde68a;
              font-size: 1.1rem;
              margin-top: 0;
              margin-bottom: 0.75rem;
            }

            .spin-button {
              font-family: 'Cinzel Decorative', serif;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              font-weight: 700;
            }

            .spin-button.btn {
              background: linear-gradient(135deg, #fbbf24, #f97316);
              border: 1px solid #facc15;
              color: #1f2937;
              box-shadow: 0 0 18px rgba(251,191,36,0.6);
            }

            .spin-button.btn:hover {
              filter: brightness(1.05);
              box-shadow: 0 0 24px rgba(251,191,36,0.9);
            }

            .wheel-wrapper {
              position: relative;
              display: flex;
              justify-content: center;
              align-items: center;
              margin-top: 0.75rem;
              margin-bottom: 0.75rem;
            }

            .wheel {
              width: 260px;
              height: 260px;
              border-radius: 50%;
              border: 6px solid #facc15;
              box-shadow: 0 0 32px rgba(0,0,0,0.9);
              /* Red loss slice is 10% of the circle */
              background-image: conic-gradient(
                #7f1d1d 0deg 36deg,      /* 10% loss sector */
                #f97316 36deg 140deg,
                #fbbf24 140deg 240deg,
                #22c55e 240deg 360deg
              );
              transition: transform 4s cubic-bezier(0.22, 0.61, 0.36, 1);
              position: relative;
              overflow: hidden;
            }

            .wheel::after {
              content: '';
              position: absolute;
              inset: 18%;
              border-radius: 50%;
              background: radial-gradient(circle at 30% 0%, rgba(255,255,255,0.18), transparent 55%);
              mix-blend-mode: screen;
            }

            .wheel-pointer {
              position: absolute;
              top: -4px;
              left: 50%;
              transform: translateX(-50%);
              width: 0;
              height: 0;
              border-left: 12px solid transparent;
              border-right: 12px solid transparent;
              border-bottom: 22px solid #fbbf24;
              filter: drop-shadow(0 4px 6px rgba(0,0,0,0.8));
            }

            .wheel-center-button {
              position: absolute;
              width: 110px;
              height: 110px;
              border-radius: 50%;
              border: 2px solid rgba(15,23,42,0.85);
              background: radial-gradient(circle at 30% 0%, #fef3c7, #fbbf24);
              display: flex;
              align-items: center;
              justify-content: center;
              cursor: pointer;
              font-family: 'Cinzel Decorative', serif;
              font-size: 0.8rem;
              text-transform: uppercase;
              letter-spacing: 0.14em;
              color: #1f2937;
              text-align: center;
              box-shadow: 0 0 16px rgba(0,0,0,0.9);
            }

            .wheel-center-button:hover {
              filter: brightness(1.05);
            }

            .status-text {
              margin-top: 0.5rem;
              font-family: 'Spectral', serif;
              font-size: 0.9rem;
              color: #e5e7eb;
            }

            .result-grid {
              display: flex;
              flex-direction: column;
              gap: 0.4rem;
              margin-top: 0.75rem;
              font-family: 'Spectral', serif;
            }

            .result-row {
              display: flex;
              justify-content: space-between;
              font-size: 0.95rem;
            }

            .result-row span:last-child {
              font-weight: 600;
            }

            .result-total span:last-child {
              color: #fbbf24;
              font-size: 1rem;
            }

            table {
              font-size: 0.85rem;
            }

            th {
              background-color: rgba(31,41,55,0.85) !important;
              color: #fde68a !important;
            }
            """
        ),
    ),

    ui.div(
        {"class": "app-header"},
        ui.div(
            {"class": "app-header-inner"},
            ui.div(
                {"class": "app-title-block"},
                ui.span("The Gilded Tankard", class_="app-title"),
                ui.span("Tavern Management Ledger", class_="app-subtitle"),
            ),
            ui.div("May fortune flavour your brew.", class_="app-tagline"),
        ),
    ),

    ui.div(
        {"class": "app-wrapper"},

        ui.row(
            # Investment + flair
            ui.column(
                4,
                ui.div(
                    {"class": "glass-panel"},
                    ui.h3("Investment"),
                    ui.input_numeric(
                        "investment",
                        "Gold invested this tenday (gp)",
                        value=100,
                        min=0,
                        step=10,
                    ),
                    ui.help_text(
                        "* Investment is optional – set to 0 if you just want to see the percentage."
                    ),
                ),
                ui.div(
                    {"class": "glass-panel"},
                    ui.h3("Narrative flair"),
                    ui.p("How richly did you describe the tavern's ambience and drama?"),
                    ui.input_radio_buttons(
                        "flair",
                        None,
                        choices={
                            "Passable (+5%)": "5",
                            "Good (+10%)": "10",
                            "Excellent (+15%)": "15",
                        },
                        selected="5",
                    ),
                ),
            ),

            # Wheel of Fortune
            ui.column(
                4,
                ui.div(
                    {"class": "glass-panel"},
                    ui.h3("Wheel of Fortune"),
                    ui.div(
                        {"class": "wheel-wrapper"},
                        ui.div({"class": "wheel-pointer"}),
                        ui.output_ui("wheel_ui"),
                        ui.input_action_button(
                            "spin",
                            "Spin",
                            class_="wheel-center-button",
                        ),
                    ),
                    ui.div({"class": "status-text"}, ui.output_text("status")),
                ),
            ),

            # Earnings summary
            ui.column(
                4,
                ui.div(
                    {"class": "glass-panel"},
                    ui.h3("Earnings"),
                    ui.output_table("latest_summary"),
                ),
            ),
        ),

        ui.br(),

        # Ledger
        ui.div(
            {"class": "glass-panel"},
            ui.h3("Tavern ledger"),
            ui.output_table("ledger_table"),
        ),
    ),
)


# --- Server ---

def server(input, output, session):
    # Rotation of wheel (degrees)
    rotation = reactive.value(0.0)
    # Last spin result (dict) or None
    last_result = reactive.value(None)
    # Ledger as list of dicts, newest first
    ledger = reactive.value([])

    @reactive.effect
    @reactive.event(input.spin)
    def _spin_wheel():
        investment = input.investment() or 0.0
        # narrative flair %
        flair_pct = int(input.flair() or "0")

        # Decide loss vs profit
        is_loss = random.random() < LOSS_CHANCE
        loss_degrees = 360 * LOSS_CHANCE
        profit_degrees = 360 - loss_degrees

        if is_loss:
            # Fixed -10% result
            result_pct = LOSS_PERCENTAGE
            # Choose a target gradient angle within the red slice (0–loss_degrees)
            margin = 2
            target_angle = margin + random.random() * (loss_degrees - 2 * margin)
        else:
            # Uniform continuum from 20–200%
            u = random.random()
            result_pct = MIN_PROFIT_PERCENT + u * (MAX_PROFIT_PERCENT - MIN_PROFIT_PERCENT)
            # Map that uniformly across the non-loss arc
            target_angle = loss_degrees + u * profit_degrees

        # Pointer is at "top" (90deg in gradient coordinates).
        # Rotate wheel so that target_angle is under the pointer.
        extra_spins = 360 * random.randint(4, 7)
        final_rot = rotation() + extra_spins + (90 - target_angle)
        rotation.set(final_rot)

        # Earnings:
        # base final = invested + profit from wheel %
        base_final = investment * (1 + result_pct / 100.0)
        # Flair multiplies that final amount
        final_with_flair = base_final * (1 + flair_pct / 100.0)
        total_profit = final_with_flair - investment

        res = {
            "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Investment (gp)": round(investment, 1),
            "Wheel %": round(result_pct, 1),
            "Flair %": flair_pct,
            "Total profit (gp)": round(total_profit, 1),
            "Final amount (gp)": round(final_with_flair, 1),
        }

        last_result.set(res)
        ledger.set([res] + ledger())

        # Flavour text
        if is_loss:
            title = "Loss this tenday."
            flavour = "The dice were cold and the patrons colder – the house takes its due."
        elif result_pct >= 150:
            title = "An outrageous success!"
            flavour = "The taproom shook with song and coin. The city will speak of it for weeks."
        else:
            title = "A respectable haul."
            flavour = "Not legendary, but solid coin in the coffer and smiles on weary faces."

        modal = ui.modal(
            ui.p(flavour),
            ui.hr(),
            ui.div(
                {"class": "result-grid"},
                ui.div(
                    {"class": "result-row"},
                    ui.span("Wheel result:"),
                    ui.span(f"{res['Wheel %']:.1f}%"),
                ),
                ui.div(
                    {"class": "result-row"},
                    ui.span("Narrative flair:"),
                    ui.span(f"+{flair_pct}%"),
                ),
                ui.div(
                    {"class": "result-row"},
                    ui.span("Total profit:"),
                    ui.span(f"{res['Total profit (gp)']:.1f} gp"),
                ),
                ui.div(
                    {"class": "result-row result-total"},
                    ui.span("Final amount:"),
                    ui.span(f"{res['Final amount (gp)']:.1f} gp"),
                ),
            ),
            title=title,
            easy_close=True,
            footer=ui.modal_button("Close"),
        )
        ui.modal_show(modal)

    # Wheel UI – just the spinning disc
    @render.ui
    def wheel_ui():
        return ui.div(
            {"class": "wheel", "style": f"transform: rotate({rotation()}deg);"},
        )

    # One-line status under the wheel
    @render.text
    def status():
        res = last_result()
        if res is None:
            return "Spin the wheel to see how this tenday's trade went."

        pct = res["Wheel %"]
        profit = res["Total profit (gp)"]
        flair_pct = res["Flair %"]

        if pct < 0:
            return (
                f"Loss of {pct:.1f}% — down roughly {abs(profit):.1f} gp, "
                f"even with {flair_pct}% narrative flair."
            )
        else:
            return (
                f"Gain of {pct:.1f}% — up about {profit:.1f} gp "
                f"after a {flair_pct}% flair bonus."
            )

    # Latest result table (1 row)
    @render.table
    def latest_summary():
        res = last_result()
        if res is None:
            return []
        return [res]

    # Full ledger table
    @render.table
    def ledger_table():
        rows = ledger()
        if not rows:
            return []
        return rows


app = App(app_ui, server)
