import time
from fastapi import APIRouter
from sqlmodel import func, select

from database.connection import SessionDep
from database.models import Note
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from seleniumbase import SB
from bs4 import BeautifulSoup
import re
import os
import subprocess

router = APIRouter(prefix="/real-estate", tags=["real-estate"])
TZ = ZoneInfo("Europe/Budapest")


BASE_URL = os.getenv("BASE_URL")
# BASE_URL = (
#     "https://ingatlan.com/lista/elado+lakas+nem-berleti-jog+oroszlany+fix-3-szazalek"
# )


def install_chrome_if_needed():
    """Chrome és ChromeDriver telepítése Azure App Service-ben"""
    try:
        # Ellenőrizzük, hogy Chrome telepítve van-e
        result = subprocess.run(
            ["which", "google-chrome"], capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ Chrome már telepítve van")
            return True

        print("📦 Chrome telepítése...")

        # Chrome telepítő parancsok
        commands = [
            "apt-get update",
            "apt-get install -y wget gnupg",
            "wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -",
            "echo 'deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main' >> /etc/apt/sources.list.d/google-chrome.list",
            "apt-get update",
            "apt-get install -y google-chrome-stable",
        ]

        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Hiba a telepítés során: {cmd}")
                print(f"Stderr: {result.stderr}")
                return False

        print("✅ Chrome sikeresen telepítve")
        return True

    except Exception as e:
        print(f"❌ Chrome telepítési hiba: {e}")
        return False


def get_selenium_options():
    """Azure App Service-hez optimalizált opciók"""
    return [
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-plugins",
        "--window-size=1920,1080",
        "--single-process",
        "--disable-web-security",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    ]


@router.post("/create")
def save_real_estate(session: SessionDep):

    def extract_cards(soup: BeautifulSoup):
        items = []
        content_divs = soup.select("div.listing-card-content")
        for i, content_div in enumerate(content_divs, 1):
            row_divs = content_div.find_all("div", class_="row")
            real_estate_data = []
            for row in row_divs:
                for span in row.find_all("span"):
                    text = span.get_text(strip=True)
                    if text:
                        real_estate_data.append(text)
            if real_estate_data:
                items.append({"real_estate_index": i, "data": real_estate_data})
        return items

    def get_page_count(soup: BeautifulSoup) -> int:
        # 1) eredeti számláló (pl. "1 / 2")
        for div in soup.find_all("div", class_="col-6 text-center"):
            span = div.find("span", class_="text-gray-200")
            if span:
                m = re.search(r"/\s*(\d+)", span.get_text(strip=True))
                if m:
                    return int(m.group(1))
        # 2) fallback: lapozó linkek "?page=N" alapján
        max_page = 1
        for a in soup.find_all("a", href=True):
            m = re.search(r"[?&]page=(\d+)", a["href"])
            if m:
                max_page = max(max_page, int(m.group(1)))
        return max_page

    def debug_page_content(sb):
        """Debug információk gyűjtése"""
        try:
            title = sb.get_title()
            print(f"🔍 Oldal címe: {title}")

            url = sb.get_current_url()
            print(f"🔍 Aktuális URL: {url}")

            # Ellenőrizzük, hogy van-e CAPTCHA
            captcha_elements = sb.find_elements("iframe[src*='recaptcha']")
            if captcha_elements:
                print(f"🤖 {len(captcha_elements)} CAPTCHA iframe található")

            # Keressünk bármilyen listing elemet
            all_listings = sb.find_elements("div[class*='listing']")
            print(f"🔍 Összes 'listing' elem: {len(all_listings)}")

            # Keressünk card elemeket
            all_cards = sb.find_elements("div[class*='card']")
            print(f"🔍 Összes 'card' elem: {len(all_cards)}")

            # Konkrét target elemek
            target_elements = sb.find_elements("div.listing-card-content")
            print(f"🎯 Target elemek (listing-card-content): {len(target_elements)}")

            # HTML részlet mentése debug célokra
            html_snippet = (
                sb.get_page_source()[:2000] if sb.get_page_source() else "No HTML"
            )
            print(f"🔍 HTML kezdete: {html_snippet[:500]}...")

        except Exception as e:
            print(f"❌ Debug hiba: {e}")

    error_log: list[str] = []

    def add_err(stage: str, e: Exception | str, extra: str = ""):
        msg = f"[{stage}] {type(e).__name__ if isinstance(e, Exception) else 'Error'}: {str(e)}"
        if extra:
            msg += f" | {extra}"
        if len(msg) > 500:  # ne legyen túl hosszú a Note
            msg = msg[:500] + " …"
        error_log.append(msg)

    all_data = []
    page_count = 1

    # Platform-függő Chrome opciók
    import platform

    chrome_options = [
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-plugins",
        "--window-size=1920,1080",
        "--disable-blink-features=AutomationControlled",  # Automation észlelés kikapcsolása
        "--disable-web-security",
        "--allow-running-insecure-content",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    # Linux-specifikus opciók (Azure App Service)
    if platform.system() == "Linux":
        chrome_options.extend(
            [
                "--single-process",
                "--no-zygote",
                "--disable-setuid-sandbox",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
            ]
        )

    # # Chrome telepítése (ha szükséges)
    # if not install_chrome_if_needed():
    #     add_err("chrome_install", "Chrome telepítése sikertelen")
    #     # Folytatjuk anélkül, hátha működik...

    # chrome_options = get_selenium_options()

    # with SB(uc=True, headless=True, locale="HU") as sb:
    #     print(f"🌐 Oldal betöltése: {BASE_URL}")
    #     # Első oldal
    #     sb.activate_cdp_mode(BASE_URL)
    #     sb.wait_for_ready_state_complete()
    #     try:
    #         sb.uc_gui_click_captcha()
    #     except Exception:
    #         pass
    #     # Várunk a kártyákra (stabilabb, mint a sleep)
    #     sb.wait_for_element_visible("div.listing-card-content", timeout=20)
    #     # Ha van lusta betöltés, görgessünk le
    #     sb.scroll_to_bottom()
    #     sb.sleep(0.5)

    #     html = sb.get_page_source()
    #     soup = BeautifulSoup(html, "html.parser")
    #     page_count = get_page_count(soup)

    #     # 1. oldal adatai
    #     all_data.extend(extract_cards(soup))

    #     # Többi oldal UGYANABBAN a böngészőben
    #     for page in range(2, page_count + 1):
    #         url = f"{BASE_URL}?page={page}"
    #         print(f"➡️ Lapozás: {url}")
    #         sb.uc_open(url)  # fontos: ugyanabban a sessionben
    #         sb.wait_for_ready_state_complete()
    #         try:
    #             sb.uc_gui_click_captcha()
    #         except Exception:
    #             pass
    #         # Várunk, míg megjelennek a kártyák
    #         sb.wait_for_element_visible("div.listing-card-content", timeout=20)
    #         sb.scroll_to_bottom()
    #         sb.sleep(0.5)

    #         html = sb.get_page_source()
    #         if not html:
    #             print(f"⚠️ {page}. oldal üres HTML")
    #             continue

    #         soup = BeautifulSoup(html, "html.parser")
    #         page_items = extract_cards(soup)
    #         if not page_items:
    #             print(f"⚠️ {page}. oldalon nem találtam kártyákat")
    #         all_data.extend(page_items)

    try:
        with SB(
            uc=True,
            headless=True,
            locale="HU",
            chromium_arg=" ".join(chrome_options),
            undetectable=True,
            incognito=True,
            disable_csp=True,
            guest_mode=True,
            driver_version="latest",
            page_load_strategy="eager",
        ) as sb:
            print(f"🌐 Oldal betöltése: {BASE_URL}")
            # Első oldal
            try:
                sb.activate_cdp_mode(BASE_URL)
                print("✅ CDP mód aktiválva")
                try:
                    sb.wait_for_ready_state_complete(timeout=30)
                    print("✅ Ready state complete")

                    debug_page_content(sb)
                    # sb.uc_gui_click_captcha()
                except Exception as ce:
                    add_err("captcha_page_1", ce)
                sb.wait_for_element_visible("div.listing-card-content", timeout=20)
                sb.scroll_to_bottom()
                sb.sleep(0.5)
            except Exception as e:
                add_err("first_page_load", e)

            try:
                html = sb.get_page_source() or ""
                if not html:
                    add_err("first_page_html", "empty HTML")
                soup = BeautifulSoup(html, "html.parser")
            except Exception as e:
                add_err("first_page_parse", e)
                soup = BeautifulSoup("", "html.parser")

            try:
                page_count = max(1, get_page_count(soup))
            except Exception as e:
                add_err("get_page_count", e)
                page_count = 1

            try:
                all_data.extend(extract_cards(soup))
            except Exception as e:
                add_err("extract_page_1", e)

            # Többi oldal UGYANABBAN a böngészőben
            for page in range(2, page_count + 1):
                url = f"{BASE_URL}?page={page}"
                print(f"➡️ Lapozás: {url}")
                try:
                    sb.uc_open(url)
                    sb.wait_for_ready_state_complete()
                    try:
                        sb.wait_for_ready_state_complete()
                    #     sb.uc_gui_click_captcha()
                    except Exception as ce:
                        add_err(f"captcha_page_{page}", ce)
                    sb.wait_for_element_visible("div.listing-card-content", timeout=20)
                    sb.scroll_to_bottom()
                    sb.sleep(0.5)
                except Exception as e:
                    add_err(f"page_{page}_load", e)

                try:
                    html = sb.get_page_source() or ""
                    if not html:
                        add_err(f"page_{page}_html", "empty HTML")
                except Exception as e:
                    add_err(f"page_{page}_get_html", e)
                    html = ""

                try:
                    soup = BeautifulSoup(html, "html.parser")
                    page_items = extract_cards(soup)
                    if not page_items:
                        add_err(f"page_{page}_no_items", "no cards found")
                    all_data.extend(page_items)
                except Exception as e:
                    add_err(f"page_{page}_extract", e)

    except Exception as e:
        # Ha a böngésző indítása / teljes folyamat esik el
        add_err("browser_session", e)

    # ---- Note összeállítása és mentése ----
    count = session.exec(select(func.count()).select_from(Note)).one()
    summary = f"lekérdezés: {count + 1}, oldalak száma: {page_count}, ingatlanok száma: {len(all_data)}"
    if error_log:
        listed = "\n- ".join(error_log[:10])  # limitáld az első 10 hibára
        summary += f"\nhibák:\n- {listed}"
        if len(error_log) > 10:
            summary += f"\n(+{len(error_log) - 10} további hiba)"

    # return {
    #     "query": BASE_URL,
    #     "pages": page_count,
    #     "items_count": len(all_data),
    #     "items": all_data,
    # }

    # note_text = f"oldalak száma: {page_count}, ingatlanok száma: {len(all_data)}"

    note = Note(note=summary, created_at=datetime.now(timezone.utc))

    # note = Note(note=note_text, created_at=datetime.now(timezone.utc))

    session.add(note)
    session.commit()
    session.refresh(note)
    return {
        **note.dict(),
        "created_at_utc": note.created_at.isoformat().replace("+00:00", "Z"),
        "created_at_local": note.created_at.astimezone(TZ).isoformat(),
    }


@router.get("/all")
async def save_real_estate(session: SessionDep):

    statement = select(Note)
    notes = session.exec(statement).all()

    return notes
