PY=.venv/bin/python
TEST=$(PY) -m pytest -q
run:
	$(PY) -m uvicorn app.api:app --reload
check:
	$(TEST)
