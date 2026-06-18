# Intelligent Trade Finance — common tasks.
# Windows without `make`: run the commands under each target directly (shown in the README).

.PHONY: install install-llm samples demo test ui clean

install:
	pip install -r requirements.txt

install-llm:
	pip install -r requirements-llm.txt

samples:
	python samples/make_sample_bundle.py

demo: samples
	python demo.py

test:
	pytest -q

ui:
	streamlit run app/ui/streamlit_app.py

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('runs').glob('*')]"
