"""
search.py
---------
arXiv 논문 검색 모듈.

Input  : date (YYYY-MM-DD 문자열, 생략 시 오늘)
Output : List[dict]  {title, authors, arxiv_id, link, keywords, summary}
         keywords / summary 는 이 단계에서 빈 값으로 초기화됩니다.
         --debug 플래그 사용 시 Excel 파일도 함께 저장합니다.
"""

import json
import arxiv
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import config


# ── 설정 (.env → config.py) ───────────────────────────────────────────────────

CATEGORY    = config.ARXIV_CATEGORY
MAX_RESULTS = config.ARXIV_MAX_RESULTS


# ── 날짜 헬퍼 ─────────────────────────────────────────────────────────────────

def _prev_business_day(d):
    """주어진 날짜에서 바로 이전 영업일(월~금)을 반환합니다."""
    d = d - timedelta(days=1)
    while d.weekday() >= 5:   # 5=Sat, 6=Sun
        d = d - timedelta(days=1)
    return d


def _submission_window(target_date):
    """
    arXiv listing 날짜 기준으로 실제 제출 window (ET)를 반환합니다.

    arXiv announcement 스케줄:
        제출 마감(ET) 14:00  →  당일 20:00 ET 에 announcement
        listing 날짜 = announcement 다음 날

    따라서:
        end_day   = target_date 직전 영업일  (= 마지막 마감일)
        start_day = end_day 직전 영업일      (= 그 이전 마감일)
    """
    et = ZoneInfo('America/New_York')
    end_day   = _prev_business_day(target_date)
    start_day = _prev_business_day(end_day)

    end_et   = datetime.combine(end_day,   datetime.min.time().replace(hour=14), tzinfo=et)
    start_et = datetime.combine(start_day, datetime.min.time().replace(hour=14), tzinfo=et)
    return start_et, end_et


# ── 핵심 검색 함수 ────────────────────────────────────────────────────────────

def search_papers(date_str: str | None = None,
                  category: str = CATEGORY,
                  max_results: int = MAX_RESULTS,
                  debug: bool = False) -> list[dict]:
    """
    arXiv에서 논문을 검색하고 구조화된 리스트를 반환합니다.

    Parameters
    ----------
    date_str    : 'YYYY-MM-DD' 형식. None 이면 오늘 날짜를 사용합니다.
    category    : arXiv 카테고리 (기본값: 'cs.RO')
    max_results : API 최대 조회 수 (기본값: 2000)
    debug       : True 이면 Excel 파일을 함께 저장합니다.

    Returns
    -------
    papers : List[dict]
        각 dict는 {title, authors, arxiv_id, link, keywords, summary} 구조입니다.
        keywords / summary 는 빈 값으로 초기화됩니다.
    """
    # ── 날짜 파싱 ──────────────────────────────────────────────────────────────
    if date_str is None:
        date_str = datetime.today().strftime('%Y-%m-%d')

    target_date  = datetime.strptime(date_str, '%Y-%m-%d').date()
    weekday_name = target_date.strftime('%A')
    wd           = target_date.weekday()   # Mon=0 … Sun=6

    if wd in (5, 6):
        print(f"[SKIP] {date_str} is a {weekday_name}. arXiv has no listing on weekends.")
        return []

    # ── 제출 window 계산 ───────────────────────────────────────────────────────
    start_et, end_et = _submission_window(target_date)

    utc       = ZoneInfo('UTC')
    start_utc = start_et.astimezone(utc)
    end_utc   = end_et.astimezone(utc)
    start_str = start_utc.strftime('%Y%m%d%H%M')
    end_str   = end_utc.strftime('%Y%m%d%H%M')

    print(f"[INFO] Listing date : {date_str} ({weekday_name})")
    print(f"[INFO] Window  (ET) : {start_et.strftime('%a %Y-%m-%d %H:%M %Z')}"
          f"  →  {end_et.strftime('%a %Y-%m-%d %H:%M %Z')}")
    print(f"[INFO] Window (UTC) : {start_utc.strftime('%a %Y-%m-%d %H:%M')}"
          f"  →  {end_utc.strftime('%a %Y-%m-%d %H:%M')}")

    # ── API 쿼리 ───────────────────────────────────────────────────────────────
    query = f'cat:{category} AND submittedDate:[{start_str} TO {end_str}]'
    print(f"[INFO] Query        : {query}\n")

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )
    client = arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)

    # ── 결과 수집 ──────────────────────────────────────────────────────────────
    papers           = []
    skipped_crosslist = 0

    for result in client.results(search):
        if result.primary_category != category:
            skipped_crosslist += 1
            continue

        papers.append({
            'title'    : result.title.strip().replace('\n', ' '),
            'authors'  : ', '.join(a.name for a in result.authors),
            'arxiv_id' : result.entry_id.split('/')[-1],
            'link'     : result.entry_id,
            'abstract' : result.summary.strip().replace('\n', ' '),
            'keywords' : '',     # summary.py 단계에서 채워집니다
            'summary'  : '',     # summary.py 단계에서 채워집니다
        })

    # ── 결과 출력 ──────────────────────────────────────────────────────────────
    print(f"[RESULT] Primary '{category}' papers : {len(papers)}")
    print(f"[RESULT] Skipped cross-lists         : {skipped_crosslist}")

    if len(papers) == 0:
        print("[WARN] 논문이 없습니다. arXiv API는 최대 12-48시간 지연될 수 있습니다.")

    # ── JSON 저장 ──────────────────────────────────────────────────────────────
    json_path = config.OUTPUT_DIR / f"arxiv_{category.replace('.', '_')}_{date_str}.json"
    json_path.write_text(
        json.dumps(papers, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f"[SAVE] JSON → {json_path}")

    # ── Debug: Excel 저장 ──────────────────────────────────────────────────────
    if debug:
        xlsx_path = config.OUTPUT_DIR / f"debug_{category.replace('.', '_')}_{date_str}.xlsx"
        df = pd.DataFrame(papers)
        df.to_excel(xlsx_path, index=False)
        print(f"[DEBUG] Excel → {xlsx_path}")

    return papers