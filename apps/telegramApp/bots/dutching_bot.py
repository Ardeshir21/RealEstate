from typing import Optional, Dict, Any

import html
import logging
from django.conf import settings

import pulp

from .base import TelegramBot
from ..models import UserState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------
STATE_AWAITING_TOTAL_BET = "DUTCHING_AWAITING_TOTAL_BET"
STATE_AWAITING_NUM_ODDS  = "DUTCHING_AWAITING_NUM_ODDS"
STATE_AWAITING_ODDS_LIST = "DUTCHING_AWAITING_ODDS_LIST"

# Pool of realistic example odds used to generate copy-paste templates
_EXAMPLE_ODDS = [2.3, 3.1, 4.5, 5.0, 6.5, 7.2, 8.0, 9.5, 11.0, 13.0]

# ---------------------------------------------------------------------------
# Inline keyboard helpers
# ---------------------------------------------------------------------------
def _cancel_kb():
    """Single ❌ Cancel button."""
    return {"inline_keyboard": [[{"text": "❌ Cancel", "callback_data": "dutching_cancel"}]]}

def _start_kb():
    """🎰 Start Wizard button."""
    return {"inline_keyboard": [[{"text": "🎰 Start Wizard", "callback_data": "dutching_start"}]]}

def _new_calc_kb():
    """Button shown after a result to start a new calculation."""
    return {"inline_keyboard": [[{"text": "🔄 New Calculation", "callback_data": "dutching_start"}]]}


