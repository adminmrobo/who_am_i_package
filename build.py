#!/usr/bin/env python3
"""who_am_i 빌드 스크립트 — 템플릿 + 데이터 + 그림 → 6개 언어 HTML

사용법:
  python3 build.py              # 검사 후 dist/에 6개 파일 생성
  python3 build.py --ko-only    # 한국어 who_am_i.html 만 생성 (번역 전 미리보기)
  python3 build.py --test       # 생성 후 헤드리스 브라우저 검사까지 (playwright 필요)

입력:  template.html, data/profile.<lang>.json, img/*.webp
출력:  dist/who_am_i.html, dist/who_am_i.en.html, .zh .ja .uz .ru
필요한 것: Python 3.8+ (표준 라이브러리만). --test 는 `pip install playwright && playwright install chromium`.
"""
import base64, html, json, re, subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
BASE = "who_am_i"                 # 파일 이름. 바꾸면 다른 시리즈의 "저자 소개" 링크도 바꿔야 한다
STORAGE_KEY = "who_am_i_lang"     # 고른 언어를 기억하는 localStorage 키
HOME_LINK = "index.html"          # "시리즈 처음으로" 버튼. 다른 시리즈 링크이므로 모든 언어에서 그대로 둔다

# 언어 순서 = 메뉴·배너에 보이는 순서 (지시서 8장, 14-1)
LANGS = [
    # 코드, 표시 이름, <html lang>, hreflang, Google Fonts 질의, 글꼴 이름(앞쪽), 저자 이름
    ("ko", "한국어", "ko", "ko", "family=IBM+Plex+Sans+KR:wght@400;500;700", '"IBM Plex Sans KR"', "안상선"),
    ("en", "English", "en", "en", "family=IBM+Plex+Sans:wght@400;500;700&family=IBM+Plex+Sans+KR:wght@400;500;700", '"IBM Plex Sans","IBM Plex Sans KR"', "Ahn Sangsun"),
    ("zh", "中文", "zh-CN", "zh-CN", "family=Noto+Sans+SC:wght@400;500;700", '"Noto Sans SC"', "Ahn Sangsun"),
    ("ja", "日本語", "ja", "ja", "family=Noto+Sans+JP:wght@400;500;700", '"Noto Sans JP"', "アン・サンソン"),
    ("uz", "Oʻzbekcha", "uz", "uz", "family=IBM+Plex+Sans:wght@400;500;700&family=IBM+Plex+Sans+KR:wght@400;500;700", '"IBM Plex Sans","IBM Plex Sans KR"', "Ahn Sangsun"),
    ("ru", "Русский", "ru", "ru", "family=IBM+Plex+Sans:wght@400;500;700&family=IBM+Plex+Sans+KR:wght@400;500;700", '"IBM Plex Sans","IBM Plex Sans KR"', "Ан Сансон"),
]
CODES = [l[0] for l in LANGS]
CJK_CSS = "*{word-break:normal!important;line-break:strict}"   # 지시서 14-2: 중국어·일본어 줄바꿈


def fname(code):
    return f"{BASE}.html" if code == "ko" else f"{BASE}.{code}.html"


def lang_head_script(cur):
    """<meta charset> 바로 뒤에 들어가는 언어 자동 전환 스크립트 (지시서 8장)."""
    return """<script>
/* 언어 전환: ?lang=xx → 저장 후 이동 / 한국어 페이지에서만 저장된 언어·브라우저 언어로 자동 이동 / 번역 파일이 없으면 머문다 */
(function(){var L=%s,K=%s,CUR=%s,B=%s;
function f(l){return B+(l==='ko'?'':'.'+l)+'.html';}
function save(l){try{localStorage.setItem(K,l);}catch(e){}}
function go(l){var u=f(l)+location.hash;if(location.protocol==='file:'){location.replace(u);return;}
 var de=document.documentElement;de.style.visibility='hidden';var t=setTimeout(show,2500);
 function show(){clearTimeout(t);de.style.visibility='';}
 try{fetch(u,{method:'HEAD'}).then(function(r){if(r.ok)location.replace(u);else show();},show);}catch(e){show();}}
window.__setLang=function(l){save(l);if(l!==CUR)location.href=f(l)+location.hash;};
var q=(location.search.match(/[?&]lang=([a-z]{2})/)||[])[1];
if(q&&L.indexOf(q)>=0){save(q);if(q!==CUR)go(q);return;}
if(CUR!=='ko')return;
var w=null;try{w=localStorage.getItem(K);}catch(e){}
if(!w&&location.protocol!=='file:'){var n=navigator.languages||[navigator.language||''];
 for(var i=0;i<n.length;i++){var c=String(n[i]).slice(0,2).toLowerCase();if(L.indexOf(c)>=0){w=c;break;}}}
if(w&&w!=='ko'&&L.indexOf(w)>=0)go(w);
})();
</script>""" % (json.dumps(CODES), json.dumps(STORAGE_KEY), json.dumps(cur), json.dumps(BASE))


