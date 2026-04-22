"""
sendmail.py
-----------
arXiv 논문 메일 발송 모듈.

Input  : summary.py 가 채운 JSON 파일
Output : Gmail BCC 발송

테이블 구조 (컬럼 비율 #:3% / Title:93% / Link:4%):
    행 1: [번호 rowspan=3] | Title             | [Link rowspan=2]
    행 2:                  | Keywords           |
    행 3:                  | Summary (colspan=2)|
"""

from __future__ import annotations

import html
import json
import os
import smtplib
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import config


# ── 설정 (.env → config.py) ───────────────────────────────────────────────────

CATEGORY   = config.ARXIV_CATEGORY
RECIPIENTS = config.EMAIL_RECIPIENTS

EMAIL_FOOTER = (
    "If you have any questions or run into any issues, please feel free to reach out.\n"
    "Good ideas and suggestions are welcome as well.\n\n"
    "Have a great day.\n"
    "Thank you.\n\n"
)


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _default_subject(date_str: str, category: str = CATEGORY) -> str:
    return f"{date_str} Daily arXiv {category} listing"


# ── HTML 생성 ─────────────────────────────────────────────────────────────────

def build_html_body(papers: list[dict]) -> str:
    """
    논문 리스트를 HTML 이메일 본문으로 변환합니다.

    논문 1개당 3행 구조 (컬럼 비율 #:3% / Title:93% / Link:4%):
        행 1: [번호 rowspan=3] | Title             | [Link rowspan=2]
        행 2:                  | Keywords           |
        행 3:                  | Summary (colspan=2)|
    """
    TABLE = (
        'border="1" cellpadding="0" cellspacing="0" width="100%" '
        'style="border-collapse:collapse;font-family:sans-serif;'
        'font-size:14px;width:100%;table-layout:fixed"'
    )
    COLGROUP = (
        '<colgroup>'
        '<col width="3%">'
        '<col width="93%">'
        '<col width="4%">'
        '</colgroup>'
    )

    # ── 헤더 스타일 ───────────────────────────────────────────────────────────
    TH_BASE = 'background:#f2f2f2;padding:6px;'
    TH_NUM  = f'width="3%"  style="{TH_BASE}text-align:center;font-size:11px"'
    TH_BODY = f'width="93%" style="{TH_BASE}text-align:left"'
    TH_LINK = f'width="4%"  style="{TH_BASE}text-align:center;font-size:11px"'

    # ── 셀 스타일 ─────────────────────────────────────────────────────────────
    TD_NUM     = ('width="3%"  style="width:3%;vertical-align:middle;'
                  'text-align:center;padding:6px;font-size:11px;color:#aaa"')
    TD_TITLE   = ('width="93%" style="width:93%;vertical-align:middle;'
                  'padding:8px 8px 3px 8px;font-weight:bold"')
    TD_KW      = ('width="93%" style="width:93%;vertical-align:middle;'
                  'padding:3px 8px 8px 8px;color:#555;font-size:13px"')
    TD_LINK    = ('width="4%"  style="width:4%;vertical-align:middle;'
                  'text-align:center;padding:6px"')
    TD_SUMMARY = ('style="vertical-align:top;padding:8px 8px 14px 8px;'
                  'color:#444;font-size:13px;background:#fafafa;font-style:italic"')

    thead = (
        f'<thead><tr>'
        f'<th {TH_NUM}>#</th>'
        f'<th {TH_BODY}>Title / Keywords</th>'
        f'<th {TH_LINK}>Link</th>'
        f'</tr></thead>'
    )

    rows: list[str] = []
    for i, paper in enumerate(papers, start=1):
        title    = html.escape(str(paper.get('title',    '')).strip())
        link_raw =             str(paper.get('link',     '')).strip()
        link_h   = html.escape(link_raw)
        keywords = html.escape(str(paper.get('keywords', '')).strip())
        summary  = html.escape(str(paper.get('summary',  '')).strip())

        link_cell = (f'<a href="{link_h}" style="font-size:12px;text-decoration:none">Link</a>'
                     if link_raw else '')

        # 행 1: 번호(rowspan=3) | Title | Link(rowspan=2)
        rows.append(
            f'<tr>'
            f'<td rowspan="3" {TD_NUM}>{i}</td>'
            f'<td {TD_TITLE}>{title}</td>'
            f'<td rowspan="2" {TD_LINK}>{link_cell}</td>'
            f'</tr>'
        )
        # 행 2: Keywords  (# 와 Link 는 rowspan 으로 이미 차지)
        rows.append(
            f'<tr>'
            f'<td {TD_KW}>🏷 {keywords}</td>'
            f'</tr>'
        )
        # 행 3: Summary  (# 는 rowspan, Title+Link 자리를 colspan=2 로)
        rows.append(
            f'<tr>'
            f'<td colspan="2" {TD_SUMMARY}>💬 {summary}</td>'
            f'</tr>'
        )

    tbody  = "<tbody>" + "".join(rows) + "</tbody>"
    table  = f"<table {TABLE}>{COLGROUP}{thead}{tbody}</table>"
    footer = html.escape(EMAIL_FOOTER).replace("\n", "<br>")

    return (
        "<html><body>"
        f"<p>{table}</p>"
        f'<p style="margin-top:1.5em;font-family:sans-serif;font-size:14px;line-height:1.5">'
        f"{footer}</p>"
        "</body></html>"
    )


