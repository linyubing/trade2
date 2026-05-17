"""
Trading Agent module - Core AI decision-making component.
Builds System Prompt, User Message, defines JSON output format,
calls OpenAI API (JSON mode), handles action loop, and parses final decision.
"""
import json
import openai
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging

from config.config import settings
from services.market_data import MarketDataService
from services.account_manager import AccountManager
from services.trade_execution import TradeExecutionService
from risk.risk_manager import RiskManager
from database.models import AIDecision
from database.database import SessionLocal
from utils.time_utils import get_utc_now, format_utc_time

logger = logging.getLogger(__name__)


class TradingAgent:
    """
    Core AI Trading Agent.
    Handles LLM interaction, tool execution, and decision parsing.
    """
    
    def __init__(self):
        """Initialize the Trading Agent."""
        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            max_retries=5
        )
        self.model_name = settings.AI_MODEL_NAME
        
        self.market_data = MarketDataService()
        self.account_manager = AccountManager()
        self.trade_execution = TradeExecutionService()
        self.risk_manager = RiskManager()
        
        self.iteration = 0
        self.start_time = get_utc_now()
        
        logger.info("TradingAgent initialized with model: %s", self.model_name)
    
    def build_system_prompt(self, strategy: str = None) -> str:
        """Build System Prompt for AI trader."""
        if strategy is None:
            strategy = settings.STRATEGY

        # ai-autonomous / alpha-beta
        if strategy in ["ai-autonomous", "alpha-beta"]:
            p = (
                "你是一个AI加密货币交易员。用户消息中包含所有市场数据，你只需阅读数据后直接输出JSON交易决策。\n\n"
                "严格规则（违反任意一条即视为错误输出）：\n"
                "1. 只输出一个合法的JSON对象，不要任何其他文字、解释、分析或思考过程\n"
                "2. 不要写\"首先\"、\"基于数据\"、\"分析如下\"等任何前缀\n"
                "3. 输出必须是可以被json.loads直接解析的纯JSON\n\n"
                "输出格式示例（三选一）：\n"
                '- {"action": "hold", "reason": "RSI超买,无趋势突破"}\n'
                '- {"action": "open", "side": "long", "leverage": 5, "amount_usdt": 100, "reason": "EMA金叉,趋势多头"}\n'
                '- {"action": "close", "close_percent": 100, "reason": "触及止损线"}\n\n'
                "reason字段必填，写具体的技术指标或市场信号（如RSI超买/EMA金叉/跌破支撑等），控制在20字以内。\n"
                "杠杆1-10倍，单笔50-200 USDT，没信号就hold。"
            )
            return p

        # 其他策略
        else:
            r = ""
            if strategy == "conservative":
                r = (
                    "风险规则：\n"
                    "- 最大杠杆：5倍\n"
                    "- 单笔最大风险：总资金的2%\n"
                    "- 必须设置止损\n"
                    "- 优先保护本金\n"
                )
            elif strategy == "balanced":
                r = (
                    "风险规则：\n"
                    "- 最大杠杆：10倍\n"
                    "- 单笔最大风险：总资金的3%\n"
                    "- 建议设置止损\n"
                    "- 平衡收益和风险\n"
                )
            elif strategy == "aggressive":
                r = (
                    "风险规则：\n"
                    "- 最大杠杆：20倍\n"
                    "- 单笔最大风险：总资金的5%\n"
                    "- 严格区分趋势市和震荡市\n"
                    "- 趋势市：持有时间长\n"
                    "- 震荡市：快速进出\n"
                )
            pn = ""
            if settings.ENABLE_CODE_LEVEL_PROTECTION:
                pn = "**代码级保护已启用**：系统自动止损止盈。\n"
            sp = (
                "你是一个AI加密货币交易员。\n\n"
                f"{pn}"
                f"{r}\n"
                "基于数据在策略框架内做出交易决策。\n"
                f"系统限制：最大杠杆{settings.MAX_LEVERAGE}倍，最多{settings.MAX_POSITIONS}个持仓。"
            )
            return sp
    def build_user_message(self, account_info: Dict, positions: List[Dict], 
                           market_data: Dict, news_data: Dict = None, 
                           trade_history: List[Dict] = None) -> str:
        """
        Build User Message (PRD Section 3.3) - Plain text, NOT JSON.
        """
        self.iteration += 1
        minutes_elapsed = int(get_utc_now().timestamp() - self.start_time.timestamp()) // 60
        current_time = format_utc_time(get_utc_now(), "%Y-%m-%d %H:%M:%S UTC")
        
        message_lines = [
            f"=== 交易周期 #{self.iteration} | 已运行 {minutes_elapsed} 分钟 | 当前时间：{current_time} ===",
            "",
            "【账户状态】",
            f"- 总余额：{account_info.get('total_wallet_balance', 0):.2f} USDT",
            f"- 可用余额：{account_info.get('available_balance', 0):.2f} USDT",
            f"- 未实现盈亏：{account_info.get('total_unrealized_profit', 0):.2f} USDT",
            f"- 收益率：{account_info.get('return_percent', 0):.2f}%",
            "",
            "【当前持仓】"
        ]
        
        if positions:
            for pos in positions:
                holding_time = self._calculate_holding_time(pos.get('open_time', get_utc_now()))
                stop_loss_price = self._calculate_stop_loss(pos)
                trailing_stop = "未触发"
                
                message_lines.append(
                    f"- {pos['symbol']} | {pos['side']} | "
                    f"数量：{pos['quantity']:.4f} | "
                    f"杠杆：{pos.get('leverage', 1)}x | "
                    f"入场价：{pos['entry_price']:.2f} | "
                    f"当前价：{pos.get('mark_price', pos.get('current_price', 0)):.2f} | "
                    f"盈亏：{pos.get('unrealized_pnl', 0):.2f} USDT | "
                    f"持仓时间：{holding_time:.1f} 小时"
                )
                message_lines.append(
                    f"  - 止损线：{stop_loss_price:.2f} | "
                    f"移动止盈触发：{trailing_stop}"
                )
        else:
            message_lines.append("（无持仓）")
        
        message_lines.extend([
            "",
            "【市场数据 - BTC】",
            f"- 当前价格：{market_data.get('price', 0):.2f}"
        ])

        if 'funding_rate' in market_data:
            message_lines.append(f"- 资金费率：{market_data['funding_rate']:.6f}")

        message_lines.extend(["", "【多时间框架技术指标分析】"])

        if 'multi_timeframe' in market_data:
            for tf in ["5m", "15m", "1h", "4h"]:
                if tf not in market_data['multi_timeframe']:
                    continue
                data = market_data['multi_timeframe'][tf]
                msg = f"【{tf}】收盘 {data.get('close', 0):.2f} | 高 {data.get('high', 0):.2f} | 低 {data.get('low', 0):.2f} | 量 {data.get('volume', 0):.2f}"
                if 'ema20' in data:
                    msg += f" | EMA20={data['ema20']:.2f}"
                if 'ema50' in data:
                    msg += f" EMA50={data['ema50']:.2f}"
                if 'rsi14' in data:
                    msg += f" | RSI14={data['rsi14']:.2f}"
                if 'macd' in data:
                    msg += f" | MACD={data['macd']:.4f}"
                if 'trend' in data:
                    msg += f" | 趋势={data['trend']}"
                message_lines.append(msg)
        else:
            message_lines.append("- 暂无多时间框架数据")
        
        message_lines.extend(["", "【新闻和消息】"])
        
        if news_data and 'news' in news_data and news_data['news']:
            for news in news_data['news'][:5]:
                message_lines.append(f"- {news.get('title', 'No title')} ({news.get('timestamp', 'N/A')})")
                if 'content' in news and news['content']:
                    content = news['content'][:200] + "..." if len(news['content']) > 200 else news['content']
                    message_lines.append(f"  {content}")
        else:
            message_lines.append("（暂无新闻）")
        
        message_lines.extend(["", "【最近交易记录】"])
        
        if trade_history:
            for trade in trade_history[-5:]:
                message_lines.append(
                    f"- {trade.get('timestamp', 'N/A')} | "
                    f"{trade.get('symbol', 'N/A')} | "
                    f"{trade.get('side', 'N/A')} | "
                    f"数量：{trade.get('quantity', 0):.4f} | "
                    f"价格：{trade.get('price', 0):.2f} | "
                    f"盈亏：{trade.get('pnl', 0):.2f}"
                )
        else:
            message_lines.append("（无交易记录）")
        
        message_lines.extend([
            "",
            "【可用工具】",
            "1. getMarketPrice(symbol) - 获取指定币种当前价格",
            "2. getTechnicalIndicators(symbol, timeframes) - 获取多时间框架技术指标",
            "3. getFundingRate(symbol) - 获取资金费率",
            "4. getOrderBook(symbol, limit) - 获取订单簿",
            "5. openPosition(symbol, side, leverage, amountUsdt) - 开仓",
            "6. closePosition(symbol, closePercent) - 平仓（部分或全部）",
            "7. cancelOrder(symbol, orderId) - 取消订单",
            "8. getAccountBalance() - 获取账户余额",
            "9. getPositions() - 获取当前持仓",
            "10. getOpenOrders() - 获取未成交订单",
            "11. checkOrderStatus(orderId) - 检查订单状态",
            "12. calculateRisk(symbol, side, leverage, amountUsdt) - 计算交易风险",
            "13. syncPositions() - 同步持仓数据",
            "14. getCryptoNews(coin, limit) - 获取加密货币新闻",
            "15. getExchangeAnnouncements(coin, limit) - 获取交易所公告",
            "16. getLatestEvents(coin, limit) - 获取最新市场事件",
            ""
        ])
        
        if settings.STRATEGY == "ai-autonomous":
            message_lines.extend([
                "【复盘思考】",
                "在分析市场和做出决策之前，请先回顾：",
                "1. 最近3笔交易的表现（盈利/亏损）",
                "2. 成功交易的共同特点",
                "3. 失败交易的问题所在",
                "4. 本次交易的改进计划",
                "",
                "然后输出你的复盘思考，再执行交易决策。",
                ""
            ])
        
        message_lines.append("现在，请基于以上信息做出你的交易决策（调用合适的工具，或直接输出分析结果）。")
        message_lines.append("")
        message_lines.append("⚠️ 极其重要：你的输出必须且只能是一个合法JSON对象，不要任何其他文字。示例: {\"action\": \"hold\", \"reason\": \"RSI超买\"}")
        return "\n".join(message_lines)
    
    def get_tools_definition(self) -> List[Dict]:
        """
        Get 16 Function Calling tools definition (PRD Section 3.6).
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "getMarketPrice",
                    "description": "Get current market price for a specified crypto symbol",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "enum": ["BTC", "ETH", "SOL", "BNB"],
                                "description": "Crypto symbol"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "getTechnicalIndicators",
                    "description": "Get multi-timeframe technical indicators for a specified symbol",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "enum": ["BTC", "ETH", "SOL", "BNB"]
                            },
                            "timeframes": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "enum": ["1m", "3m", "5m", "15m", "30m", "1h", "4h"]
                                }
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "getFundingRate",
                    "description": "Get perpetual contract funding rate for a symbol",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "enum": ["BTC", "ETH", "SOL", "BNB"]
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "getOrderBook",
                    "description": "Get order book for a specified symbol",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "enum": ["BTC", "ETH", "SOL", "BNB"]
                            },
                            "limit": {
                                "type": "number",
                                "description": "Number of bid/ask levels (default 20)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "openPosition",
                    "description": "Open a new futures position (market order)",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol", "side", "leverage", "amountUsdt"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "enum": ["BTC", "ETH", "SOL", "BNB"]
                            },
                            "side": {
                                "type": "string",
                                "enum": ["long", "short"]
                            },
                            "leverage": {
                                "type": "number",
                                "minimum": 1,
                                "maximum": settings.MAX_LEVERAGE
                            },
                            "amountUsdt": {
                                "type": "number",
                                "description": "Margin amount in USDT"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "closePosition",
                    "description": "Close part or all of an existing position (market order)",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "enum": ["BTC", "ETH", "SOL", "BNB"]
                            },
                            "closePercent": {
                                "type": "number",
                                "minimum": 1,
                                "maximum": 100,
                                "description": "Percentage to close (default 100)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "cancelOrder",
                    "description": "Cancel a pending order",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol", "orderId"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "enum": ["BTC", "ETH", "SOL", "BNB"]
                            },
                            "orderId": {
                                "type": "string"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "getAccountBalance",
                    "description": "Get current account balance and PnL",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "getPositions",
                    "description": "Get all current active positions",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "getOpenOrders",
                    "description": "Get all pending orders",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "checkOrderStatus",
                    "description": "Check status of a specific order",
                    "parameters": {
                        "type": "object",
                        "required": ["orderId"],
                        "properties": {
                            "orderId": {
                                "type": "string"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculateRisk",
                    "description": "Calculate risk metrics for a proposed trade",
                    "parameters": {
                        "type": "object",
                        "required": ["symbol", "side", "leverage", "amountUsdt"],
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "enum": ["BTC", "ETH", "SOL", "BNB"]
                            },
                            "side": {
                                "type": "string",
                                "enum": ["long", "short"]
                            },
                            "leverage": {
                                "type": "number"
                            },
                            "amountUsdt": {
                                "type": "number"
                            },
                            "stopLossPercent": {
                                "type": "number"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "syncPositions",
                    "description": "Sync local position records with exchange data",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "getCryptoNews",
                    "description": "Get latest crypto news for a specified coin",
                    "parameters": {
                        "type": "object",
                        "required": ["coin"],
                        "properties": {
                            "coin": {
                                "type": "string",
                                "enum": ["bitcoin", "ethereum", "solana", "binancecoin"],
                                "description": "Coin name for news API"
                            },
                            "limit": {
                                "type": "number",
                                "description": "Number of news items (default 10)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "getExchangeAnnouncements",
                    "description": "Get latest exchange announcements for a specified coin",
                    "parameters": {
                        "type": "object",
                        "required": ["coin"],
                        "properties": {
                            "coin": {
                                "type": "string",
                                "enum": ["bitcoin", "ethereum", "solana", "binancecoin"]
                            },
                            "limit": {
                                "type": "number"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "getLatestEvents",
                    "description": "Get latest market event alerts for a specified coin",
                    "parameters": {
                        "type": "object",
                        "required": ["coin"],
                        "properties": {
                            "coin": {
                                "type": "string",
                                "enum": ["bitcoin", "ethereum", "solana", "binancecoin"]
                            },
                            "limit": {
                                "type": "number"
                            }
                        }
                    }
                }
            }
        ]
        return tools
    
    def call_llm(self, messages: List[Dict], tools: List[Dict] = None, 
                  max_iterations: int = 5) -> Dict:
        """
        Call LLM API with JSON mode.
        """
        iteration = 0
        _retry_502 = 0
        _max_retry_502 = 20
        
        while iteration < max_iterations:
            # 消息历史上下文裁剪
            if len(messages) > 3:
                total_chars = sum(len(str(m.get("content", ""))) for m in messages)
                if total_chars > 6000 * 4:
                    keep = [0]
                    non_sys = [i for i in range(1, len(messages)) if messages[i].get("role") == "assistant"]
                    if non_sys:
                        keep.append(non_sys[-1])
                    keep.append(len(messages) - 1)
                    keep = sorted(set(keep))
                    messages = [messages[i] for i in keep]
                    logger.info(f"消息历史裁剪至 {len(keep)} 条")

            try:
                # 日志：调用前打印消息统计
                _total_chars = sum(len(str(m.get("content", ""))) for m in messages)
                _role_counts = {}
                for m in messages:
                    _role_counts[m.get("role", "unknown")] = _role_counts.get(m.get("role", "unknown"), 0) + 1
                logger.info(f"LLM 调用: model={self.model_name}, messages={len(messages)}条({_role_counts}), "
                            f"总字符={_total_chars}, 估算token≈{_total_chars//4}")

                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    # LM Studio: response_format removed - model follows prompt for JSON output
                    temperature=0.7,
                    max_tokens=2048,
                    timeout=120
                )
                
                message = response.choices[0].message
                content = message.content or ""

                # 日志：响应统计
                _usage = getattr(response, 'usage', None)
                if _usage:
                    from typing import get_args
                    _pt = getattr(_usage, 'prompt_tokens', None) or getattr(_usage, 'prompt_tokens', '?')
                    _ct = getattr(_usage, 'completion_tokens', None) or getattr(_usage, 'completion_tokens', '?')
                    _tt = getattr(_usage, 'total_tokens', None) or getattr(_usage, 'total_tokens', '?')
                    logger.info(f"LLM 响应: prompt_tokens={_pt}, completion_tokens={_ct}, total_tokens={_tt}")
                else:
                    logger.info(f"LLM 响应: content_len={len(content)}, reasoning_len={len(getattr(message, 'reasoning_content', '') or '')}")
                
                # Handle deepseek-r1 thinking_content
                # LM Studio + deepseek-r1 有时将实际输出放在 reasoning_content 而非 content
                if hasattr(message, "reasoning_content") and message.reasoning_content:
                    if not content or not content.strip():
                        content = message.reasoning_content
                        logger.debug("content 为空，从 reasoning_content 获取内容")
                    else:
                        logger.debug(f"LLM thinking: {message.reasoning_content[:200]}")

                # 多策略提取 JSON（处理思考文本混杂的情况）
                import re
                json_data = None

                # 策略1：整段内容就是 JSON
                try:
                    json_data = json.loads(content)
                    content = json.dumps(json_data, ensure_ascii=False)
                    logger.debug("JSON 解析成功（策略1：整段解析）")
                except json.JSONDecodeError:
                    json_data = None

                # 策略2：从 markdown 代码块提取
                if json_data is None:
                    _json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
                    if _json_match:
                        try:
                            content = _json_match.group(1).strip()
                            json_data = json.loads(content)
                            logger.debug("JSON 解析成功（策略2：markdown 代码块）")
                        except json.JSONDecodeError:
                            json_data = None

                # 策略3：找第一个 { 和最后一个 } 之间的内容
                if json_data is None:
                    start = content.find("{")  # 找到第一个 {
                    end = content.rfind("}")
                    if start != -1 and end > start:
                        candidate = content[start:end+1]
                        try:
                            content = candidate
                            json_data = json.loads(content)
                            logger.debug("JSON 解析成功（策略3：首尾括号提取）")
                        except json.JSONDecodeError:
                            json_data = None

                # 策略4：从后往前找最后一个合法 JSON 对象（推理文本在前，JSON 在后）
                if json_data is None:
                    _last_brace = content.rfind("}")
                    if _last_brace != -1:
                        # 从最后一个 } 往前找匹配的 {
                        _search = content[:_last_brace + 1]
                        for _start in range(_search.rfind("{"), -1, -1):
                            if _search[_start] != "{":
                                continue
                            try:
                                decoder = json.JSONDecoder()
                                obj, idx = decoder.raw_decode(_search, _start)
                                json_data = obj
                                content = json.dumps(json_data, ensure_ascii=False)
                                logger.debug("JSON 解析成功（策略4：从后往前 raw_decode）")
                                break
                            except json.JSONDecodeError:
                                continue

                if json_data is None:
                    logger.error(f"LLM 返回了非 JSON 内容: {content[:300]}")
                    return {
                        "type": "error",
                        "content": "JSON 解析失败，默认 HOLD"
                    }
                
                logger.info(f"LLM JSON 响应: {json.dumps(json_data, ensure_ascii=False)[:300]}")
                
                if "actions" in json_data and isinstance(json_data["actions"], list):
                    actions = json_data["actions"]
                    logger.info(f"LLM 请求执行 {len(actions)} 个操作")
                    
                    action_results = []
                    for action_item in actions:
                        action_name = action_item.get("action")
                        action_args = action_item.get("args", {})
                        
                        logger.info(f"执行操作: {action_name}, 参数: {action_args}")
                        result = self.execute_tool(action_name, action_args)
                        action_results.append({
                            "action": action_name,
                            "args": action_args,
                            "result": result
                        })
                        logger.info(f"操作结果: {result}")
                    
                    messages.append({
                        "role": "assistant",
                        "content": content
                    })
                    
                    results_text = "操作执行结果：\n" + "\n".join([
                        f"- {r['action']}: {json.dumps(r['result'], ensure_ascii=False, default=str)}"
                        for r in action_results
                    ])
                    messages.append({
                        "role": "user",
                        "content": results_text
                    })
                    
                    iteration += 1
                    continue
                
                if "decision" in json_data:
                    logger.info(f"LLM 做出最终决策: {json_data['decision']}")
                    return {
                        "type": "json_decision",
                        "content": content,
                        "data": json_data
                    }
                
                if "thinking" in json_data and "decision" not in json_data and "actions" not in json_data:
                    logger.info("LLM 输出分析/复盘（无决策）")
                    return {
                        "type": "text",
                        "content": content,
                        "data": json_data
                    }

                # 直接决策格式：{"action": "hold", "reason": "..."}
                if "action" in json_data:
                    logger.info(f"LLM 做出直接决策: action={json_data['action']}")
                    return {
                        "type": "json_decision",
                        "content": content,
                        "data": json_data
                    }

                logger.info(f"LLM 返回了未知 JSON 格式，降级为文本响应: {json_data}")
                return {
                    "type": "text",
                    "content": content,
                    "data": json_data
                }
                    
            except Exception as e:
                _status = getattr(e, 'status_code', 'N/A') if hasattr(e, 'status_code') else 'N/A'
                _body = getattr(e, 'body', str(e))[:500] if hasattr(e, 'body') else str(e)[:500]
                _code = getattr(e, 'code', 'N/A') if hasattr(e, 'code') else 'N/A'
                
                # 502 Bad Gateway: LM Studio 后端短暂不可用，等一会再重试
                if '502' in str(_status) or '502' in str(_body):
                    _retry_502 += 1
                    if _retry_502 > _max_retry_502:
                        logger.error(f"502 重试 {_max_retry_502} 次后仍失败，放弃")
                        return {"type": "error", "content": f"502 重试 {_max_retry_502} 次后超时"}
                    import time as _time
                    _wait = min(30, 2 ** (_retry_502 // 3))
                    logger.warning(f"LM Studio 返回 502 ({_retry_502}/{_max_retry_502})，等待 {_wait}s 后重试...")
                    _time.sleep(_wait)
                    continue
                
                logger.error(f"LLM 调用失败: HTTP {_status}, code={_code}, body={_body}")
                logger.error(f"调用时 messages={len(messages)}条, 总chars≈{_total_chars}")
                return {
                    "type": "error",
                    "content": str(e),
                    "raw_response": None
                }
        
        logger.warning(f"达到最大工具调用迭代次数 ({max_iterations})")
        return {
            "type": "max_iterations_reached",
            "content": "达到最大工具调用迭代次数",
            "raw_response": None
        }

    def execute_tool(self, function_name: str, function_args: Dict) -> Dict:
        """
        Execute a tool function.
        """
        try:
            if function_name == "getMarketPrice":
                symbol = function_args.get("symbol")
                price = self.market_data.get_current_price(symbol)
                return {"symbol": symbol, "price": price}
            
            elif function_name == "getTechnicalIndicators":
                symbol = function_args.get("symbol")
                timeframes = function_args.get("timeframes", ["5m", "15m", "1h", "4h"])
                indicators = self.market_data.get_technical_indicators(symbol, timeframes)
                return {"symbol": symbol, "timeframes": indicators}
            
            elif function_name == "getFundingRate":
                symbol = function_args.get("symbol")
                rate_data = self.market_data.get_funding_rate(symbol)
                return rate_data
            
            elif function_name == "getOrderBook":
                symbol = function_args.get("symbol")
                limit = function_args.get("limit", 20)
                order_book = self.market_data.get_order_book(symbol, limit)
                return order_book
            
            elif function_name == "openPosition":
                symbol = function_args.get("symbol")
                side = function_args.get("side")
                leverage = function_args.get("leverage")
                amount_usdt = function_args.get("amountUsdt")
                
                risk_check = self.risk_manager.check_before_trade(
                    symbol, side, leverage, amount_usdt
                )
                if not risk_check["allowed"]:
                    return {"success": False, "error": risk_check["reason"]}
                
                result = self.trade_execution.open_position(
                    symbol, side, leverage, amount_usdt
                )
                return result
            
            elif function_name == "closePosition":
                symbol = function_args.get("symbol")
                close_percent = function_args.get("closePercent", 100)
                result = self.trade_execution.close_position(symbol, close_percent)
                return result
            
            elif function_name == "cancelOrder":
                symbol = function_args.get("symbol")
                order_id = function_args.get("orderId")
                result = self.trade_execution.cancel_order(symbol, order_id)
                return result
            
            elif function_name == "getAccountBalance":
                balance = self.account_manager.get_account_balance()
                return balance
            
            elif function_name == "getPositions":
                positions = self.account_manager.get_positions()
                return {"positions": positions}
            
            elif function_name == "getOpenOrders":
                orders = self.account_manager.get_open_orders()
                return {"orders": orders}
            
            elif function_name == "checkOrderStatus":
                order_id = function_args.get("orderId")
                status = self.account_manager.check_order_status(order_id)
                return status
            
            elif function_name == "calculateRisk":
                symbol = function_args.get("symbol")
                side = function_args.get("side")
                leverage = function_args.get("leverage")
                amount_usdt = function_args.get("amountUsdt")
                stop_loss_percent = function_args.get("stopLossPercent")
                
                risk_metrics = self.risk_manager.calculate_risk(
                    symbol, side, leverage, amount_usdt, stop_loss_percent
                )
                return risk_metrics
            
            elif function_name == "syncPositions":
                positions = self.account_manager.sync_positions()
                return {"positions": positions, "count": len(positions)}
            
            elif function_name == "getCryptoNews":
                coin = function_args.get("coin")
                limit = function_args.get("limit", 10)
                return {"coin": coin, "news": [], "message": "News API not implemented yet"}
            
            elif function_name == "getExchangeAnnouncements":
                coin = function_args.get("coin")
                limit = function_args.get("limit", 10)
                return {"coin": coin, "announcements": [], "message": "Announcements API not implemented yet"}
            
            elif function_name == "getLatestEvents":
                coin = function_args.get("coin")
                limit = function_args.get("limit", 10)
                return {"coin": coin, "events": [], "message": "Events API not implemented yet"}
            
            else:
                logger.error(f"Unknown tool: {function_name}")
                return {"error": f"Unknown tool: {function_name}"}
        
        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {e}")
            return {"error": str(e)}
    
    def run_trading_cycle(self) -> Dict:
        """
        Run a complete trading cycle.
        """
        logger.info(f"Starting trading cycle #{self.iteration + 1}")
        
        try:
            account_info = self.account_manager.get_account_balance()
            logger.info(f"[DATA] account_info: {account_info}")
            positions = self.account_manager.get_positions()
            logger.info(f"[DATA] positions: {positions}")
            
            symbol = settings.TRADING_SYMBOL.replace("USDT", "")
            current_price = self.market_data.get_current_price(symbol)
            logger.info(f"[DATA] current_price({symbol}): {current_price}")
            funding_rate = self.market_data.get_funding_rate(symbol)
            logger.info(f"[DATA] funding_rate: {funding_rate}")
            indicators = self.market_data.get_technical_indicators(
                symbol, ["5m", "15m", "1h", "4h"]
            )
            logger.info(f"[DATA] indicators: {indicators}")
            
            multi_tf = self.market_data.get_multi_timeframe_klines(
                settings.TRADING_SYMBOL, ["5m", "15m", "1h", "4h"], limit=1
            )
            logger.info(f"[DATA] multi_tf raw: {multi_tf}")
            
            market_data = {
                "price": current_price,
                "funding_rate": funding_rate.get("funding_rate", 0),
                "indicators": indicators,
                "multi_timeframe": {}
            }

            for tf, klines in multi_tf.items():
                if klines:
                    latest = klines[-1]
                    market_data["multi_timeframe"][tf] = {
                        "open": latest["open"],
                        "high": latest["high"],
                        "low": latest["low"],
                        "close": latest["close"],
                        "volume": latest["volume"]
                    }
                    # 添加该时间框架的技术指标
                    if tf in indicators:
                        market_data["multi_timeframe"][tf].update(indicators[tf])
            
            news_data = {"news": []}
            trade_history = self._get_trade_history()
            
            system_prompt = self.build_system_prompt()
            user_message = self.build_user_message(
                account_info, positions, market_data, news_data, trade_history
            )
            logger.info(f"[DATA] user_message sent to LLM:\n{user_message}")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            db = SessionLocal()
            try:
                ai_decision = AIDecision(
                    prompt=user_message,
                    response="",
                    decision="",
                    execution_result="",
                    model_name=self.model_name,
                    iteration=self.iteration
                )
                db.add(ai_decision)
                db.commit()
                decision_id = ai_decision.id
            finally:
                db.close()
            
            logger.info("Calling LLM for trading decision...")
            llm_response = self.call_llm(messages)
            
            db = SessionLocal()
            try:
                ai_decision = db.query(AIDecision).filter(AIDecision.id == decision_id).first()
                if ai_decision:
                    ai_decision.response = json.dumps(
                        llm_response, 
                        ensure_ascii=False, 
                        default=str
                    )
                    ai_decision.decision = llm_response.get("content", "")
                    db.commit()
            finally:
                db.close()
            
            result = self._parse_and_execute_decision(llm_response)
            
            db = SessionLocal()
            try:
                ai_decision = db.query(AIDecision).filter(AIDecision.id == decision_id).first()
                if ai_decision:
                    ai_decision.execution_result = json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str
                    )
                    db.commit()
            finally:
                db.close()
            
            logger.info(f"Trading cycle #{self.iteration} completed")
            return result
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")
            return {"success": False, "error": str(e)}
    
    def _parse_and_execute_decision(self, llm_response: Dict) -> Dict:
        """
        Parse LLM response and execute decision if needed.
        """
        if llm_response["type"] == "text":
            content = llm_response["content"]
            logger.info(f"LLM analysis: {content[:200]}...")
            
            if settings.STRATEGY == "ai-autonomous" and "复盘" in content:
                logger.info("AI provided self-reflection")
            
            return {
                "success": True,
                "action": "analyze",
                "content": content
            }
        
        elif llm_response["type"] == "json_decision":
            data = llm_response.get("data", {})
            action = data.get("action", "unknown")
            reason = data.get("reason", "")
            logger.info(f"LLM 决策执行: action={action}, reason={reason}")
            return {
                "success": True,
                "action": action,
                "reason": reason,
                "side": data.get("side"),
                "leverage": data.get("leverage"),
                "amount_usdt": data.get("amount_usdt"),
                "close_percent": data.get("close_percent"),
                "response": llm_response
            }

        elif llm_response["type"] == "error":
            return {
                "success": False,
                "action": "error",
                "error": llm_response["content"]
            }

        else:
            return {
                "success": True,
                "action": "unknown",
                "response": llm_response
            }
    
    def _calculate_holding_time(self, open_time: datetime) -> float:
        """Calculate holding time in hours."""
        if isinstance(open_time, datetime):
            if open_time.tzinfo is None:
                open_time = open_time.replace(tzinfo=timezone.utc)
            elapsed = get_utc_now() - open_time
            return elapsed.total_seconds() / 3600
        return 0.0
    
    def _calculate_stop_loss(self, position: Dict) -> float:
        """Calculate stop loss price for a position."""
        entry_price = position.get('entry_price', 0)
        side = position.get('side', 'long')
        leverage = position.get('leverage', 1)
        
        stop_loss_percent = 0.08 if leverage <= 5 else (0.06 if leverage <= 15 else 0.05)
        
        if side == 'long':
            return entry_price * (1 - stop_loss_percent)
        else:
            return entry_price * (1 + stop_loss_percent)
    
    def _get_trade_history(self, limit: int = 10) -> List[Dict]:
        """Get recent trade history from database."""
        db = SessionLocal()
        try:
            from database.models import Trade
            trades = db.query(Trade).order_by(Trade.timestamp.desc()).limit(limit).all()
            return [{
                "timestamp": trade.timestamp.isoformat() if trade.timestamp else "",
                "symbol": trade.symbol,
                "side": trade.side,
                "quantity": float(trade.quantity) if trade.quantity else 0,
                "price": float(trade.price) if trade.price else 0,
                "pnl": float(trade.pnl) if trade.pnl else 0
            } for trade in trades]
        except Exception as e:
            logger.error(f"Error fetching trade history: {e}")
            return []
        finally:
            db.close()


logger.info("TradingAgent module loaded successfully")
