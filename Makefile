gettext:
	redgettext --command-docstrings --verbose --recursive .

upload_translations:
	crowdin upload sources

download_translations:
	crowdin download

reformat:
	python3 -m black -l 99 `git ls-files "*.py"`

stylecheck:
	python3 -m black -l 99 --check --diff `git ls-files "*.py"`

compile:
	python3 -m compileall .