# ── 발송 ──────────────────────────────────────────────────────────────────────

def send_gmail_html(
    *,
    bcc_addrs: list[str],
    subject: str,
    html_body: str,
) -> None:
    user     = config.GMAIL_USER
    password = config.GMAIL_APP_PASSWORD

    bcc_addrs = [a.strip() for a in bcc_addrs if a and str(a).strip()]
    if not bcc_addrs:
        raise ValueError("수신자가 없습니다. RECIPIENTS 또는 --to 를 확인하세요.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = user
    msg["To"]      = "Undisclosed recipients:;"
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.sendmail(user, bcc_addrs, msg.as_string())


# ── 메인 함수 (main.py 에서 호출) ────────────────────────────────────────────

def send_mail(
    date_str: str | None = None,
    papers: list[dict] | None = None,
    category: str = CATEGORY,
    recipients: list[str] | None = None,
    subject: str | None = None,
) -> None:
    """
    Parameters
    ----------
    date_str   : 'YYYY-MM-DD'. None 이면 오늘 날짜 사용.
    papers     : 이미 로드된 논문 리스트. None 이면 JSON 파일에서 읽습니다.
    category   : arXiv 카테고리
    recipients : 수신자 목록. None 이면 파일 상단 RECIPIENTS 사용.
    subject    : 메일 제목. None 이면 기본 제목 사용.
    """
    if date_str is None:
        date_str = datetime.today().strftime('%Y-%m-%d')

    # ── JSON 로드 ─────────────────────────────────────────────────────────────
    if papers is None:
        json_path = config.OUTPUT_DIR / f"arxiv_{category.replace('.', '_')}_{date_str}.json"
        if not json_path.exists():
            raise FileNotFoundError(
                f"[ERROR] JSON 파일을 찾을 수 없습니다: {json_path}\n"
                "먼저 search.py / summary.py 를 실행하세요."
            )
        papers = json.loads(json_path.read_text(encoding='utf-8'))
        print(f"[LOAD] {json_path}  ({len(papers)}편)")

    _recipients = recipients or RECIPIENTS
    _subject    = subject    or _default_subject(date_str, category)

    html_body = build_html_body(papers)
    send_gmail_html(bcc_addrs=_recipients, subject=_subject, html_body=html_body)

    print(
        f"[SEND] {len(papers)}편  →  {len(_recipients)}명 BCC 발송 완료\n"
        f"       수신자: {', '.join(_recipients)}"
    )


# ── CLI (단독 실행용) ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="arXiv JSON을 HTML 테이블로 변환해 Gmail로 발송합니다."
    )
    parser.add_argument(
        '--date', '-d',
        default=None,
        metavar='YYYY-MM-DD',
        help="처리할 날짜 (생략 시 오늘)",
    )
    parser.add_argument(
        '--to',
        action='append',
        dest='to_addrs',
        metavar='EMAIL',
        help="BCC 수신자 (여러 번 지정 가능). 생략 시 파일 상단 RECIPIENTS 사용.",
    )
    parser.add_argument(
        '--subject',
        default=None,
        help="메일 제목 전체를 덮어씁니다.",
    )
    args = parser.parse_args()

    send_mail(
        date_str=args.date,
        recipients=args.to_addrs or None,
        subject=args.subject,
    )
