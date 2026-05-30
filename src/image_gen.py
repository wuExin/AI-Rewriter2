"""
豆包生图模块
通过 Selenium 自动化调用豆包网页版生图，JS 注入去水印，下载无水印原图
"""
import os
import re
import time
import random

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from loguru import logger

WATERMARK_REMOVER_SCRIPT = """
(function(){
    'use strict';
    function findAllKeysInJson(obj, key) {
        const results = [];
        function search(current) {
            if (current && typeof current === 'object') {
                if (!Array.isArray(current) &&
                    Object.prototype.hasOwnProperty.call(current, key)) {
                    results.push(current[key]);
                }
                const items = Array.isArray(current) ? current : Object.values(current);
                for (const item of items) { search(item); }
            }
        }
        search(obj);
        return results;
    }
    let _parse = JSON.parse;
    JSON.parse = function(data) {
        let jsonData = _parse(data);
        if (!data.match('creations')) return jsonData;
        let creations = findAllKeysInJson(jsonData, 'creations');
        if (creations.length > 0) {
            creations.forEach((creation) => {
                creation.map((item) => {
                    const rawUrl = item.image.image_ori_raw.url;
                    item.image.image_ori.url = rawUrl;
                    return item;
                });
            });
        }
        return jsonData;
    };
})();
"""

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.7151.120 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.7151.120 Safari/537.36 Edg/114.0.1823.67",
]


