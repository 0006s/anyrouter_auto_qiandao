#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AnyRouter 自动签到脚本 (独立版)
支持多账号，使用 cron / Windows 任务计划程序 定时执行
签到结果通过邮件通知
"""

import json
import logging
import os
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Tuple

# 尝试导入 cloudscraper 以处理反爬虫挑战
try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except Exception:
    HAS_CLOUDSCRAPER = False
    cloudscraper = None  # type: ignore

# 尝试导入 playwright 以处理 JavaScript 挑战
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except Exception:
    HAS_PLAYWRIGHT = False
    sync_playwright = None  # type: ignore

import requests



# ============ 配置 ============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "checkin.log")

DEFAULT_BASE_URL = "https://anyrouter.zhx47.deno.net"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# ============ 日志配置 ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


# ============ 签到客户端 ============
class AnyRouterClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        # 优先使用 cloudscraper 以绕过反爬虫挑战
        if HAS_CLOUDSCRAPER:
            self.session = cloudscraper.create_scraper()
            logger.info("使用 cloudscraper 会话以处理反爬虫挑战")
        else:
            self.session = requests.Session()
            logger.info("使用标准 requests 会话")
        self.session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

    def _extract_cookies_from_playwright(self, page) -> str:
        """从Playwright页面提取cookie字符串"""
        cookies = page.context.cookies()
        cookie_parts = []
        for cookie in cookies:
            cookie_parts.append(f"{cookie['name']}={cookie['value']}")
        return "; ".join(cookie_parts)

    def sign_in(self, cookie: str) -> Tuple[bool, str]:
        """
        执行签到，处理JavaScript挑战

        返回: (成功与否, 消息)
        """
        url = f"{self.base_url}/api/user/sign_in"

        # 如果有Playwright，尝试使用它处理JavaScript挑战
        if HAS_PLAYWRIGHT:
            try:
                logger.info("尝试使用Playwright处理JavaScript挑战...")
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent=DEFAULT_USER_AGENT,
                        ignore_https_errors=True
                    )
                    page = context.new_page()

                    logger.info("访问签到端点以触发JavaScript执行...")
                    response = page.goto(url, wait_until="networkidle", timeout=30000)

                    page.wait_for_timeout(2000)

                    new_cookie = self._extract_cookies_from_playwright(page)
                    logger.info(f"获取到新cookie: {new_cookie[:100]}...")

                    # 合并原始cookie和新获取的cookie
                    cookie_dict = {}
                    for part in cookie.split(";"):
                        part = part.strip()
                        if "=" in part:
                            key, value = part.split("=", 1)
                            cookie_dict[key.strip()] = value.strip()
                    for part in new_cookie.split(";"):
                        part = part.strip()
                        if "=" in part:
                            key, value = part.split("=", 1)
                            cookie_dict[key.strip()] = value.strip()
                    # 更新cookie变量，以便传统方法使用
                    cookie = "; ".join([f"{k}={v}" for k, v in cookie_dict.items()])

                    browser.close()
            except Exception as e:
                logger.warning(f"Playwright处理失败，回退到传统方法: {e}")
                # 回退到传统方法

        # 传统方法（cloudscraper或requests）
        logger.info("使用传统方法进行签到...")
        headers = {"Cookie": cookie}

        try:
            resp = self.session.post(url, headers=headers, timeout=30)
        except Exception as e:
            return False, f"请求异常: {e}"

        if resp.status_code == 401:
            return False, "Cookie 无效(401)，请更新"
        if resp.status_code != 200:
            return False, f"签到失败 HTTP {resp.status_code}: {resp.text}"

        try:
            data = resp.json()
        except Exception:
            return False, f"响应非JSON: {resp.text}"

        if not isinstance(data, dict):
            return True, f"返回: {data}"

        success = data.get("success")
        message = data.get("message", "")

        if success is True:
            if message.strip():
                return True, message.strip()
            return True, "今日已签到"

        if success is False:
            if message.strip():
                return False, message.strip()
            return False, f"签到失败: {data}"

        return True, f"返回: {data}"


# ============ 邮件通知 ============
def send_email(config: Dict, subject: str, body: str) -> bool:
    """发送邮件通知，返回是否成功"""
    email_cfg = config.get("email", {})
    if not email_cfg.get("enabled", False):
        logger.info("邮件通知未启用，跳过发送")
        return True

    smtp_server = email_cfg.get("smtp_server", "smtp.qq.com")
    smtp_port = email_cfg.get("smtp_port", 465)
    smtp_user = email_cfg.get("smtp_user", "")
    smtp_pass = email_cfg.get("smtp_pass", "")
    recipient = email_cfg.get("recipient", "")

    if not all([smtp_user, smtp_pass, recipient]):
        logger.warning("邮件配置不完整，跳过发送")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        logger.info(f"正在发送邮件到 {recipient}...")
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [recipient], msg.as_string())

        logger.info("邮件发送成功")
        return True
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")
        return False


# ============ 配置加载 ============
def load_config() -> Dict:
    """加载配置文件"""
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"配置文件不存在: {CONFIG_FILE}")
        logger.info("请复制 config.example.json 为 config.json 并填入账号信息")
        sys.exit(1)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"配置文件格式错误: {e}")
        sys.exit(1)


# ============ 主函数 ============
def main():
    logger.info("=" * 50)
    logger.info(f"AnyRouter 自动签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    config = load_config()
    accounts: List[Dict] = config.get("accounts", [])
    base_url = config.get("base_url", DEFAULT_BASE_URL)

    if not accounts:
        logger.warning("未配置任何账号，请检查 config.json")
        return

    logger.info(f"共 {len(accounts)} 个账号待签到")
    logger.info(f"签到地址: {base_url}")

    client = AnyRouterClient(base_url)

    success_count = 0
    fail_count = 0
    results = []  # 记录每个账号的签到结果，用于邮件通知

    for i, account in enumerate(accounts, start=1):
        name = account.get("name", f"账号{i}")
        cookie = account.get("cookie", "").strip()

        logger.info(f"")
        logger.info(f"-----> [{i}/{len(accounts)}] {name}")

        if not cookie:
            logger.warning(f" Cookie 为空，跳过")
            fail_count += 1
            results.append({"name": name, "ok": False, "msg": "Cookie 为空，跳过"})
            continue

        ok, result = client.sign_in(cookie)

        if ok:
            logger.info(f" SUCCESS: {result}")
            success_count += 1
            results.append({"name": name, "ok": True, "msg": result})
        else:
            logger.error(f" FAILED: {result}")
            fail_count += 1
            results.append({"name": name, "ok": False, "msg": result})

    logger.info(f"")
    logger.info("=" * 50)
    logger.info(f"签到完成: 成功 {success_count}, 失败 {fail_count}")
    logger.info("=" * 50)

    # 发送邮件通知
    email_cfg = config.get("email", {})
    if email_cfg.get("enabled", False):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_icon = "✅" if fail_count == 0 else "⚠️"
        subject = f"{status_icon} AnyRouter签到报告 - {now_str}"

        lines = [
            f"📅 签到时间: {now_str}",
            f"📊 汇总: 成功 {success_count}, 失败 {fail_count}",
            "",
            "📋 详细结果:",
        ]
        for r in results:
            icon = "✅" if r["ok"] else "❌"
            lines.append(f"  {icon} {r['name']}: {r['msg']}")
        lines.append("")
        lines.append("—— 由 AnyRouter 自动签到脚本发送")

        body = "\n".join(lines)
        send_email(config, subject, body)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n发生未预期的错误: {e}")
        sys.exit(1)
