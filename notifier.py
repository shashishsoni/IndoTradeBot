"""
Telegram Notification Module for Trading Signal Analyzer.
Sends alerts when BUY/SELL signals are detected.
"""

import datetime
import json
import os
import time
from typing import List, Optional, TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from risk_manager import RiskState
from zoneinfo import ZoneInfo

from config import SignalType, TradeSignal


def _telegram_error_hint(response: requests.Response) -> str:
    """Explain common Telegram Bot API errors (wrong chat id, etc.)."""
    try:
        data = response.json()
        desc = str(data.get("description", "")).lower()
        code = data.get("error_code")
    except (json.JSONDecodeError, ValueError, TypeError):
        return ""

    if code == 403 and "bots can't send messages to bots" in desc:
        return (
            "TELEGRAM_CHAT_ID must be *your personal user id* (from @userinfobot), "
            "not another bot’s id and not @BotFather’s id.\n"
            "   → Open Telegram as yourself → message @userinfobot → copy the numeric `Id` into .env"
        )
    if code == 403 and "blocked" in desc:
        return "User blocked the bot — open the bot chat and tap Start / Unblock."
    if "chat not found" in desc or "chat_id is empty" in desc:
        return "Message your bot once (tap Start) so Telegram creates the chat, then retry."
    if code == 400 and "chat not found" in desc:
        return "Invalid TELEGRAM_CHAT_ID — use the numeric id from @userinfobot."
    return ""


