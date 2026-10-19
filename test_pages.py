#!/usr/bin/env python3
"""who_am_i 페이지 검사 (지시서 16장).

사용법: python3 test_pages.py [ko en zh ja uz ru]
필요한 것: pip install playwright && playwright install chromium

검사 항목
 1. 모든 언어 × 데스크톱(1280)·휴대폰(390): 스크립트 오류 0, 가로 넘침 0
 2. 번역판: 화면 글자·alt·aria-label·title에 남은 한국어 0 (언어 선택 목록의 "한국어"는 제외)
 3. 버튼(거르기·연도 막대·확대 보기) 모두 눌러 보기
 4. 조수 말풍선 4개, 대화 4곳이 있는지
 5. 언어 전환: 브라우저 언어 en/ja/zh/uz/ru → 해당 파일, de/ko → 한국어, ?lang=, 고른 언어 기억, #섹션 유지
"""
import functools, http.server, re, socketserver, sys, threading, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
DIST = ROOT / "dist"
CODES = sys.argv[1:] or ["ko", "en", "zh", "ja", "uz", "ru"]
HANGUL = re.compile(r"[가-힣]")


def fname(c):
    return "who_am_i.html" if c == "ko" else f"who_am_i.{c}.html"


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Quiet, directory=str(DIST))
    s = socketserver.TCPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_address[1]}/"


LEFT_KO_JS = """() => {
  const skip = el => !el || el.closest('.langsel,.langfab,script,style');
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = w.nextNode())) { if (!skip(n.parentElement) && /[\\uac00-\\ud7a3]/.test(n.textContent)) out.push(n.textContent.trim().slice(0,50)); }
  document.querySelectorAll('[alt],[aria-label],[title],[data-cap]').forEach(el => {
    if (skip(el)) return;
    ['alt','aria-label','title','data-cap'].forEach(a => { const v = el.getAttribute(a); if (v && /[\\uac00-\\ud7a3]/.test(v)) out.push(a+': '+v.slice(0,50)); });
  });
  if (/[\\uac00-\\ud7a3]/.test(document.title)) out.push('title: '+document.title);
  return out;
}"""


def main():
    from playwright.sync_api import sync_playwright
    srv, base = serve()
    fails = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        for c in CODES:
            for vw, vh in [(1280, 900), (390, 844)]:
                ctx = b.new_context(viewport={"width": vw, "height": vh}, locale="ko-KR", reduced_motion="reduce")
                pg = ctx.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(base + fname(c)); pg.wait_for_timeout(300)
                if c != "ko":   # 번역판 주소로 들어오면 자동 전환하지 않아야 한다
                    assert pg.url.endswith(fname(c)), f"{c}: 번역판에서 다른 언어로 이동함 {pg.url}"
                over = pg.evaluate("document.documentElement.scrollWidth") - vw
                # 버튼 모두 눌러 보기
                for sel in ["#patChips button", "#pubChips button", "#teachChips button", "#bars button:not([disabled])"]:
                    for i in range(pg.locator(sel).count()):
                        pg.locator(sel).nth(i).click()
                pg.locator("[data-zoom]").first.click(); pg.wait_for_timeout(100)
                pg.locator("#zoomClose").click()
                pg.locator("#langfab button").click(); pg.keyboard.press("Escape")
                asst = pg.locator(".say.asst").count(); talks = pg.locator(".talk").count()
                ko_left = pg.evaluate(LEFT_KO_JS) if c != "ko" else []
                ok = not errs and over <= 0 and asst == 4 and talks == 4 and not ko_left
                fails += not ok
                print(f"[{c} {vw:4d}px] {'통과' if ok else '실패'}  오류 {len(errs)} · 가로 넘침 {max(over,0)}px · 조수 {asst} · 대화 {talks} · 남은 한국어 {len(ko_left)}")
                for e in errs[:5]: print("    오류:", e)
                for k in ko_left[:8]: print("    한국어:", k)
                ctx.close()
        # 언어 전환
        if set(CODES) >= {"ko", "en", "zh", "ja", "uz", "ru"}:
            def land(locale, url, store=None):
                ctx = b.new_context(locale=locale); pg = ctx.new_page()
                if store:
                    pg.goto(base + fname("ko") + "?lang=" + store); pg.wait_for_timeout(600)
                pg.goto(url); pg.wait_for_timeout(900)
                u = pg.url; ctx.close(); return u.replace(base, "")
            cases = [(l, base + fname("ko"), None, fname(l[:2])) for l in ["en-US", "ja-JP", "zh-CN", "uz-UZ", "ru-RU"]]
            cases += [("de-DE", base + fname("ko"), None, fname("ko")), ("ko-KR", base + fname("ko"), None, fname("ko")),
                      ("ko-KR", base + fname("ko") + "?lang=ja", None, fname("ja")),
                      ("en-US", base + fname("ko"), "ru", fname("ru")),            # 고른 언어 기억이 브라우저 언어보다 먼저
                      ("ko-KR", base + fname("ko") + "#teach", "en", fname("en") + "#teach"),
                      ("ja-JP", base + fname("en"), None, fname("en"))]             # 번역판 주소는 그대로
            for loc, url, store, want in cases:
                got = land(loc, url, store)
                ok = got.split("?")[0] == want
                fails += not ok
                print(f"[전환] 브라우저 {loc:6s} 저장 {store or '-':3s} {url.replace(base,''):28s} → {got:28s} {'통과' if ok else '실패 (기대 '+want+')'}")
        b.close()
    srv.shutdown()
    print("모두 통과" if not fails else f"실패 {fails}건")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
