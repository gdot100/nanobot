"""Snapchat channel implementation using headed Playwright Chrome."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from typing import TYPE_CHECKING, Any

from loguru import logger
from pydantic import Field

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import Base

PLAYWRIGHT_AVAILABLE = importlib.util.find_spec("playwright") is not None
if TYPE_CHECKING:
    from playwright.async_api import async_playwright

if PLAYWRIGHT_AVAILABLE:
    from playwright.async_api import async_playwright

_SNAPCHAT_WEB_URL = "https://www.snapchat.com/web"
_POLL_INTERVAL_S = 5
_MAX_MESSAGE_CHARS = 12000


class SnapchatConfig(Base):
    """Snapchat channel configuration."""

    enabled: bool = False
    allow_from: list[str] = Field(default_factory=list)
    poll_interval_s: int = _POLL_INTERVAL_S
    headless: bool = False  # Default to headed mode so user can see browser and handle login
    user_data_dir: str = ""  # Chrome profile directory for persistent sessions
    max_message_chars: int = _MAX_MESSAGE_CHARS
    connect_to_chrome: bool = False  # Connect to existing Chrome via CDP
    chrome_debugging_port: int = 9222  # Chrome remote debugging port


class SnapchatChannel(BaseChannel):
    """
    Snapchat channel using headed Playwright Chrome.

    Monitors Snapchat Web (snapchat.com/web) for incoming chat messages
    and sends replies through the web interface.

    The browser runs in headed mode by default so users can:
    - See the browser window
    - Handle login/2FA manually if needed
    - Verify the automation is working

    Session persistence is achieved through Chrome user data directory.
    """

    name = "snapchat"
    display_name = "Snapchat"

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return SnapchatConfig().model_dump(by_alias=True)

    def __init__(self, config: Any, bus: MessageBus):
        if isinstance(config, dict):
            config = SnapchatConfig.model_validate(config)
        super().__init__(config, bus)
        self.config: SnapchatConfig = config
        self._browser = None
        self._page = None
        self._context = None
        self._known_messages: set[str] = set()
        self._current_chat_user: str | None = None
        self._playwright = None
        self._cdp_session = None
        self._notification_event = asyncio.Event()

    async def login(self, force: bool = False) -> bool:
        """
        Launch headed Chrome and let user log in to Snapchat Web.

        The browser window is visible so the user can handle login/2FA.
        Session is persisted via Chrome user data directory.
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error(
                "Snapchat channel requires Playwright. Install with: pip install nanobot[snapchat] && playwright install chromium"
            )
            return False
        playwright = await self._get_playwright()
        try:
            await self._launch_browser(playwright, force=force)
        except Exception as e:
            logger.error("Failed to launch Snapchat browser: {}", e)
            return False

        if not self._page:
            return False

        logger.info(
            "Snapchat browser launched. Please log in at Snapchat Web if not already logged in."
        )
        logger.info("Waiting for Snapchat Web to load...")

        try:
            await self._page.goto(_SNAPCHAT_WEB_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.warning("Could not navigate to Snapchat Web: {}", e)

        # Wait for user to log in - check for chat-related elements
        max_wait = 300  # 5 minutes max
        waited = 0
        while waited < max_wait:
            try:
                # Check if we're logged in by looking for chat sidebar
                chat_elements = await self._page.query_selector(
                    '[data-testid="chat-sidebar"], .chat-list, [class*="chat"]'
                )
                if chat_elements:
                    logger.info("Snapchat Web appears to be loaded and logged in.")
                    return True
            except Exception:
                pass

            # Also check if we're still on login page
            current_url = self._page.url
            if "login" in current_url.lower() or "accounts" in current_url.lower():
                logger.info(
                    "Waiting for login... ({}s elapsed, {}s remaining)", waited, max_wait - waited
                )
            else:
                logger.info("Snapchat Web loaded ({}s elapsed)", waited)
                return True

            await asyncio.sleep(5)
            waited += 5

        logger.warning("Login wait timed out. You may need to log in manually.")
        return True

    async def start(self) -> None:
        """Start monitoring Snapchat Web for incoming messages."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error(
                "Snapchat channel requires Playwright. Install with: pip install nanobot[snapchat] && playwright install chromium"
            )
            return
        playwright = await self._get_playwright()

        try:
            await self._launch_browser(playwright)
        except Exception as e:
            logger.error("Failed to launch Snapchat browser: {}", e)
            return

        if not self._page:
            logger.error("Snapchat page not available")
            return

        self._running = True

        try:
            await self._page.goto(_SNAPCHAT_WEB_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning("Could not navigate to Snapchat Web: {}", e)

        logger.info("Starting Snapchat channel (headed Playwright Chrome mode)...")

        await self._setup_notification_listener()

        poll_interval = max(3, int(self.config.poll_interval_s))

        while self._running:
            try:
                new_messages = await self._poll_for_messages()
                for msg in new_messages:
                    await self._handle_message(
                        sender_id=msg["sender"],
                        chat_id=msg["sender"],
                        content=msg["content"],
                        metadata=msg.get("metadata", {}),
                    )
            except Exception as e:
                logger.error("Snapchat polling error: {}", e)
                try:
                    if self._page:
                        await self._page.reload()
                except Exception:
                    logger.warning("Page reload failed, will retry on next poll")

            try:
                await asyncio.wait_for(self._notification_event.wait(), timeout=poll_interval)
                self._notification_event.clear()
            except asyncio.TimeoutError:
                pass

    async def stop(self) -> None:
        """Stop the Snapchat channel and close browser."""
        self._running = False

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
            self._page = None
            self._context = None

        await self._close_playwright()

        logger.info("Snapchat channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Snapchat Web."""
        if not self._page:
            logger.warning("Snapchat page not available, cannot send message")
            return

        chat_id = msg.chat_id
        content = msg.content or ""

        if not content:
            return

        # Truncate if too long
        if len(content) > self.config.max_message_chars:
            content = content[: self.config.max_message_chars]

        try:
            # Navigate to the chat with the user
            await self._open_chat(chat_id)

            # Type and send the message
            await self._send_chat_message(content)

            logger.info("Sent Snapchat message to {}: {}", chat_id, content[:50])
        except Exception as e:
            logger.error("Error sending Snapchat message to {}: {}", chat_id, e)
            raise

    async def _get_playwright(self):
        """Get Playwright instance."""
        if self._playwright:
            return self._playwright
        self._playwright = await async_playwright().start()
        return self._playwright

    async def _close_playwright(self):
        """Close Playwright instance."""
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def _launch_browser(self, playwright, force: bool = False) -> None:
        """Launch headed Chrome browser with optional persistent session or connect to existing."""
        # Connect to existing Chrome via CDP if configured
        if self.config.connect_to_chrome:
            logger.info(
                "Connecting to existing Chrome via CDP on port {}...",
                self.config.chrome_debugging_port,
            )
            try:
                self._browser = await playwright.chromium.connect_over_cdp(
                    f"http://localhost:{self.config.chrome_debugging_port}"
                )
                self._context = (
                    self._browser.contexts[0]
                    if self._browser.contexts
                    else await self._browser.new_context()
                )
                self._page = (
                    self._context.pages[0]
                    if self._context.pages
                    else await self._context.new_page()
                )
                logger.info("Connected to existing Chrome browser")
                return
            except Exception as e:
                logger.warning(
                    "Failed to connect to Chrome via CDP: {}. Falling back to launching new browser.",
                    e,
                )

        launch_args = {
            "headless": self.config.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }

        # Use persistent context if user_data_dir is configured
        user_data_dir = self.config.user_data_dir
        if user_data_dir:
            os.makedirs(user_data_dir, exist_ok=True)
            self._context = await playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                **launch_args,
            )
            self._browser = self._context
            self._page = (
                self._context.pages[0] if self._context.pages else await self._context.new_page()
            )
        else:
            self._browser = await playwright.chromium.launch(**launch_args)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            self._page = await self._context.new_page()

        # Anti-detection: remove webdriver property
        await self._page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.snapchatNotificationDetected = function() {
                window.dispatchEvent(new CustomEvent('snapchat-notification'));
            };
            """
        )

    async def _setup_notification_listener(self) -> None:
        """Set up CDP listeners to detect new Snapchat activity."""
        if not self._browser:
            return

        try:
            page = (
                self._browser.contexts[0].pages[0]
                if self._browser.contexts and self._browser.contexts[0].pages
                else None
            )
            if not page:
                return

            self._cdp_session = await page.new_cdp_session(page)

            async def on_title_changed(event: dict):
                title = event.get("params", {}).get("title", "")
                if title and (
                    "(" in title or "message" in title.lower() or "snap" in title.lower()
                ):
                    logger.info("Page title changed (potential notification): {}", title)
                    self._notification_event.set()

            await self._cdp_session.send("Page.enable")
            self._cdp_session.on("Page.titleDidChange", on_title_changed)

            logger.info("CDP page listener enabled for title changes")
        except Exception as e:
            logger.warning("Failed to set up CDP notification listener: {}", e)

        try:
            if self._page:
                self._page.on(
                    "console",
                    lambda msg: (
                        self._notification_event.set()
                        if "notification" in msg.text.lower()
                        else None
                    ),
                )

                await self._page.evaluate(
                    """
                    () => {
                        window.addEventListener('snapchat-notification', () => {
                            console.log('SNAPCHAT_NOTIFICATION_DETECTED');
                        });
                        const observer = new MutationObserver((mutations) => {
                            for (const mutation of mutations) {
                                const addedNodes = mutation.addedNodes;
                                for (const node of addedNodes) {
                                    if (node.nodeType === Node.ELEMENT_NODE) {
                                        const text = node.innerText || '';
                                        if (text.includes('unread') || text.includes('new') || text.match(/\\(\\d+\\)/)) {
                                            window.dispatchEvent(new CustomEvent('snapchat-notification', { detail: text }));
                                        }
                                    }
                                }
                                if (mutation.target.nodeType === Node.ELEMENT_NODE) {
                                    const target = mutation.target;
                                    const badge = target.querySelector('[class*="badge"], [class*="unread"], [class*="count"]');
                                    if (badge && (badge.innerText || '').trim()) {
                                        window.dispatchEvent(new CustomEvent('snapchat-notification'));
                                    }
                                }
                            }
                        });
                        observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'aria-label'] });
                    }
                    """
                )
                logger.info("DOM mutation observer enabled for notification detection")
        except Exception as e:
            logger.warning("Failed to set up DOM observer: {}", e)

    async def _poll_for_messages(self) -> list[dict[str, Any]]:
        """
        Poll Snapchat Web for new messages.

        Since Snapchat Web doesn't expose a simple API, we use DOM scraping
        to detect new chat messages in the sidebar and active conversation.
        """
        new_messages = []

        try:
            # Check for unread indicators in chat sidebar
            unread_chats = await self._get_unread_chats()

            for chat_user in unread_chats:
                # Open the chat to read messages
                await self._open_chat(chat_user)
                await asyncio.sleep(1)  # Wait for messages to load

                # Extract recent messages
                messages = await self._extract_chat_messages()

                for msg in messages:
                    msg_id = msg.get("id", "")
                    if msg_id and msg_id not in self._known_messages:
                        self._known_messages.add(msg_id)

                        # Cap the set size
                        if len(self._known_messages) > 1000:
                            self._known_messages = set(list(self._known_messages)[-500:])

                        sender = msg.get("sender", chat_user)
                        content = msg.get("content", "")

                        if content and sender != "self":
                            new_messages.append(
                                {
                                    "sender": chat_user,
                                    "content": content,
                                    "metadata": {
                                        "snapchat_message_id": msg_id,
                                        "timestamp": msg.get("timestamp", ""),
                                    },
                                }
                            )

                # Mark as current chat
                self._current_chat_user = chat_user

        except Exception as e:
            logger.warning("Error polling for Snapchat messages: {}", e)

        return new_messages

    async def _get_unread_chats(self) -> list[str]:
        """Extract list of chats with unread messages from the sidebar."""
        try:
            # Try multiple selectors as Snapchat's DOM structure may change
            selectors = [
                '[data-testid="chat-list-item"]',
                ".chat-list-item",
                '[class*="ConversationListItem"]',
                '[class*="chat-item"]',
                'nav [class*="list"] > [class*="item"]',
            ]

            for selector in selectors:
                elements = await self._page.query_selector_all(selector)
                if elements:
                    chats = []
                    for el in elements:
                        # Check for unread indicator
                        has_unread = await self._has_unread_indicator(el)
                        if has_unread:
                            name = await self._extract_chat_name(el)
                            if name:
                                chats.append(name)

                    if chats:
                        return chats

                    # If no unread, return empty (no new messages)
                    return []

            # Fallback: try to extract from page text
            return await self._fallback_unread_detection()

        except Exception as e:
            logger.debug("Unread chat detection failed: {}", e)
            return []

    async def _has_unread_indicator(self, element) -> bool:
        """Check if a chat element has an unread message indicator."""
        try:
            # Common unread indicators
            indicators = [
                '[class*="unread"]',
                '[class*="new-message"]',
                '[class*="badge"]',
                ".unread-indicator",
            ]

            for indicator in indicators:
                found = await element.query_selector(indicator)
                if found:
                    return True

            return False
        except Exception:
            return False

    async def _extract_chat_name(self, element) -> str | None:
        """Extract the chat participant name from a sidebar element."""
        try:
            selectors = [
                '[class*="name"]',
                '[class*="display-name"]',
                '[class*="title"]',
                "span",
            ]

            for selector in selectors:
                name_el = await element.query_selector(selector)
                if name_el:
                    text = await name_el.inner_text()
                    text = text.strip()
                    if text and len(text) < 50:
                        return text

            return None
        except Exception:
            return None

    async def _fallback_unread_detection(self) -> list[str]:
        """Fallback method to detect unread chats using page evaluation."""
        try:
            chats = await self._page.evaluate(
                """
                () => {
                    const chats = [];
                    // Try to find chat list items with unread indicators
                    const allElements = document.querySelectorAll('[class*="chat"], [class*="conversation"], [class*="friend"]');
                    for (const el of allElements) {
                        const text = el.innerText || el.textContent || '';
                        const className = el.className || '';
                        if (className.includes('unread') || className.includes('new') || className.includes('badge')) {
                            const nameEl = el.querySelector('[class*="name"], span');
                            if (nameEl && nameEl.innerText) {
                                chats.push(nameEl.innerText.trim());
                            }
                        }
                    }
                    return [...new Set(chats)].slice(0, 10);
                }
                """
            )
            return chats if isinstance(chats, list) else []
        except Exception:
            return []

    async def _open_chat(self, chat_user: str) -> None:
        """Open a chat conversation with the specified user."""
        try:
            # Search for the user in the search bar
            search_selectors = [
                '[data-testid="search-input"]',
                'input[placeholder*="Search"]',
                'input[type="text"]',
                '[class*="search"] input',
            ]

            search_box = None
            for selector in search_selectors:
                search_box = await self._page.query_selector(selector)
                if search_box:
                    break

            if search_box:
                await search_box.click()
                await search_box.fill(chat_user)
                await asyncio.sleep(1)

                # Click on the first search result
                result_selectors = [
                    '[data-testid="search-result"]',
                    ".search-result",
                    '[class*="search-result"]',
                    '[class*="suggestion"]',
                ]

                for selector in result_selectors:
                    result = await self._page.query_selector(selector)
                    if result:
                        await result.click()
                        await asyncio.sleep(1)
                        return

            # Alternative: try clicking on the chat directly from sidebar
            chat_selectors = [
                f'[data-testid="chat-item-{chat_user}"]',
                f'[class*="chat"]:has-text("{chat_user}")',
            ]

            for selector in chat_selectors:
                try:
                    el = await self._page.query_selector(selector)
                    if el:
                        await el.click()
                        await asyncio.sleep(1)
                        return
                except Exception:
                    continue

            logger.warning("Could not open chat with {}", chat_user)

        except Exception as e:
            logger.warning("Error opening chat with {}: {}", chat_user, e)

    async def _send_chat_message(self, content: str) -> None:
        """Type and send a message in the current chat."""
        try:
            # Find the message input field
            input_selectors = [
                '[data-testid="chat-input"]',
                'textarea[placeholder*="Message"]',
                'input[placeholder*="Message"]',
                '[contenteditable="true"]',
                '[class*="chat-input"]',
                '[class*="message-input"]',
            ]

            input_field = None
            for selector in input_selectors:
                try:
                    input_field = await self._page.query_selector(selector)
                    if input_field:
                        break
                except Exception:
                    continue

            if not input_field:
                raise RuntimeError("Could not find message input field")

            # Clear and type the message
            await input_field.click()
            await input_field.fill(content)
            await asyncio.sleep(0.5)

            # Send the message (Enter key or send button)
            send_selectors = [
                '[data-testid="send-button"]',
                'button[class*="send"]',
                '[class*="send-button"]',
            ]

            send_button = None
            for selector in send_selectors:
                try:
                    send_button = await self._page.query_selector(selector)
                    if send_button:
                        break
                except Exception:
                    continue

            if send_button:
                await send_button.click()
            else:
                # Fallback: press Enter
                await input_field.press("Enter")

            await asyncio.sleep(1)

        except Exception as e:
            logger.error("Error sending chat message: {}", e)
            raise

    async def _extract_chat_messages(self) -> list[dict[str, Any]]:
        """Extract recent messages from the current chat conversation."""
        try:
            messages = await self._page.evaluate(
                """
                () => {
                    const messages = [];
                    // Try various message container selectors
                    const selectors = [
                        '[data-testid="chat-message"]',
                        '[class*="message"]',
                        '[class*="chat-bubble"]',
                        '[class*="conversation-message"]',
                        'div[class*="Message"]',
                    ];

                    let messageElements = [];
                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            messageElements = Array.from(elements);
                            break;
                        }
                    }

                    for (const el of messageElements.slice(-20)) {
                        const text = (el.innerText || el.textContent || '').trim();
                        const className = el.className || '';
                        const isFromSelf = className.includes('sent') ||
                                          className.includes('outgoing') ||
                                          className.includes('self') ||
                                          className.includes('mine');

                        if (text && text.length > 0) {
                            messages.push({
                                id: el.getAttribute('data-message-id') || el.id || `msg_${Date.now()}_${Math.random()}`,
                                content: text.substring(0, 2000),
                                sender: isFromSelf ? 'self' : 'other',
                                timestamp: new Date().toISOString()
                            });
                        }
                    }

                    return messages;
                }
                """
            )

            return messages if isinstance(messages, list) else []

        except Exception as e:
            logger.debug("Message extraction failed: {}", e)
            return []
