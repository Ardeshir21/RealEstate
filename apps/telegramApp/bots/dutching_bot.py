from typing import Optional, Dict, Any
import ast
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
STATE_AWAITING_TOTAL_BET  = "DUTCHING_AWAITING_TOTAL_BET"
STATE_AWAITING_NUM_ODDS   = "DUTCHING_AWAITING_NUM_ODDS"
STATE_AWAITING_ODDS_LIST  = "DUTCHING_AWAITING_ODDS_LIST"


# ---------------------------------------------------------------------------
# Core LP calculation
# ---------------------------------------------------------------------------
def calculate_arbitrage(team_configs: Dict[str, Dict], total_stake: float = 100.0) -> str:
    # Initialize the LP problem
    prob = pulp.LpProblem("Betting_Arbitrage_Optimization", pulp.LpMaximize)

    # Decision variables: individual stakes for each team (must be >= 0)
    stakes = pulp.LpVariable.dicts("Stake", team_configs.keys(), lowBound=0, cat='Continuous')

    # Decision variable: base profit multiplier
    base_profit = pulp.LpVariable("Base_Profit", lowBound=None, cat='Continuous')

    # Objective: Maximize the base profit
    prob += base_profit, "Maximize_Profit"

    # Constraint 1: sum of all stakes == total budget
    prob += pulp.lpSum([stakes[team] for team in team_configs.keys()]) == total_stake, "Total_Stake_Constraint"

    # Constraints: profit if a team wins must be proportional to its weight
    for team, config in team_configs.items():
        weight = config.get("weight", 1.0)
        profit_if_wins = stakes[team] * config["odds"] - total_stake
        prob += profit_if_wins == base_profit * weight, f"Profit_Constraint_{team}"

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # Build result text
    result_lines = []
    result_lines.append(f"LP Optimization Status: {pulp.LpStatus[prob.status]}")
    result_lines.append("-" * 65)

    arbitrage_sum = sum(1 / config["odds"] for config in team_configs.values())
    arbitrage_percentage = arbitrage_sum * 100
    result_lines.append(f"The Golden Rule of Arbitrage: {arbitrage_percentage:.2f}% (Sum of Implied Probabilities)")

    if arbitrage_percentage < 100 - 1e-4:
        result_lines.append("-> Status: PROFITABLE (Sum < 100%). A guaranteed profit is possible.")
    elif abs(arbitrage_percentage - 100) <= 1e-4:
        result_lines.append("-> Status: BREAK-EVEN (Sum == 100%). You will exactly break even.")
    else:
        result_lines.append("-> Status: NOT PROFITABLE (Sum > 100%). A guaranteed loss is unavoidable.")

    result_lines.append("-" * 65)
    result_lines.append(f"Total Invested: ${total_stake:.2f}")
    result_lines.append("-" * 65)

    for team, config in team_configs.items():
        stake = stakes[team].varValue
        if stake is None:
            stake = 0.0
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
        obj.state = state
        obj.context = context
        obj.save()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        try:
            message_text = message.get('text', '').strip()
            user_id = str(message.get('from', {}).get('id', ''))

            # ── /start ──────────────────────────────────────────────────────
            if message_text.startswith('/start'):
                return (
                    "Hello! I am the Dutching Arbitrage Bot.\n\n"
                    "You can use me in two ways:\n\n"
                    "1️⃣  <b>Interactive Wizard</b> (recommended on mobile)\n"
                    "   Type /interactive to start a guided session.\n\n"
                    "2️⃣  <b>Dictionary Mode</b>\n"
                    "   Send a Python dict directly, e.g.:\n"
                    "<pre>{\n"
                    "  'Team A': {'odds': 2.5, 'weight': 1.0},\n"
                    "  'Team B': {'odds': 3.0, 'weight': 3.0}\n"
                    "}</pre>"
                )

            # ── /cancel ──────────────────────────────────────────────────────
            if message_text.startswith('/cancel'):
                self._clear_state(user_id)
                return "✅ Session cancelled. Send /interactive to start again."

            # ── /interactive ─────────────────────────────────────────────────
            if message_text.startswith('/interactive'):
                self._set_state(user_id, STATE_AWAITING_TOTAL_BET, {})
                return (
                    "🎰 <b>Arbitrage Wizard</b>\n\n"
                    "Step 1 of 3: What is your <b>total bet amount</b>? (e.g., <code>100</code>)\n\n"
                    "Send /cancel at any time to abort."
                )

            # ── check if there is an active wizard session ────────────────────
            user_state = self._get_state(user_id)
            if user_state:
                return self._handle_wizard(user_id, user_state, message_text)

            # ── legacy dict mode ─────────────────────────────────────────────
            return self._handle_dict_mode(message_text)

        except Exception as e:
            logger.error(f"Error in DutchingBot.handle_command: {e}", exc_info=True)
            return f"<pre>{html.escape(f'An unexpected error occurred: {str(e)}')}</pre>"

    # ------------------------------------------------------------------
    # Wizard state machine
    # ------------------------------------------------------------------
    def _handle_wizard(self, user_id: str, user_state: UserState, text: str) -> str:
        state   = user_state.state
        context = user_state.context

        # ── Step 1: receive total bet ────────────────────────────────────────
        if state == STATE_AWAITING_TOTAL_BET:
            try:
                total_bet = float(text)
                if total_bet <= 0:
                    return "⚠️ Please enter a positive number for the total bet amount."
            except ValueError:
                return f"⚠️ <code>{html.escape(text)}</code> is not a valid number. Please enter the total bet amount (e.g., <code>100</code>)."

            self._set_state(user_id, STATE_AWAITING_NUM_ODDS, {"total_bet": total_bet})
            return (
                f"✅ Total bet: <b>${total_bet:.2f}</b>\n\n"
                "Step 2 of 3: How many odds do you have? (e.g., <code>4</code>)"
            )

        # ── Step 2: receive number of odds ───────────────────────────────────
        if state == STATE_AWAITING_NUM_ODDS:
            try:
                num_odds = int(text)
                if num_odds < 2:
                    return "⚠️ You need at least 2 odds for dutching. Please enter a number ≥ 2."
            except ValueError:
                return f"⚠️ <code>{html.escape(text)}</code> is not a valid integer. Please enter the number of odds."

            context["num_odds"] = num_odds
            self._set_state(user_id, STATE_AWAITING_ODDS_LIST, context)

            example_lines = "\n".join(f"2.{i+3} 1" for i in range(min(num_odds, 3)))
            return (
                f"✅ Expecting <b>{num_odds} odds</b>.\n\n"
                "Step 3 of 3: Enter each odd and its weight on a <b>separate line</b>:\n"
                "<code>odds weight</code>\n\n"
                "Example:\n"
                f"<pre>{example_lines}</pre>\n"
                "Weight is optional — if omitted it defaults to <code>1</code>.\n\n"
                f"Please paste all <b>{num_odds} lines</b> now:"
            )

        # ── Step 3: receive odds list ────────────────────────────────────────
        if state == STATE_AWAITING_ODDS_LIST:
            total_bet = context.get("total_bet", 100.0)
            num_odds  = context.get("num_odds", 0)

            lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

            if len(lines) != num_odds:
                return (
                    f"⚠️ Expected <b>{num_odds} lines</b> but received <b>{len(lines)}</b>.\n"
                    "Please paste all lines at once, one per line."
                )

            team_configs: Dict[str, Dict] = {}
            for i, line in enumerate(lines, start=1):
                parts = line.split()
                try:
                    odds = float(parts[0])
                    weight = float(parts[1]) if len(parts) >= 2 else 1.0
                    if odds <= 1.0:
                        return f"⚠️ Line {i}: odds must be greater than 1.0 (got <code>{html.escape(parts[0])}</code>)."
                    if weight <= 0:
                        return f"⚠️ Line {i}: weight must be positive (got <code>{html.escape(parts[1])}</code>)."
                except (ValueError, IndexError):
                    return (
                        f"⚠️ Line {i}: <code>{html.escape(line)}</code> is invalid.\n"
                        "Format: <code>odds weight</code> or just <code>odds</code>"
                    )
                team_configs[f"Team {i}"] = {"odds": odds, "weight": weight}

            # All good – run calculation
            self._clear_state(user_id)
            try:
                result = calculate_arbitrage(team_configs, total_stake=total_bet)
                return f"<pre>{html.escape(result)}</pre>"
            except Exception as e:
                logger.error(f"calculate_arbitrage error: {e}", exc_info=True)
                return f"<pre>{html.escape(f'Calculation error: {str(e)}')}</pre>"

        # Unknown state – reset
        self._clear_state(user_id)
        return "⚠️ Unknown session state. It has been cleared. Send /interactive to start again."

    # ------------------------------------------------------------------
    # Legacy dict mode
    # ------------------------------------------------------------------
    def _handle_dict_mode(self, message_text: str) -> str:
        if not message_text.startswith('{'):
            return (
                "ℹ️ I didn't understand that.\n\n"
                "• Send /interactive for a guided step-by-step session.\n"
                "• Or send a Python dictionary directly:\n"
                "<pre>{\n"
                "  'Team A': {'odds': 2.5, 'weight': 1.0},\n"
                "  'Team B': {'odds': 3.0, 'weight': 1.0}\n"
                "}</pre>"
            )
        try:
            team_configs = ast.literal_eval(message_text)
            if not isinstance(team_configs, dict):
                return "Error: Input must be a valid Python dictionary."

            for k, v in team_configs.items():
                if not isinstance(v, dict) or 'odds' not in v:
                    return f"Error: The value for '{k}' must be a dictionary containing 'odds'."

            result = calculate_arbitrage(team_configs)
            return f"<pre>{html.escape(result)}</pre>"
        except (ValueError, SyntaxError) as e:
            error_msg = f"Error parsing dictionary: Make sure it is valid Python syntax.\n{str(e)}"
            return f"<pre>{html.escape(error_msg)}</pre>"
        except Exception as e:
            error_msg = f"Error calculating arbitrage: {str(e)}"
            return f"<pre>{html.escape(error_msg)}</pre>"

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        pass