class TelegramNotifier:
    """Sends Telegram messages when signals are detected."""

    def __init__(self, token: str = None, chat_id: str = None):
        """
        Initialize Telegram bot.
        
        Args:
            token: Telegram Bot API token (get from @BotFather)
            chat_id: Your Telegram chat ID (get from @userinfobot)
        """
        raw_token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN", "")
        raw_chat = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID", "")
        # Strip whitespace / newlines (common .env copy-paste issues)
        self.token = str(raw_token).strip().strip('"').strip("'")
        self.chat_id = str(raw_chat).strip().strip('"').strip("'")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self._last_signal_time = {}  # Track last alert per asset to avoid spam

    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.token and self.chat_id)

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send a message to Telegram.
        
        Args:
            text: Message text (supports Markdown formatting)
            parse_mode: "Markdown" or "HTML"
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured():
            print(f"⚠️ Telegram not configured. Message:\n{text}")
            return False

        url = f"{self.api_url}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                print(f"✅ Telegram message sent successfully")
                return True
            else:
                print(f"❌ Telegram API error: {response.text}")
                hint = _telegram_error_hint(response)
                if hint:
                    print(f"   💡 {hint}")
                return False
        except Exception as e:
            print(f"❌ Failed to send Telegram message: {e}")
            return False

    def send_plain_text(self, text: str) -> bool:
        """
        Send plain text (no Markdown/HTML) — avoids parse errors on special chars.
        Splits into multiple messages if longer than Telegram's 4096 character limit.
        """
        if not self.is_configured():
            print(f"⚠️ Telegram not configured. Message:\n{text[:500]}...")
            return False
        if not text:
            return True

        TELEGRAM_MAX = 4096
        # Reserve space for "Part n/m" header on multi-part messages
        header_reserve = 40
        chunk_body = TELEGRAM_MAX - header_reserve

        chunks: List[str] = []
        i = 0
        while i < len(text):
            chunks.append(text[i : i + chunk_body])
            i += chunk_body

        url = f"{self.api_url}/sendMessage"
        ok_all = True
        for idx, part in enumerate(chunks):
            if len(chunks) > 1:
                body = f"📄 Part {idx + 1}/{len(chunks)}\n\n{part}"
            else:
                body = part
            if len(body) > TELEGRAM_MAX:
                body = body[:TELEGRAM_MAX]
            try:
                response = requests.post(
                    url,
                    json={"chat_id": self.chat_id, "text": body},
                    timeout=30,
                )
                if response.status_code != 200:
                    print(f"❌ Telegram API error: {response.text}")
                    hint = _telegram_error_hint(response)
                    if hint:
                        print(f"   💡 {hint}")
                    ok_all = False
                else:
                    if len(chunks) > 1:
                        print(f"✅ Telegram part {idx + 1}/{len(chunks)} sent")
            except Exception as e:
                print(f"❌ Failed to send Telegram message: {e}")
                ok_all = False
        if ok_all and len(chunks) == 1:
            print("✅ Telegram message sent successfully")
        elif ok_all:
            print(f"✅ Telegram: sent {len(chunks)} message(s)")
        return ok_all

    def send_detailed_scan_report(
        self,
        results: List[TradeSignal],
        market_name: str,
        risk_state: Optional["RiskState"] = None,
        include_guide: bool = True,
        include_full_top_report: bool = True,
    ) -> bool:
        """Send the same detailed scan report as the console (rankings, table, guide, full signal)."""
        from scan_report import format_detailed_scan_report

        body = format_detailed_scan_report(
            results,
            market_name,
            risk_state=risk_state,
            include_guide=include_guide,
            include_full_top_report=include_full_top_report,
        )
        title = f"📊 Detailed scan — {market_name}\n\n"
        return self.send_plain_text(title + body)

    def format_signal_message(
        self, 
        signal: TradeSignal, 
        market_name: str,
        include_timestamp: bool = True
    ) -> str:
        """
        Format a TradeSignal as a Telegram message.
        
        Args:
            signal: The TradeSignal object
            market_name: "India Equity" or "Crypto"
            include_timestamp: Include execution time
            
        Returns:
            Formatted message string
        """
        # Emoji based on signal type
        emoji = {
            SignalType.BUY: "🟢",
            SignalType.SELL: "🔴",
            SignalType.HOLD: "🟡",
        }.get(signal.signal, "⚪")

        # Build the message
        lines = [
            f"*{emoji} TRADING SIGNAL ALERT*",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"*Asset:* `{signal.asset}` ({market_name})",
            f"*Signal:* {emoji} *{signal.signal.value}*",
            f"*Timeframe:* {signal.timeframe.value}",
            f"*Confidence:* {signal.confidence}/10",
            "",
            f"*📊 Entry Zone:* {signal.currency_symbol}{signal.entry_low:,.2f} – {signal.currency_symbol}{signal.entry_high:,.2f}",
            f"*🛡️ Stop Loss:* {signal.currency_symbol}{signal.stop_loss:,.2f} ({signal.risk_pct}%)",
            f"*🎯 Target 1:* {signal.currency_symbol}{signal.target_1:,.2f} (R:R = 1:{signal.rr_t1})",
            f"*🎯 Target 2:* {signal.currency_symbol}{signal.target_2:,.2f} (R:R = 1:{signal.rr_t2})",
            "",
            f"*❌ Invalidation:* {signal.invalidation}",
            "",
        ]

        # Add reasoning
        if signal.reasoning_technical:
            lines.append("*📈 Technical Reasons:*")
            for i, reason in enumerate(signal.reasoning_technical[:3], 1):
                lines.append(f"  {i}. {reason}")
            lines.append("")

        if signal.reasoning_fundamental:
            lines.append(f"*📰 Fundamental:* {signal.reasoning_fundamental}")

        # Add risk notes
        if signal.risk_notes:
            lines.append("")
            lines.append("*⚠️ Risk Notes:*")
            for note in signal.risk_notes:
                lines.append(f"  • {note}")

        # Timestamp
        if include_timestamp:
            timestamp = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).strftime(
                "%Y-%m-%d %I:%M %p IST"
            )
            lines.append("")
            lines.append(f"_Generated: {timestamp}_")

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚡ *Trading Signal Analyzer*")

        return "\n".join(lines)

    def should_alert(self, symbol: str, cooldown_seconds: int = 300) -> bool:
        """
        Check if we should send an alert for this symbol (prevents spam).
        
        Args:
            symbol: Asset symbol
            cooldown_seconds: Minimum seconds between alerts for same symbol
            
        Returns:
            True if alert should be sent, False if recently alerted
        """
        import time
        
        current_time = time.time()
        last_time = self._last_signal_time.get(symbol, 0)
        
        if current_time - last_time >= cooldown_seconds:
            self._last_signal_time[symbol] = current_time
            return True
        return False

    def send_signal_alert(
        self, 
        signal: TradeSignal, 
        market_name: str,
        force: bool = False
    ) -> bool:
        """
        Send a trading signal alert to Telegram.
        
        Args:
            signal: The TradeSignal to alert about
            market_name: "India Equity" or "Crypto"
            force: Override cooldown and send anyway
            
        Returns:
            True if alert was sent
        """
        # Only alert for actionable signals (BUY/SELL), not HOLD
        if signal.signal == SignalType.HOLD and not force:
            return False
        
        # Check cooldown (5 minutes default)
        if not force and not self.should_alert(signal.asset, cooldown_seconds=300):
            return False
            
        message = self.format_signal_message(signal, market_name)
        return self.send_message(message)

    def send_scan_summary(
        self,
        results: List[TradeSignal],
        market_name: str,
        buy_count: int,
        sell_count: int,
        hold_count: int
    ) -> bool:
        """
        Send a summary of watchlist scan results.
        
        Args:
            results: List of TradeSignal objects
            market_name: Market type name
            buy_count: Number of BUY signals
            sell_count: Number of SELL signals
            hold_count: Number of HOLD signals
            
        Returns:
            True if message sent successfully
        """
        timestamp = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).strftime(
            "%Y-%m-%d %I:%M %p IST"
        )
        
        # Find top signals
        actionable = [r for r in results if r.signal != SignalType.HOLD]
        top_signal = None
        if actionable:
            top_signal = max(actionable, key=lambda s: s.confidence)
        
        lines = [
            f"*📊 WATCHLIST SCAN COMPLETE*",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            f"*Time:* {timestamp}",
            f"*Market:* {market_name}",
            f"*Assets Scanned:* {len(results)}",
            "",
            f"*📈 Summary:*",
            f"  🟢 BUY: {buy_count}",
            f"  🔴 SELL: {sell_count}",
            f"  🟡 HOLD: {hold_count}",
        ]
        
        if top_signal:
            emoji = "🟢" if top_signal.signal == SignalType.BUY else "🔴"
            lines.extend([
                "",
                f"*🏆 TOP SIGNAL:* {emoji} {top_signal.asset}",
                f"   Signal: *{top_signal.signal.value}*",
                f"   Entry: {top_signal.currency_symbol}{top_signal.entry_mid:,.2f}",
                f"   SL: {top_signal.currency_symbol}{top_signal.stop_loss:,.2f}",
                f"   Confidence: {top_signal.confidence}/10",
            ])
        elif buy_count == 0 and sell_count == 0:
            lines.extend([
                "",
                "⚠️ *No actionable signals*",
                "Market appears to be in consolidation.",
                "Waiting for clearer setup...",
            ])
        
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚡ *Trading Signal Analyzer*")
        
        return self.send_message("\n".join(lines))

    def send_error_alert(self, error_message: str) -> bool:
        """Send an error alert."""
        lines = [
            "⚠️ *ERROR ALERT*",
            "━━━━━━━━━━━━━━━━━━━━━━",
            f"*{error_message}*",
            "",
            f"_Time: {datetime.datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y-%m-%d %I:%M %p IST')}_",
        ]
        return self.send_message("\n".join(lines))

    def test_connection(self) -> bool:
        """Test the Telegram bot connection."""
        if not self.is_configured():
            print("⚠️ Telegram not configured - cannot test connection")
            return False
        
        try:
            url = f"{self.api_url}/getMe"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                bot_info = response.json()
                print(f"✅ Telegram bot connected: @{bot_info['result']['username']}")
                return True
            else:
                print(f"❌ Telegram connection failed: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Telegram connection error: {e}")
            return False