# ---------------------------------------------------------------------------
# Core LP calculation
# ---------------------------------------------------------------------------
def calculate_arbitrage(team_configs: Dict[str, Dict], total_stake: float = 100.0) -> str:
    prob   = pulp.LpProblem("Betting_Arbitrage_Optimization", pulp.LpMaximize)
    stakes = pulp.LpVariable.dicts("Stake", team_configs.keys(), lowBound=0, cat='Continuous')
    base_profit = pulp.LpVariable("Base_Profit", lowBound=None, cat='Continuous')

    prob += base_profit, "Maximize_Profit"
    prob += pulp.lpSum([stakes[team] for team in team_configs.keys()]) == total_stake, "Total_Stake_Constraint"

    for team, config in team_configs.items():
        weight = config.get("weight", 1.0)
        profit_if_wins = stakes[team] * config["odds"] - total_stake
        prob += profit_if_wins == base_profit * weight, f"Profit_Constraint_{team}"

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    result_lines = []
    result_lines.append(f"LP Optimization Status: {pulp.LpStatus[prob.status]}")
    result_lines.append("-" * 65)

    arbitrage_sum = sum(1 / config["odds"] for config in team_configs.values())
    arbitrage_pct = arbitrage_sum * 100
    result_lines.append(f"The Golden Rule of Arbitrage: {arbitrage_pct:.2f}% (Sum of Implied Probabilities)")

    if arbitrage_pct < 100 - 1e-4:
        result_lines.append("-> Status: PROFITABLE (Sum < 100%). A guaranteed profit is possible.")
    elif abs(arbitrage_pct - 100) <= 1e-4:
        result_lines.append("-> Status: BREAK-EVEN (Sum == 100%). You will exactly break even.")
    else:
        result_lines.append("-> Status: NOT PROFITABLE (Sum > 100%). A guaranteed loss is unavoidable.")

    result_lines.append("-" * 65)
    result_lines.append(f"Total Invested: ${total_stake:.2f}")
    result_lines.append("-" * 65)

    for team, config in team_configs.items():
        stake = stakes[team].varValue or 0.0
        return_if_wins = stake * config["odds"]
        profit = return_if_wins - total_stake
        result_lines.append(
            f"Stake on {team}: ${stake:.2f} @ {config['odds']:.2f} odds "
            f"-> Return: ${return_if_wins:.2f} | Profit: ${profit:.2f}"
        )

    result_lines.append("-" * 65)
    base_profit_val = base_profit.varValue
    if base_profit_val is not None:
        result_lines.append(f"Base Profit Multiplier: {base_profit_val:.2f}")
    else:
        result_lines.append("Could not find an optimal solution.")

    return "\n".join(result_lines)


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------
class DutchingBot(TelegramBot):
    def __init__(self):
        super().__init__(getattr(settings, 'TELEGRAM_DUTCHING_BOT_TOKEN', ''))

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _get_state(self, user_id: str) -> Optional[UserState]:
        return UserState.objects.filter(user_id=user_id).first()

    def _clear_state(self, user_id: str) -> None:
        UserState.objects.filter(user_id=user_id).delete()

    def _set_state(self, user_id: str, state: str, context: Dict) -> None:
        obj, _ = UserState.objects.get_or_create(user_id=user_id)
        obj.state   = state
        obj.context = context
        obj.save()

    # ------------------------------------------------------------------
    # Shorthand: send directly and return None so views.py sends nothing extra
    # ------------------------------------------------------------------
    def _reply(self, chat_id: str, text: str, reply_markup: Optional[Dict] = None) -> None:
        self.send_message(chat_id, text, reply_markup=reply_markup)

    # ------------------------------------------------------------------
    # Wizard flow helpers (shared between text commands and button callbacks)
    # ------------------------------------------------------------------
    def _start_wizard(self, user_id: str, chat_id: str) -> None:
        self._set_state(user_id, STATE_AWAITING_TOTAL_BET, {})
        self._reply(
            chat_id,
            "🎰 <b>Arbitrage Wizard</b>\n\n"
            "Step 1 of 3: What is your <b>total bet amount</b>? (e.g., <code>100</code>)",
            reply_markup=_cancel_kb(),
        )

    def _cancel_wizard(self, user_id: str, chat_id: str) -> None:
        self._clear_state(user_id)
        self._reply(
            chat_id,
            "✅ Session cancelled.",
            reply_markup=_start_kb(),
        )

    # ------------------------------------------------------------------
    # Main entry point (text messages)
    # ------------------------------------------------------------------
    def handle_command(self, message: Dict[str, Any]) -> None:
        """
        Sends responses directly (with reply_markup) and always returns None
        so views.py does not attempt a second send.
        """
        try:
            message_text = message.get('text', '').strip()
            user_id  = str(message.get('from', {}).get('id', ''))
            chat_id  = str(message.get('chat', {}).get('id', ''))

            # ── /start ──────────────────────────────────────────────────────
            if message_text.startswith('/start'):
                self._reply(
                    chat_id,
                    "Hello! I am the <b>Dutching Arbitrage Bot</b>.\n\n"
                    "Use the button below to start a guided step-by-step session.",
                    reply_markup=_start_kb(),
                )
                return None

            # ── /cancel ──────────────────────────────────────────────────────
            if message_text.startswith('/cancel'):
                self._cancel_wizard(user_id, chat_id)
                return None

            # ── /interactive ─────────────────────────────────────────────────
            if message_text.startswith('/interactive'):
                self._start_wizard(user_id, chat_id)
                return None

            # ── active wizard session ─────────────────────────────────────────
            user_state = self._get_state(user_id)
            if user_state:
                self._handle_wizard(user_id, chat_id, user_state, message_text)
                return None

            # ── unknown input ─────────────────────────────────────────────────
            self._reply(
                chat_id,
                "ℹ️ Use the button below to start a guided session.",
                reply_markup=_start_kb(),
            )
            return None

        except Exception as e:
            logger.error(f"Error in DutchingBot.handle_command: {e}", exc_info=True)
            # Fall back to returning a string so views.py still delivers the error
            return f"<pre>{html.escape(f'An unexpected error occurred: {str(e)}')}</pre>"

    # ------------------------------------------------------------------
    # Button callback handler
    # ------------------------------------------------------------------
    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        try:
            callback_id = callback_query.get('id', '')
            data        = callback_query.get('data', '')
            user_id     = str(callback_query.get('from', {}).get('id', ''))
            chat_id     = str(callback_query.get('message', {}).get('chat', {}).get('id', ''))

            # Acknowledge the button press immediately (removes the loading spinner)
            self.answer_callback_query(callback_id)

            if data == 'dutching_start':
                self._start_wizard(user_id, chat_id)
            elif data == 'dutching_cancel':
                self._cancel_wizard(user_id, chat_id)

        except Exception as e:
            logger.error(f"Error in DutchingBot.handle_callback_query: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Wizard state machine
    # ------------------------------------------------------------------
    def _handle_wizard(self, user_id: str, chat_id: str, user_state: UserState, text: str) -> None:
        state   = user_state.state
        context = user_state.context

        # ── Step 1: receive total bet ────────────────────────────────────────
        if state == STATE_AWAITING_TOTAL_BET:
            try:
                total_bet = float(text)
                if total_bet <= 0:
                    self._reply(
                        chat_id,
                        "⚠️ Please enter a positive number for the total bet amount.",
                        reply_markup=_cancel_kb(),
                    )
                    return
            except ValueError:
                self._reply(
                    chat_id,
                    f"⚠️ <code>{html.escape(text)}</code> is not a valid number. "
                    f"Please enter the total bet amount (e.g., <code>100</code>).",
                    reply_markup=_cancel_kb(),
                )
                return

            self._set_state(user_id, STATE_AWAITING_NUM_ODDS, {"total_bet": total_bet})
            self._reply(
                chat_id,
                f"✅ Total bet: <b>${total_bet:.2f}</b>\n\n"
                "Step 2 of 3: How many odds do you have? (e.g., <code>4</code>)",
                reply_markup=_cancel_kb(),
            )
            return

        # ── Step 2: receive number of odds ───────────────────────────────────
        if state == STATE_AWAITING_NUM_ODDS:
            try:
                num_odds = int(text)
                if num_odds < 2:
                    self._reply(
                        chat_id,
                        "⚠️ You need at least 2 odds for dutching. Please enter a number ≥ 2.",
                        reply_markup=_cancel_kb(),
                    )
                    return
            except ValueError:
                self._reply(
                    chat_id,
                    f"⚠️ <code>{html.escape(text)}</code> is not a valid integer. "
                    f"Please enter the number of odds.",
                    reply_markup=_cancel_kb(),
                )
                return

            context["num_odds"] = num_odds
            self._set_state(user_id, STATE_AWAITING_ODDS_LIST, context)

            # Generate a full-sized example (one line per expected odd)
            example_lines = "\n".join(
                f"{_EXAMPLE_ODDS[i % len(_EXAMPLE_ODDS)]} 1"
                for i in range(num_odds)
            )
            self._reply(
                chat_id,
                f"✅ Expecting <b>{num_odds} odds</b>.\n\n"
                "Step 3 of 3: Enter each odd and its weight on a <b>separate line</b>:\n"
                "<code>odds weight</code>\n\n"
                "Copy and edit this template:\n"
                f"<pre>{example_lines}</pre>\n"
                f"Weight is optional — if omitted it defaults to <code>1</code>.\n\n"
                f"Please paste all <b>{num_odds} lines</b> now:",
                reply_markup=_cancel_kb(),
            )
            return

        # ── Step 3: receive odds list ────────────────────────────────────────
        if state == STATE_AWAITING_ODDS_LIST:
            total_bet = context.get("total_bet", 100.0)
            num_odds  = context.get("num_odds", 0)

            lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

            if len(lines) != num_odds:
                self._reply(
                    chat_id,
                    f"⚠️ Expected <b>{num_odds} lines</b> but received <b>{len(lines)}</b>.\n"
                    "Please paste all lines at once, one per line.",
                    reply_markup=_cancel_kb(),
                )
                return

            team_configs: Dict[str, Dict] = {}
            for i, line in enumerate(lines, start=1):
                parts = line.split()
                try:
                    odds   = float(parts[0])
                    weight = float(parts[1]) if len(parts) >= 2 else 1.0
                    if odds <= 1.0:
                        self._reply(
                            chat_id,
                            f"⚠️ Line {i}: odds must be greater than 1.0 "
                            f"(got <code>{html.escape(parts[0])}</code>).",
                            reply_markup=_cancel_kb(),
                        )
                        return
                    if weight <= 0:
                        self._reply(
                            chat_id,
                            f"⚠️ Line {i}: weight must be positive "
                            f"(got <code>{html.escape(parts[1])}</code>).",
                            reply_markup=_cancel_kb(),
                        )
                        return
                except (ValueError, IndexError):
                    self._reply(
                        chat_id,
                        f"⚠️ Line {i}: <code>{html.escape(line)}</code> is invalid.\n"
                        "Format: <code>odds weight</code> or just <code>odds</code>",
                        reply_markup=_cancel_kb(),
                    )
                    return
                team_configs[f"Team {i}"] = {"odds": odds, "weight": weight}

            # All good – run calculation
            self._clear_state(user_id)
            try:
                result = calculate_arbitrage(team_configs, total_stake=total_bet)
                self._reply(
                    chat_id,
                    f"<pre>{html.escape(result)}</pre>",
                    reply_markup=_new_calc_kb(),
                )
            except Exception as e:
                logger.error(f"calculate_arbitrage error: {e}", exc_info=True)
                self._reply(
                    chat_id,
                    f"<pre>{html.escape(f'Calculation error: {str(e)}')}</pre>",
                    reply_markup=_start_kb(),
                )
            return

        # Unknown state – reset
        self._clear_state(user_id)
        self._reply(
            chat_id,
            "⚠️ Unknown session state. It has been cleared.",
            reply_markup=_start_kb(),
        )


