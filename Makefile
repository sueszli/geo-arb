# init venv from imports
.PHONY: venv
venv:
	pip install pip --upgrade
	rm -rf requirements.txt requirements.in .venv
	uvx pipreqs . --mode no-pin --encoding utf-8 --ignore .venv && mv requirements.txt requirements.in && uv pip compile requirements.in -o requirements.txt
	uv venv .venv --python 3.11
	uv pip install -r requirements.txt
	@echo "activate venv with: \033[1;33msource .venv/bin/activate\033[0m"

# dump + compile dependencies
.PHONY: lock
lock:
	uv pip freeze > requirements.in
	uv pip compile requirements.in -o requirements.txt

.PHONY: fmt
fmt:
	uvx isort .
	uvx autoflake --remove-all-unused-imports --recursive --in-place .
	uvx black --line-length 5000 .

.PHONY: md-to-pdf
md-to-pdf:
	pandoc "$(filepath)" -o "$(basename $(filepath)).pdf"

.PHONY: rmd-to-pdf
rmd-to-pdf:
	Rscript -e 'for(p in c("rmarkdown", "ISLR", "IRkernel")) if(!requireNamespace(p, quietly = TRUE)) install.packages(p, repos = "https://cran.rstudio.com")'
	Rscript -e "rmarkdown::render('$(filepath)', output_format = 'pdf_document')"
	rm -rf *.bib *.aux *.log *.out *.synctex.gz