# Singleton instance
_notifier = None

def get_notifier() -> TelegramNotifier:
    """Get or create the Telegram notifier instance."""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


def send_telegram_alert(signal: TradeSignal, market_name: str) -> bool:
    """Convenience function to send a signal alert."""
    notifier = get_notifier()
    return notifier.send_signal_alert(signal, market_name)


def send_scan_alert(
    results: List[TradeSignal],
    market_name: str,
    buy_count: int,
    sell_count: int,
    hold_count: int,
    risk_state: Optional["RiskState"] = None,
) -> bool:
    """Send full detailed scan (rankings, entry table, guide, top signal) to Telegram."""
    notifier = get_notifier()
    return notifier.send_detailed_scan_report(
        results,
        market_name,
        risk_state=risk_state,
        include_guide=True,
        include_full_top_report=True,
    )


if __name__ == "__main__":
    # Test the notifier
    notifier = TelegramNotifier()
    
    if notifier.is_configured():
        print("Testing Telegram connection...")
        notifier.test_connection()
        print("\nSending test message...")
        notifier.send_message("🧪 *Test Message*\n\nTrading Signal Analyzer is running!")
    else:
        print("Telegram not configured!")
        print("Set these environment variables:")
        print("  TELEGRAM_BOT_TOKEN=your_bot_token")
        print("  TELEGRAM_CHAT_ID=your_chat_id")
        print("\nOr pass them to TelegramNotifier(token='...', chat_id='...')")
