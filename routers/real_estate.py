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

router = APIRouter(prefix="/real-estate", tags=["real-estate"])
TZ = ZoneInfo("Europe/Budapest")


BASE_URL = os.getenv("BASE_URL")
# BASE_URL = (
#     "https://ingatlan.com/lista/elado+lakas+nem-berleti-jog+oroszlany+fix-3-szazalek"
# )


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
        with SB(uc=True, headless=True, locale="HU") as sb:
            print(f"🌐 Oldal betöltése: {BASE_URL}")
            # Első oldal
            try:
                sb.activate_cdp_mode(BASE_URL)
                sb.wait_for_ready_state_complete()
                # try:
                #     sb.uc_gui_click_captcha()
                # except Exception as ce:
                #     add_err("captcha_page_1", ce)
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
                    # try:
                    #     sb.uc_gui_click_captcha()
                    # except Exception as ce:
                    #     add_err(f"captcha_page_{page}", ce)
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
    summary = f"oldalak száma: {page_count}, ingatlanok száma: {len(all_data)}"
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

    # count = session.exec(select(func.count()).select_from(Note)).one()
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