def lang_select(cur, label):
    opts = "".join(f'<option value="{c}"{" selected" if c == cur else ""}>{html.escape(n)}</option>' for c, n, *_ in LANGS)
    return (f'<label class="langsel"><span aria-hidden="true">🌐</span><span class="sr">{html.escape(label)}</span>'
            f'<select onchange="window.__setLang(this.value)">{opts}</select></label>')


def lang_fab(cur, label):
    cur_name = dict((c, n) for c, n, *_ in LANGS)[cur]
    items = "".join(
        f'<li><a href="{fname(c)}" lang="{h}" data-l="{c}"{" aria-current=\"true\"" if c == cur else ""}>{html.escape(n)}</a></li>'
        for c, n, h, *_ in LANGS)
    return f"""<div class="langfab" id="langfab">
  <button type="button" aria-haspopup="true" aria-expanded="false" aria-label="{html.escape(label)}">🌐 {html.escape(cur_name)}</button>
  <ul hidden>{items}</ul>
</div>
<script>
(function(){{var w=document.getElementById('langfab'),b=w.querySelector('button'),u=w.querySelector('ul');
function set(o){{u.hidden=!o;b.setAttribute('aria-expanded',o?'true':'false');}}
b.addEventListener('click',function(e){{e.stopPropagation();set(u.hidden);}});
u.addEventListener('click',function(e){{var a=e.target.closest('a');if(!a)return;e.preventDefault();window.__setLang(a.dataset.l);}});
document.addEventListener('click',function(e){{if(!w.contains(e.target))set(false);}});
document.addEventListener('keydown',function(e){{if(e.key==='Escape')set(false);}});
}})();
</script>"""


def hreflang():
    rows = [f'<link rel="alternate" hreflang="{h}" href="{fname(c)}">' for c, n, lh, h, *_ in LANGS]
    rows.append(f'<link rel="alternate" hreflang="x-default" href="{fname("ko")}">')
    return "\n".join(rows)


def js_images(data):
    """스크립트가 IMG[...]로 부르는 그림 (말풍선 표정, 특허증, 강의 배너). 템플릿에 바로 박히는 그림은 따로 넣는다."""
    keys = set()
    for part in data["talk"].values():
        for line in part:
            keys.add(f'{line["who"]}_{line["mood"]}')
    keys |= {p["img"] for p in data["ip"]["items"]}
    keys |= {c["img"] for c in data["elearn"]["items"] if c["img"]}
    return keys


def b64(key):
    p = ROOT / "img" / f"{key}.webp"
    if not p.exists():
        sys.exit(f"그림 없음: img/{key}.webp")
    return "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode()


def build(code, tpl):
    data = json.loads((ROOT / "data" / f"profile.{code}.json").read_text(encoding="utf-8"))
    c, name, html_lang, hl, fq, fstack, author = next(l for l in LANGS if l[0] == code)
    inline = {k: b64(k) for k in set(re.findall(r"%%IMG:(\w+)%%", tpl))}
    imgs = {k: b64(k) for k in sorted(js_images(data))}
    out = tpl
    rep = {
        "HTML_LANG": html_lang,
        "TITLE": html.escape(data["meta"]["title"]),
        "DESCRIPTION": html.escape(data["meta"]["description"]),
        "AUTHOR": html.escape(author),
        "HREFLANG": hreflang(),
        "FONT_QUERY": fq,
        "FONT_STACK": fstack,
        "EXTRA_CSS": CJK_CSS if code in ("zh", "ja") else "",
        "LANG_SWITCH_HEAD": lang_head_script(code),
        "LANG_SELECT": lang_select(code, data["ui"]["langLabel"]),
        "LANG_FAB": lang_fab(code, data["ui"]["langBanner"]),
        "HOME": HOME_LINK,
        "DATA": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
        "IMG_MAP": json.dumps(imgs),
    }
    for k, v in rep.items():
        out = out.replace(f"%%{k}%%", v)
    out = re.sub(r"%%IMG:(\w+)%%", lambda m: inline[m.group(1)], out)
    left = re.findall(r"%%[A-Z_:a-z0-9]+%%", out)
    if left:
        sys.exit(f"[{code}] 채우지 못한 자리표시: {sorted(set(left))}")
    dst = ROOT / "dist" / fname(code)
    dst.write_text(out, encoding="utf-8")
    print(f"  {dst.name:22s} {len(out.encode()) // 1024:5d} KB")


def main():
    args = sys.argv[1:]
    codes = ["ko"] if "--ko-only" in args else CODES
    if codes != ["ko"]:
        r = subprocess.run([sys.executable, str(ROOT / "check_data.py")], capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0 and "--force" not in args:
            sys.exit("데이터 검사에 실패했습니다. 위 문제를 고친 뒤 다시 실행하세요. (그래도 만들려면 --force)")
    tpl = (ROOT / "template.html").read_text(encoding="utf-8")
    (ROOT / "dist").mkdir(exist_ok=True)
    print("생성:")
    for c in codes:
        build(c, tpl)
    if "--test" in args:
        subprocess.run([sys.executable, str(ROOT / "test_pages.py")] + codes, check=False)


if __name__ == "__main__":
    main()
