from langchain.agents import tool


@tool
def generate_trading_signal(symbol:str):
	"""
	Notify the trading signal generator node to provide a trading signal for the symbol.
	"""
	return "Nodified the trading signal generator node."

@tool
def update_trading_signal(symbol:str):
	"""
	Notify the trading signal generator node to update the trading signal for the symbol.
	"""
	return "Nodified the trading signal generator node to update signal."

@tool
def notify_backtest_node(signal_content:str):
	"""
	Notify the backtest node to execute a backtest for the signal content.
    Args:
        signal_contenst (str): The description of the trading signal, all the data backtest need.
	"""
	return "Nodified the trading signal generator node."

# 更新工具列表
tools = [
    generate_trading_signal,
	# update_trading_signal,
    notify_backtest_node,
]