class DoubaoImageGenerator:
    """豆包生图生成器"""

    def __init__(self, output_dir: str, chromedriver_dir: str = "./chromedriver", timeout: int = 120):
        self.output_dir = output_dir
        self.chromedriver_dir = os.path.abspath(chromedriver_dir)
        self.timeout = timeout
        self.user_data_dir = os.path.join(self.chromedriver_dir, "user_data")

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.user_data_dir, exist_ok=True)

    def generate(self, title: str, filename: str = None) -> str | None:
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title[:50])
        if not filename:
            filename = f"{safe_title}_封面.png"

        prompt = (
            f"根据下面标题，要求只生成一张照片，要求符合标题大意，"
            f"影视化场景，亚洲人，照片中不要出现文字，尺寸1200*800，"
            f"标题：【{title}】"
        )

        driver = None
        try:
            driver = self._create_driver()
            self._open_doubao(driver)
            self._send_prompt(driver, prompt)
            image_urls = self._wait_for_images(driver)

            if not image_urls:
                logger.warning("[豆包生图] 未检测到生成的图片")
                return None

            filepath = os.path.join(self.output_dir, filename)
            saved = self._download_image(driver, image_urls[0], filepath)

            if saved:
                # 保存原图，处理后的图片用新文件名
                raw_path = os.path.join(self.output_dir, f"{safe_title}_原图.png")
                Image.open(filepath).save(raw_path)
                self._remove_watermark(filepath)
                logger.info(f"[豆包生图] 原图已保存: {raw_path}")
                logger.info(f"[豆包生图] 封面图已保存: {filepath}")
                return filepath
            return None

        except WebDriverException as e:
            logger.warning(f"[豆包生图] 浏览器错误: {str(e)[:200]}")
            return None
        except Exception as e:
            logger.warning(f"[豆包生图] 生成失败: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _create_driver(self):
        options = Options()
        options.add_argument(f"--user-data-dir={self.user_data_dir}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

        cd_path = os.path.join(self.chromedriver_dir, "chromedriver.exe")
        if os.path.exists(cd_path):
            return webdriver.Chrome(service=Service(cd_path), options=options)
        return webdriver.Chrome(options=options)

    @staticmethod
    def _dismiss_modals(driver):
        try:
            if driver.find_elements(By.CSS_SELECTOR, ".semi-modal-wrap"):
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(0.5)
        except Exception:
            pass

    @staticmethod
    def _is_logged_in(driver) -> bool:
        """检查是否已登录"""
        try:
            avatars = driver.find_elements(By.CSS_SELECTOR,
                '[class*="userAvatar"], [class*="UserAvatar"], [class*="avatar"][class*="header"]')
            for av in avatars:
                if av.is_displayed():
                    return True
            login_btns = driver.find_elements(By.XPATH,
                '//span[contains(text(),"登录") and not(contains(text(),"下载"))]')
            for btn in login_btns:
                if btn.is_displayed() and btn.text.strip() == "登录":
                    return False
            for c in driver.get_cookies():
                if 'session_id' in c['name'].lower() or 'passport' in c['name'].lower():
                    return True
            return False
        except Exception:
            return False

    def _wait_for_login(self, driver, timeout=120) -> bool:
        """等待用户完成登录"""
        time.sleep(5)
        if self._is_logged_in(driver):
            logger.info("[豆包生图] 已检测到登录状态")
            return True
        logger.warning(f"[豆包生图] 未登录，请在浏览器中手动登录（最长等待 {timeout} 秒）...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._is_logged_in(driver):
                logger.info("[豆包生图] 登录成功！")
                self._dismiss_modals(driver)
                return True
            time.sleep(3)
        return False

    def _open_doubao(self, driver):
        driver.get("https://www.doubao.com/chat/")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea.semi-input-textarea"))
        )
        time.sleep(8)
        self._dismiss_modals(driver)

        if not self._wait_for_login(driver):
            raise RuntimeError("豆包登录超时，请重新运行并手动登录")

        driver.execute_script(WATERMARK_REMOVER_SCRIPT)

    def _send_prompt(self, driver, prompt: str):
        for attempt in range(3):
            try:
                self._dismiss_modals(driver)
                textarea = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "textarea.semi-input-textarea"))
                )
                textarea.click()
                time.sleep(0.5)
                textarea.clear()
                textarea.send_keys(prompt)
                time.sleep(0.5)

                try:
                    wrapper = driver.find_element(By.CSS_SELECTOR, '.send-btn-wrapper')
                    wrapper.find_element(By.TAG_NAME, 'button').click()
                except Exception:
                    textarea.send_keys(Keys.ENTER)
                time.sleep(1)
                return
            except Exception:
                if attempt < 2:
                    time.sleep(3)
                else:
                    raise

    def _wait_for_images(self, driver) -> list:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            urls = self._get_image_urls(driver)
            if urls:
                time.sleep(5)
                return self._get_image_urls(driver)
            time.sleep(5)
        return []

    @staticmethod
    def _get_image_urls(driver) -> list:
        try:
            return driver.execute_script("""
                var imgs = document.querySelectorAll('img');
                var r = [], seen = {};
                for (var i = 0; i < imgs.length; i++) {
                    var s = imgs[i].src || '';
                    if (s.indexOf('flow-imagex') !== -1 && !seen[s]) { seen[s] = 1; r.push(s); }
                }
                return r;
            """) or []
        except Exception:
            return []

    @staticmethod
    def _download_image(driver, url: str, filepath: str) -> bool:
        # canvas data URL
        if url.startswith("data:"):
            try:
                import base64
                data = url.split(",", 1)[1]
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(data))
                return True
            except Exception as e:
                logger.warning(f"[豆包生图] base64保存失败: {e}")
                return False

        session = requests.Session()
        for c in driver.get_cookies():
            session.cookies.set(c['name'], c['value'])

        try:
            resp = session.get(url, timeout=30, headers={'Referer': 'https://www.doubao.com/'})
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                return True
        except Exception as e:
            logger.warning(f"[豆包生图] 下载失败: {e}")
        return False

    @staticmethod
    def _remove_watermark(filepath: str):
        """检测左上角水印区域并裁剪"""
        try:
            img = cv2.imdecode(np.fromfile(filepath, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return
            h, w = img.shape[:2]

            # 只扫描左上角 20% 区域（水印固定在左上）
            lw = int(w * 0.2)
            scan_h = max(int(h * 0.12), 30)
            gray = cv2.cvtColor(img[:scan_h, :lw], cv2.COLOR_BGR2GRAY)

            # 每行中像素值 >= 200 的数量（水印像素偏亮）
            row_bright = [(gray[row] >= 200).sum() for row in range(scan_h)]

            # 水印行特征：有 >= 5 个亮像素
            watermark_rows = [i for i, c in enumerate(row_bright) if c >= 5]
            if not watermark_rows:
                return

            # 分组（间隔 <= 3 行的合并）
            groups = [[watermark_rows[0]]]
            for i in range(1, len(watermark_rows)):
                if watermark_rows[i] - groups[-1][-1] <= 3:
                    groups[-1].append(watermark_rows[i])
                else:
                    groups.append([watermark_rows[i]])

            # 取最长的组
            longest = max(groups, key=len)
            watermark_bottom = longest[-1] + 1

            if watermark_bottom > 0 and watermark_bottom < h - 10:
                cropped = img[watermark_bottom:, :]
                cv2.imencode('.png', cropped)[1].tofile(filepath)
                logger.info(f"[豆包生图] 裁剪水印: 去掉顶部 {watermark_bottom} 像素, "
                            f"原图 {w}x{h} → {w}x{h - watermark_bottom}")
        except Exception as e:
            logger.warning(f"[豆包生图] 水印去除失败: {e}")