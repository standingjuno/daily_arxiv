"""
config.py
---------
.env 파일을 로드하고 프로젝트 전체 설정을 제공합니다.
모든 모듈은 이 파일에서 설정값을 가져옵니다.
"""

from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv
import os

# 프로젝트 루트의 .env 파일 로드
load_dotenv(Path(__file__).parent / '.env')


def _require(key: str) -> str:
    """필수 환경변수가 없으면 명확한 에러를 냅니다."""
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"[config] 필수 환경변수 '{key}' 가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return val


# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY : str = _require('OPENAI_API_KEY')
OPENAI_MODEL   : str = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

# ── Gmail ─────────────────────────────────────────────────────────────────────
GMAIL_USER         : str = _require('GMAIL_USER')
GMAIL_APP_PASSWORD : str = _require('GMAIL_APP_PASSWORD')

# ── arXiv ─────────────────────────────────────────────────────────────────────
ARXIV_CATEGORY    : str = os.getenv('ARXIV_CATEGORY',    'cs.RO')
ARXIV_MAX_RESULTS : int = int(os.getenv('ARXIV_MAX_RESULTS', '2000'))

# ── 수신자 ────────────────────────────────────────────────────────────────────
# 쉼표(,)와 줄바꿈(\n) 모두 구분자로 지원합니다.
# .env 에서 멀티라인으로 작성하려면 따옴표로 감싸세요:
#
#   EMAIL_RECIPIENTS="
#   standingjuno@gmail.com,
#   wie10044@naver.com,
#   "
#
_recipients_raw : str       = os.getenv('EMAIL_RECIPIENTS', '')
import re as _re
_EMAIL_RE = _re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+')
EMAIL_RECIPIENTS: list[str] = [
    m.group()
    for part in _recipients_raw.splitlines()
    for raw   in part.split(',')
    if (m := _EMAIL_RE.search(raw.split('#')[0]))  # # 이후 제거 후 이메일만 추출
]

# ── 기타 ──────────────────────────────────────────────────────────────────────
OUTPUT_DIR : Path = Path(os.getenv('OUTPUT_DIR', './output'))
DEBUG      : bool = os.getenv('DEBUG', 'false').lower() == 'true'

# output 디렉토리 자동 생성
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)