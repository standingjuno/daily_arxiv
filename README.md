# daily_arxiv

main.py

⌙ config.py (module)

⌙ search.py (module)

⌙ summary.py (module)

⌙ sendmail.py (module)

### Install dependency
```
pip install -r requirements.txt
```

Also, to run this repository, you need to create a .env file with following settings: (OPENAI_API_KEY, OPENAI_MODEL, GMAIL_USER, GMAIL_APP_PASSWORD, ARXIV_CATEGORY, ARXIV_MAX_RESULTS, EMAIL_RECIPIENTS, OUTPUT_DIR, DEBUG).

Example
```
OPENAI_API_KEY=sk-
OPENAI_MODEL=gpt-5.4-nano

GMAIL_USER=mail_id@gmail.com
GMAIL_APP_PASSWORD=

ARXIV_CATEGORY=cs.RO
ARXIV_MAX_RESULTS=2000

EMAIL_RECIPIENTS="
mail_id@gmail.com,
mail_id2@gmail.com,
...
"

OUTPUT_DIR=./output
DEBUG=false
```

### Run
```
python main.py
```