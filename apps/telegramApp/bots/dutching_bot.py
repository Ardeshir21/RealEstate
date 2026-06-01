from typing import Optional, Dict, Any
import ast
import logging
from django.conf import settings

import pulp

from .base import TelegramBot

logger = logging.getLogger(__name__)

def calculate_arbitrage(team_configs, total_stake=100.0):
    # Initialize the LP problem
    # We want to maximize the guaranteed return
    prob = pulp.LpProblem("Betting_Arbitrage_Optimization", pulp.LpMaximize)

    # Decision variables: individual stakes for each team (must be >= 0)
    stakes = pulp.LpVariable.dicts("Stake", team_configs.keys(), lowBound=0, cat='Continuous')

    # Decision variable: base profit multiplier
    base_profit = pulp.LpVariable("Base_Profit", lowBound=None, cat='Continuous')

    # Objective Function: Maximize the base profit
    prob += base_profit, "Maximize_Profit"

    # Constraint 1: The sum of all stakes must equal our total budget (100)
    prob += pulp.lpSum([stakes[team] for team in team_configs.keys()]) == total_stake, "Total_Stake_Constraint"

    # Constraints 2 to 7: The PROFIT if a team wins must be proportional to their weight.
    # Profit = (Stake * Odds) - Total Stake.
    for team, config in team_configs.items():
        # Defaults to weight 1.0 if not specified
        weight = config.get("weight", 1.0)
        profit_if_wins = stakes[team] * config["odds"] - total_stake
        prob += profit_if_wins == base_profit * weight, f"Profit_Constraint_{team}"

    # Solve the problem
    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    # Extract and format the results
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

    actual_invested = 0
    for team, config in team_configs.items():
        stake = stakes[team].varValue
        if stake is None: stake = 0.0
        actual_invested += stake
        return_if_wins = stake * config["odds"]
        profit = return_if_wins - total_stake
        # Use simpler string formatting to ensure alignment
        result_lines.append(f"Stake on {team}: ${stake:.2f} @ {config['odds']:.2f} odds -> Return: ${return_if_wins:.2f} | Profit: ${profit:.2f}")

    result_lines.append("-" * 65)
    base_profit_val = base_profit.varValue
    if base_profit_val is not None:
        result_lines.append(f"Base Profit Multiplier: {base_profit_val:.2f}")
    else:
        result_lines.append("Could not find an optimal solution.")

    return "\n".join(result_lines)

class DutchingBot(TelegramBot):
    def __init__(self):
        # We assume settings.TELEGRAM_DUTCHING_BOT_TOKEN exists, otherwise fallback to empty/dummy string
        super().__init__(getattr(settings, 'TELEGRAM_DUTCHING_BOT_TOKEN', ''))

    def handle_command(self, message: Dict[str, Any]) -> Optional[str]:
        try:
            message_text = message.get('text', '').strip()
            
            if message_text.startswith('/start'):
                return (
                    "Hello! I am the Dutching Arbitrage Bot.\n"
                    "Send me a python dictionary with team configs (odds and weights) to calculate arbitrage.\n"
                    "Example:\n"
                    "{\n"
                    "  'Team A': {'odds': 2.5, 'weight': 1.0},\n"
                    "  'Team B': {'odds': 3.0, 'weight': 1.0}\n"
                    "}"
                )
            
            # Evaluate the dictionary securely
            try:
                team_configs = ast.literal_eval(message_text)
                if not isinstance(team_configs, dict):
                    return "Error: Input must be a valid Python dictionary."
                
                # Check dictionary format
                for k, v in team_configs.items():
                    if not isinstance(v, dict) or 'odds' not in v:
                        return f"Error: The value for '{k}' must be a dictionary containing 'odds'."
                
                import html
                result = calculate_arbitrage(team_configs)
                escaped_result = html.escape(result)
                return f"<pre>{escaped_result}</pre>"
            except (ValueError, SyntaxError) as e:
                return f"Error parsing dictionary: Make sure it is valid Python syntax.\n{str(e)}"
            except Exception as e:
                return f"Error calculating arbitrage: {str(e)}"

        except Exception as e:
            logger.error(f"Error in DutchingBot: {e}")
            return f"An error occurred: {str(e)}"

    def handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        pass
