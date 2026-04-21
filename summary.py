"""
summary.py
----------
arXiv 논문 요약 모듈.

Input  : search.py 가 생성한 JSON 파일
Output : keywords / summary 필드가 채워진 JSON 파일 (덮어쓰기)

- keywords : 영어 키워드 3~5개 (쉼표 구분)
- summary  : 한국어 3~5문장 요약
"""

import json
import time
import argparse
from datetime import datetime
from pathlib import Path

from openai import OpenAI
import config


# ── 설정 (.env → config.py) ───────────────────────────────────────────────────

CATEGORY      = config.ARXIV_CATEGORY
DEFAULT_MODEL = config.OPENAI_MODEL
BATCH_SIZE    = 10     # API 호출 사이 sleep 기준 (N건마다 pause)
SLEEP_SECONDS   = 1.0       # rate-limit 방지용 대기 시간
MAX_RETRIES     = 3         # 실패 시 재시도 횟수

SYSTEM_PROMPT = """\
You are a research assistant specializing in robotics and AI.

Given the title and abstract of an arXiv paper, respond ONLY with a valid JSON object in this exact format:

{
  "keywords": "keyword1, keyword2, keyword3, keyword4, keyword5",
  "summary": "한국어로 2문장 요약"
}

Rules:
- keywords: EXACTLY 5 English keywords, comma-separated, lowercase
- summary: EXACTLY 2 sentences in Korean
- Do NOT include any text outside the JSON object
"""


# ── 핵심 함수 ─────────────────────────────────────────────────────────────────

def _build_user_prompt(paper: dict) -> str:
    abstract = paper['abstract'][:3000]  # 약 300~400 단어 수준
    return f"Title: {paper['title']}\n\nAbstract: {abstract}"


def _create_batch_file(papers, model, file_path):
    with open(file_path, "w", encoding="utf-8") as f:
        for paper in papers:
            req = {
                "custom_id": paper["arxiv_id"],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": _build_user_prompt(paper)},
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                }
            }
            f.write(json.dumps(req, ensure_ascii=False) + "\n")

def _run_batch(client, input_file_path):
    batch_file = client.files.create(
        file=open(input_file_path, "rb"),
        purpose="batch"
    )

    batch = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )

    print(f"[BATCH] job 생성됨: {batch.id}")
    return batch.id

def _wait_and_get_result(client, batch_id):
    import time

    while True:
        batch = client.batches.retrieve(batch_id)
        print(f"[STATUS] {batch.status}")

        if batch.status == "completed":
            if not batch.output_file_id:
                raise RuntimeError("Batch completed but no output file (all failed 가능)")
            break
        
        elif batch.status in ["failed", "cancelled"]:
            raise RuntimeError("Batch 실패")

        time.sleep(5)

    output_file_id = batch.output_file_id

    content = client.files.content(output_file_id)
    return content.text

def _apply_results(papers, result_text):
    paper_index = {p["arxiv_id"]: p for p in papers}

    for line in result_text.splitlines():
        data = json.loads(line)
        paper_id = data.get("custom_id")

        try:
            response = data.get("response", {})
            body = response.get("body", {})
            choices = body.get("choices", [])

            if not choices:
                raise ValueError("choices 없음")

            content = choices[0]["message"]["content"]
            result = json.loads(content)

            paper_index[paper_id]["keywords"] = result.get("keywords", "")
            paper_index[paper_id]["summary"] = result.get("summary", "")

        except Exception as e:
            print(f"[WARN] {paper_id} 파싱 실패: {e}")

    return papers

def summarize_papers(date_str: str | None = None,
                     papers: list[dict] | None = None,
                     category: str = CATEGORY,
                     model: str = DEFAULT_MODEL) -> list[dict]:
    if papers is None:
        if date_str is None:
            date_str = datetime.today().strftime('%Y-%m-%d')

        json_path = config.OUTPUT_DIR / f"arxiv_{category.replace('.', '_')}_{date_str}.json"

        if not json_path.exists():
            raise FileNotFoundError(f"{json_path} 없음. search.py 먼저 실행")

        papers = json.loads(json_path.read_text(encoding="utf-8"))
        print(f"[LOAD] {json_path} ({len(papers)}편)")
    else:
        json_path = None  # 외부에서 넣은 경우

    client = OpenAI(api_key=config.OPENAI_API_KEY)

    def is_summarized(p):
        return (
            isinstance(p.get("summary"), str) and len(p["summary"].strip()) > 10
            and isinstance(p.get("keywords"), str) and len(p["keywords"].split(",")) == 5
        )

    pending = [p for p in papers if not is_summarized(p)]

    if not pending:
        return papers

    batch_file_path = config.OUTPUT_DIR / f"batch_input_{date_str}.jsonl"

    # 1. JSONL 생성
    _create_batch_file(pending, model, batch_file_path)

    # 2. batch 실행
    batch_id = _run_batch(client, batch_file_path)

    print("[INFO] Batch 처리 중... (몇 분 기다려야 함)")

    # 3. 결과 받기
    result_text = _wait_and_get_result(client, batch_id)

    # 4. 결과 반영
    papers = _apply_results(papers, result_text)

    # 5. 저장
    if json_path is not None:
        json_path.write_text(
            json.dumps(papers, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"[SAVE] {json_path}")

    return papers