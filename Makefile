.PHONY: setup run \
        test test-twilio test-azure test-integration test-all \
        lint format requirements \
        conv-generate conv-terminal conv-browser

###################
# Setup & Running #
###################
setup:
	uv sync
	cp azure_functions/local.settings.copythis.json azure_functions/local.settings.json

func-run:
	cd azure_functions && uv run func start

###########
# Testing #
###########
test:
	uv run python -m pytest --ignore=tests/integration/remote

test-azure:
	uv run --group integration python -m pytest tests/integration/remote/test_azure_functions.py -v -rs -s

test-twilio:
	uv run --group integration python -m pytest tests/integration/remote/test_twilio_sms.py -v -rs -s

test-integration:
	uv run --group integration python -m pytest tests/integration -v -rs -s

test-all:
	uv run --group integration python -m pytest -v -rs -s

################
# Code Quality #
################
lint:
	uv run ruff check .

format:
	uv run ruff format .

requirements:
	uv export --no-dev --no-hashes --no-emit-project -o requirements.txt

###################
# Conv Simulation #
###################
conv-generate:
	uv run scripts/conv_simulation.py > conv_simulation.txt
	uvx ansi2html < conv_simulation.txt > conv_simulation.html

conv-terminal: conv_simulation.txt
	cat conv_simulation.txt

conv-browser: conv_simulation.html
	open conv_simulation.html

conv_simulation.txt conv_simulation.html:
	$(MAKE) conv-generate
