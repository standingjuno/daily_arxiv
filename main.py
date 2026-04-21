"""
Usage:
    python main.py                        # 오늘 날짜, 전체 파이프라인 실행
    python main.py --date 2026-04-17      # 특정 날짜 실행
    python main.py --debug                # 디버그 모드 (Excel 추가 저장)
    python main.py --step search          # 검색만 실행
    python main.py --step summary         # 요약만 실행 (기존 JSON 필요)
    python main.py --step send            # 메일 발송만 실행 (기존 JSON 필요)
"""

import argparse
from datetime import datetime

from search import search_papers
from summary import summarize_papers
from sendmail import send_mail


STEPS = ('search', 'summary', 'send', 'all')


def run_pipeline(date_str: str, debug: bool = False, step: str = 'all'):
    print(f"=== arXiv Pipeline  |  date={date_str}  |  step={step}  |  debug={debug} ===\n")

    papers = None

    # ── 1. 검색 ──────────────────────────────────────────────────────────────
    if step in ('all', 'search'):
        print("── [1/3] Search ─────────────────────────────────────────")
        papers = search_papers(date_str=date_str, debug=debug)
        print(f"     → {len(papers)}편 수집 완료\n")

    # ── 2. 요약 ──────────────────────────────────────────────────────────────
    if step in ('all', 'summary'):
        print("── [2/3] Summary ────────────────────────────────────────")
        papers = summarize_papers(date_str=date_str, papers=papers)
        print(f"     → 요약 완료\n")

    # ── 3. 메일 발송 ──────────────────────────────────────────────────────────
    if step in ('all', 'send'):
        print("── [3/3] Send Mail ──────────────────────────────────────")
        send_mail(date_str=date_str, papers=papers)
        print()

    print("=== Pipeline 완료 ===")


def main():
    parser = argparse.ArgumentParser(
        description="arXiv 논문 자동화 파이프라인",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        '--date', '-d',
        default=None,
        metavar='YYYY-MM-DD',
        help="실행할 날짜 (생략 시 오늘 날짜 사용)",
    )
    parser.add_argument(
        '--step', '-s',
        default='all',
        choices=STEPS,
        help=(
            "실행할 단계 (기본값: all)\n"
            "  all     : 전체 파이프라인 실행\n"
            "  search  : 논문 검색만\n"
            "  summary : 요약만 (기존 JSON 필요)\n"
            "  send    : 메일 발송만 (기존 JSON 필요)\n"
        ),
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help="디버그 모드: 각 단계에서 Excel 등 추가 출력을 저장합니다.",
    )

    args = parser.parse_args()
    date_str = args.date or datetime.today().strftime('%Y-%m-%d')

    run_pipeline(date_str=date_str, debug=args.debug, step=args.step)


if __name__ == '__main__':
    main()