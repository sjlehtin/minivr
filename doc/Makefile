.PHONY : all minivr.sql clean

.INTERMEDIATE : minivr.sql relations.out.tex

all: minivr.pdf

minivr.sql:
	$(PYTHON) ../devsite/manage.py sqlall minivr > $@

minivr.pdf: minivr.sql relations.out.tex

%.pdf %.aux %.log %.out %.toc %.lol %.lof: %.tex
	-pdflatex -draftmode -interaction batchmode -halt-on-error $<
	pdflatex -interaction nonstopmode -halt-on-error $<

%.out.tex: %.dia
	dia --log-to-stderr --export=$@ $<

clean:
	rm -f minivr.aux minivr.log minivr.out minivr.toc minivr.pdf minivr.lol minivr.lof relations.out.tex
